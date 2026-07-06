#!/usr/bin/env python3
"""CGI entry point: track detail page."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.cgi.common import connect, get_current_user, library_context_from_form
from sonus.cgi.form import read_cgi_form
from sonus.cgi.render import render_error
from sonus.cgi.track_page import render_track_page, track_page_with_library_nav


def main() -> None:
    form = read_cgi_form()
    raw_id = form.getfirst("id")

    if not raw_id or not str(raw_id).isdigit():
        print("Content-Type: text/html; charset=utf-8")
        print("Status: 400 Bad Request")
        print()
        print(render_error("Invalid track id", status_hint="Bad request"))
        return

    track_id = int(raw_id)
    library = library_context_from_form(form)

    try:
        with connect() as conn:
            current_user = get_current_user(conn)
            track, playlists, track_playlists, prev_url, next_url = (
                track_page_with_library_nav(conn, track_id, current_user, library)
            )
        if track is None or track.is_missing:
            print("Content-Type: text/html; charset=utf-8")
            print("Status: 404 Not Found")
            print()
            print(render_error("Track not found", status_hint="Not found"))
            return
        html = render_track_page(
            track,
            current_user,
            playlists,
            track_playlists,
            library=library,
            prev_url=prev_url,
            next_url=next_url,
        )
        print("Content-Type: text/html; charset=utf-8")
        print()
        print(html)
    except FileNotFoundError as exc:
        print("Content-Type: text/html; charset=utf-8")
        print("Status: 503 Service Unavailable")
        print()
        print(render_error(str(exc), status_hint="Database unavailable"))
    except Exception as exc:
        print("Content-Type: text/html; charset=utf-8")
        print("Status: 500 Internal Server Error")
        print()
        print(render_error(str(exc)))


if __name__ == "__main__":
    main()
