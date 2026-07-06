#!/usr/bin/env python3
"""CGI entry point: upload album art from the browser."""

from __future__ import annotations

import os
import sqlite3
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.admins import user_is_admin
from sonus.cgi.common import (
    art_dir,
    connect,
    connect_rw,
    get_current_user,
    library_context_from_form,
    track_ids_with_album,
    update_tracks_art_paths,
)
from sonus.cgi.form import read_cgi_form
from sonus.cgi.render import render_error
from sonus.cgi.track_page import render_track_page, track_page_with_library_nav
from sonus.fetch_art import FetchArtError, save_uploaded_cover


def _html(body: str) -> None:
    print("Content-Type: text/html; charset=utf-8")
    print()
    print(body)


def main() -> None:
    if os.environ.get("REQUEST_METHOD", "GET").upper() != "POST":
        _html(render_error("POST required.", status_hint="Method not allowed"))
        return

    form = read_cgi_form()
    raw_id = form.getfirst("id")
    if not raw_id or not str(raw_id).isdigit():
        _html(render_error("Missing or invalid track id.", status_hint="Bad request"))
        return

    track_id = int(raw_id)
    library = library_context_from_form(form)

    def _render_track_page(**kwargs: object) -> None:
        with connect() as conn:
            current_user = get_current_user(conn)
            track, playlists, track_playlists, prev_url, next_url = (
                track_page_with_library_nav(conn, track_id, current_user, library)
            )
        if track is None:
            _html(render_error("Track not found.", status_hint="Not found"))
            return
        _html(
            render_track_page(
                track,
                current_user,
                playlists,
                track_playlists,
                library=library,
                prev_url=prev_url,
                next_url=next_url,
                **kwargs,
            )
        )

    try:
        with connect() as conn:
            current_user = get_current_user(conn)
            track, playlists, track_playlists, prev_url, next_url = (
                track_page_with_library_nav(conn, track_id, current_user, library)
            )

        if track is None or track.is_missing:
            _html(render_error("Track not found.", status_hint="Not found"))
            return

        if not user_is_admin(current_user):
            _html(
                render_track_page(
                    track,
                    current_user,
                    playlists,
                    track_playlists,
                    library=library,
                    prev_url=prev_url,
                    next_url=next_url,
                    error="Only administrators can upload album art.",
                )
            )
            return

        upload = form.getfile("art")
        if upload is None or not upload.value:
            _render_track_page(error="Choose an image file to upload.")
            return

        with connect() as read_conn:
            album_track_ids = track_ids_with_album(read_conn, track.album)
        if not album_track_ids:
            album_track_ids = [track_id]

        conn = connect_rw()
        try:
            result = save_uploaded_cover(
                upload.value,
                track_id=track_id,
                track_ids=album_track_ids,
                art_dir=art_dir(),
            )
            update_tracks_art_paths(conn, result.art_paths)
        finally:
            conn.close()

        notice = "Album art uploaded."
        if len(result.updated_track_ids) > 1:
            notice += (
                f" Applied to {len(result.updated_track_ids)} tracks with the same album."
            )
        _render_track_page(notice=notice)
    except ValueError as exc:
        _render_track_page(error=str(exc))
    except FileNotFoundError as exc:
        _html(render_error(str(exc), status_hint="Database unavailable"))
    except PermissionError as exc:
        _render_track_page(error=str(exc))
    except sqlite3.OperationalError as exc:
        message = str(exc)
        if "readonly" in message.lower():
            message = (
                "Database is read-only for the web server. Grant www-data write "
                "access to the data/ directory (see scripts/setup-data-dir.sh)."
            )
        _render_track_page(error=message)
    except FetchArtError as exc:
        _render_track_page(error=str(exc))
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _render_track_page(error="Unexpected error while uploading album art.")


if __name__ == "__main__":
    main()
