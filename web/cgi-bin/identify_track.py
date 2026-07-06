#!/usr/bin/env python3
"""CGI entry point: identify a track using AcoustID."""

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
    acoustid_client_key,
    connect,
    connect_rw,
    get_current_user,
    library_context_from_form,
    update_track_metadata,
)
from sonus.cgi.form import read_cgi_form
from sonus.cgi.render import render_error
from sonus.cgi.track_page import render_track_page, track_page_with_library_nav
from sonus.identify import (
    IdentifyTrackError,
    identify_track,
    metadata_updates_from_identification,
)


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
                    error="Only administrators can identify tracks.",
                )
            )
            return

        identified = identify_track(
            track.file_path,
            client_key=acoustid_client_key(),
        )
        updates = metadata_updates_from_identification(
            current_title=track.title,
            current_artist=track.artist,
            current_album=track.album,
            current_genre=track.genre,
            identified=identified,
        )
        if not updates:
            _render_track_page(notice="Track identified, but there was nothing to update.")
            return

        conn = connect_rw()
        try:
            update_track_metadata(conn, track_id, updates)
        finally:
            conn.close()

        parts = ["Track identified."]
        if "title" in updates:
            parts.append("Title updated.")
        if "artist" in updates:
            parts.append("Artist filled in.")
        if "album" in updates:
            parts.append("Album filled in.")
        if "genre" in updates:
            parts.append("Genre filled in.")
        _render_track_page(notice=" ".join(parts))
    except IdentifyTrackError as exc:
        _render_track_page(error=str(exc))
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
    except Exception:
        traceback.print_exc(file=sys.stderr)
        _render_track_page(error="Unexpected error while identifying the track.")


if __name__ == "__main__":
    main()
