#!/usr/bin/env python3
"""CGI entry point: fetch online album art for a track."""

from __future__ import annotations

import os
import sqlite3
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.cgi.form import read_cgi_form
from sonus.cgi.common import (
    art_dir,
    connect,
    connect_rw,
    get_current_user,
    get_track,
    list_playlists,
    playlists_for_track,
    update_track_fields,
)
from sonus.cgi.render import render_error, render_track
from sonus.fetch_art import FetchArtError, enrich_track_art


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

    try:
        conn = connect_rw()
        try:
            track = get_track(conn, track_id)
            if track is None or track.is_missing:
                _html(render_error("Track not found.", status_hint="Not found"))
                return

            result = enrich_track_art(
                track_id=track_id,
                artist=track.artist,
                album=track.album,
                title=track.title,
                art_dir=art_dir(),
            )
            update_track_fields(
                conn,
                track_id,
                {"art_path": result.art_path},
            )
            source = result.source
        finally:
            conn.close()

        with connect() as conn:
            track = get_track(conn, track_id)
            current_user = get_current_user(conn)
            playlists = []
            track_playlists = []
            if current_user is not None:
                playlists = list_playlists(conn, user_id=current_user.id)
                track_playlists = playlists_for_track(
                    conn, track_id, user_id=current_user.id
                )

        if track is None:
            _html(render_error("Track not found after update.", status_hint="Not found"))
            return

        _html(
            render_track(
                track,
                playlists,
                track_playlists,
                current_user=current_user,
                notice=f"Album art updated from {source}",
            )
        )
    except FileNotFoundError as exc:
        _html(render_error(str(exc), status_hint="Database unavailable"))
    except PermissionError as exc:
        with connect() as conn:
            track = get_track(conn, track_id)
            current_user = get_current_user(conn)
        if track is None:
            _html(render_error(str(exc)))
            return
        _html(
            render_track(
                track,
                [],
                [],
                current_user=current_user,
                error=str(exc),
            )
        )
    except sqlite3.OperationalError as exc:
        message = str(exc)
        if "readonly" in message.lower():
            message = (
                "Database is read-only for the web server. Grant www-data write "
                "access to the data/ directory (see scripts/setup-data-dir.sh)."
            )
        with connect() as conn:
            track = get_track(conn, track_id)
            current_user = get_current_user(conn)
        if track is None:
            _html(render_error(message))
            return
        _html(
            render_track(
                track,
                [],
                [],
                current_user=current_user,
                error=message,
            )
        )
    except FetchArtError as exc:
        with connect() as conn:
            track = get_track(conn, track_id)
            current_user = get_current_user(conn)
            playlists = []
            track_playlists = []
            if current_user is not None:
                playlists = list_playlists(conn, user_id=current_user.id)
                track_playlists = playlists_for_track(
                    conn, track_id, user_id=current_user.id
                )
        if track is None:
            _html(render_error(str(exc)))
            return
        _html(
            render_track(
                track,
                playlists,
                track_playlists,
                current_user=current_user,
                error=str(exc),
            )
        )
    except Exception:
        traceback.print_exc(file=sys.stderr)
        with connect() as conn:
            track = get_track(conn, track_id)
            current_user = get_current_user(conn)
        if track is None:
            _html(render_error("Unexpected error while fetching album art."))
            return
        _html(
            render_track(
                track,
                [],
                [],
                current_user=current_user,
                error="Unexpected error while fetching album art.",
            )
        )


if __name__ == "__main__":
    main()
