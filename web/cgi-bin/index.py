#!/usr/bin/env python3
"""CGI entry point: browse the indexed music collection."""

from __future__ import annotations

import cgi
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.cgi.common import connect, get_current_user, list_tracks
from sonus.cgi.render import render_error, render_library


def main() -> None:
    form = cgi.FieldStorage()
    title = form.getfirst("title", "") or ""
    artist = form.getfirst("artist", "") or ""
    album = form.getfirst("album", "") or ""
    genre = form.getfirst("genre", "") or ""
    sort = form.getfirst("sort", "title") or "title"
    sort_dir = form.getfirst("sort_dir", "") or ""
    raw_page_size = form.getfirst("page_size", "") or ""
    raw_page = form.getfirst("page", "1") or "1"
    page = int(raw_page) if str(raw_page).isdigit() else 1

    try:
        with connect() as conn:
            current_user = get_current_user(conn)
            tracks, filtered_count, library_total, page, options = list_tracks(
                conn,
                title=title,
                artist=artist,
                album=album,
                genre=genre,
                sort=sort,
                sort_dir=sort_dir,
                page=page,
                page_size=raw_page_size,
            )
        html = render_library(
            tracks,
            filtered_count,
            library_total,
            page,
            options,
            selected_title=title,
            selected_artist=artist,
            selected_album=album,
            selected_genre=genre,
            sort=sort,
            sort_dir=sort_dir,
            page_size=raw_page_size,
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
