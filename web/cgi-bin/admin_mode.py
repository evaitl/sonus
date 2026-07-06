#!/usr/bin/env python3
"""CGI entry point: toggle administrator mode for listed users."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.admins import user_is_admin_listed
from sonus.auth import admin_mode_cookie_header
from sonus.cgi.common import connect, get_current_user, safe_referer_location
from sonus.cgi.form import read_cgi_form


def main() -> None:
    if os.environ.get("REQUEST_METHOD", "GET").upper() != "POST":
        print("Status: 405 Method Not Allowed")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("POST required")
        return

    with connect() as conn:
        current_user = get_current_user(conn)

    if not user_is_admin_listed(current_user):
        print("Status: 403 Forbidden")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Forbidden")
        return

    form = read_cgi_form()
    enable = form.getfirst("enable") == "1"

    print("Status: 303 See Other")
    print(f"Location: {safe_referer_location()}")
    print(admin_mode_cookie_header(enabled=enable))
    print()


if __name__ == "__main__":
    main()
