#!/usr/bin/env python3
"""CGI entry point: create and edit playlists."""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.cgi.form import read_cgi_form
from sonus.cgi.common import (
    add_track_to_playlist,
    cgi_script,
    connect,
    connect_rw,
    create_playlist,
    delete_playlist,
    get_current_user,
    remove_track_from_playlist,
    rename_playlist,
)


def _redirect(location: str) -> None:
    print(f"Location: {location}")
    print("Content-Type: text/plain; charset=utf-8")
    print()
    print("Redirecting…")


def _redirect_login(next_path: str) -> None:
    print("Status: 303 See Other")
    print(f"Location: login.py?next={quote(next_path, safe='')}")
    print()


def _playlist_url(playlist_id: int, *, message: str = "") -> str:
    url = f"{cgi_script('playlists.py')}?id={playlist_id}"
    if message:
        url += f"&msg={quote(message)}"
    return url


def main() -> None:
    form = read_cgi_form()
    action = (form.getfirst("action", "") or "").strip().lower()

    try:
        with connect() as read_conn:
            user = get_current_user(read_conn)
        if user is None:
            _redirect_login("playlists.py")
            return

        conn = connect_rw()
        try:
            if action == "create":
                name = form.getfirst("name", "") or ""
                playlist = create_playlist(conn, name, user_id=user.id)
                _redirect(_playlist_url(playlist.id, message="Playlist created"))
                return

            if action == "create_and_add":
                name = form.getfirst("name", "") or ""
                raw_track = form.getfirst("track_id", "")
                if not raw_track or not str(raw_track).isdigit():
                    raise ValueError("Invalid track id")
                playlist = create_playlist(conn, name, user_id=user.id)
                add_track_to_playlist(
                    conn, playlist.id, int(raw_track), user_id=user.id
                )
                _redirect(
                    _playlist_url(playlist.id, message="Playlist created and track added")
                )
                return

            raw_playlist = form.getfirst("playlist_id", "")
            if not raw_playlist or not str(raw_playlist).isdigit():
                raise ValueError("Invalid playlist id")
            playlist_id = int(raw_playlist)

            if action == "delete":
                delete_playlist(conn, playlist_id, user_id=user.id)
                _redirect(f"{cgi_script('playlists.py')}?msg={quote('Playlist deleted')}")
                return

            if action == "rename":
                name = form.getfirst("name", "") or ""
                rename_playlist(conn, playlist_id, name, user_id=user.id)
                _redirect(_playlist_url(playlist_id, message="Playlist renamed"))
                return

            raw_track = form.getfirst("track_id", "")
            if not raw_track or not str(raw_track).isdigit():
                raise ValueError("Invalid track id")
            track_id = int(raw_track)

            if action == "add":
                add_track_to_playlist(conn, playlist_id, track_id, user_id=user.id)
                _redirect(f"{cgi_script('track.py')}?id={track_id}")
                return

            if action == "remove":
                remove_track_from_playlist(
                    conn, playlist_id, track_id, user_id=user.id
                )
                _redirect(_playlist_url(playlist_id, message="Track removed"))
                return

            raise ValueError(f"Unknown action: {action}")
        finally:
            conn.close()
    except FileNotFoundError as exc:
        print("Content-Type: text/html; charset=utf-8")
        print("Status: 503 Service Unavailable")
        print()
        from sonus.cgi.render import render_error

        print(render_error(str(exc), status_hint="Database unavailable"))
    except (ValueError, PermissionError) as exc:
        print("Content-Type: text/html; charset=utf-8")
        print("Status: 400 Bad Request")
        print()
        from sonus.cgi.render import render_error

        print(render_error(str(exc), status_hint="Bad request"))
    except Exception as exc:
        print("Content-Type: text/html; charset=utf-8")
        print("Status: 500 Internal Server Error")
        print()
        from sonus.cgi.render import render_error

        print(render_error(str(exc)))


if __name__ == "__main__":
    main()
