#!/usr/bin/env python3
"""CGI entry point: update track metadata (administrators only)."""

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
    connect,
    connect_rw,
    get_current_user,
    library_context_from_form,
    parse_track_metadata_form,
    propagate_album_to_album_mates,
    propagate_genre_to_album_mates,
    update_track_metadata,
)
from sonus.cgi.form import read_cgi_form
from sonus.cgi.render import render_error
from sonus.cgi.track_page import render_track_page, track_page_with_library_nav


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
                    error="Only administrators can edit track metadata.",
                )
            )
            return

        metadata = parse_track_metadata_form(form)
        original_album = track.album
        conn = connect_rw()
        try:
            update_track_metadata(conn, track_id, metadata)
            propagated_album = propagate_album_to_album_mates(
                conn,
                track_id=track_id,
                old_album=original_album,
                new_album=metadata.get("album"),
            )
            propagated = propagate_genre_to_album_mates(
                conn,
                track_id=track_id,
                album=metadata.get("album"),
                genre=metadata.get("genre"),
            )
        finally:
            conn.close()

        notice = "Metadata saved."
        if propagated_album:
            notice += (
                f" Album updated for {propagated_album} other track(s) on this album."
            )
        if propagated:
            notice += (
                f" Genre applied to {propagated} other track(s) on this album."
            )

        _render_track_page(notice=notice)
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
        _render_track_page(error="Unexpected error while saving metadata.")


if __name__ == "__main__":
    main()
