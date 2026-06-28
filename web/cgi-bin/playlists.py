#!/usr/bin/env python3
"""CGI entry point: list and view playlists."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.cgi.form import read_cgi_form
from sonus.cgi.common import (
    connect,
    get_current_user,
    get_playlist,
    list_playlist_tracks,
    list_playlists,
)
from sonus.cgi.render import (
    render_error,
    render_playlist_detail,
    render_playlists,
    render_playlists_login_prompt,
)


def main() -> None:
    form = read_cgi_form()
    raw_id = form.getfirst("id")
    message = form.getfirst("msg", "") or ""

    try:
        with connect() as conn:
            current_user = get_current_user(conn)
            if current_user is None:
                html = render_playlists_login_prompt()
            elif raw_id and str(raw_id).isdigit():
                playlist_id = int(raw_id)
                playlist = get_playlist(conn, playlist_id, user_id=current_user.id)
                if playlist is None:
                    print("Content-Type: text/html; charset=utf-8")
                    print("Status: 404 Not Found")
                    print()
                    print(render_error("Playlist not found", status_hint="Not found"))
                    return
                tracks = list_playlist_tracks(conn, playlist_id)
                html = render_playlist_detail(
                    playlist,
                    tracks,
                    message=message,
                    current_user=current_user,
                )
            else:
                playlists = list_playlists(conn, user_id=current_user.id)
                html = render_playlists(
                    playlists,
                    message=message,
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
