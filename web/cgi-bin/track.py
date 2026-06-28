#!/usr/bin/env python3
"""CGI entry point: track detail page."""

from __future__ import annotations

import cgi
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.cgi.common import (
    connect,
    get_current_user,
    get_track,
    list_playlists,
    playlists_for_track,
)
from sonus.cgi.render import render_error, render_track


def main() -> None:
    form = cgi.FieldStorage()
    raw_id = form.getfirst("id")

    if not raw_id or not str(raw_id).isdigit():
        print("Content-Type: text/html; charset=utf-8")
        print("Status: 400 Bad Request")
        print()
        print(render_error("Invalid track id", status_hint="Bad request"))
        return

    track_id = int(raw_id)

    try:
        with connect() as conn:
            track = get_track(conn, track_id)
            if track is None or track.is_missing:
                print("Content-Type: text/html; charset=utf-8")
                print("Status: 404 Not Found")
                print()
                print(render_error("Track not found", status_hint="Not found"))
                return
            current_user = get_current_user(conn)
            playlists = (
                list_playlists(conn, user_id=current_user.id)
                if current_user is not None
                else []
            )
            track_playlists = (
                playlists_for_track(conn, track_id, user_id=current_user.id)
                if current_user is not None
                else []
            )
        html = render_track(
            track,
            playlists,
            track_playlists,
            current_user=current_user,
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
