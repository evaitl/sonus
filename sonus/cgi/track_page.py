"""Shared helpers for rendering the track detail page from CGI scripts."""

from __future__ import annotations

import sqlite3

from sonus.admins import user_can_fetch_art, user_is_admin
from sonus.cgi.common import (
    LibraryContext,
    PlaylistRow,
    TrackRow,
    UserRow,
    get_track,
    list_playlists,
    playlists_for_track,
    track_library_nav_urls,
)
from sonus.cgi.render import render_track


def playlist_context(
    conn: sqlite3.Connection, track_id: int, user: UserRow | None
) -> tuple[list[PlaylistRow], list[PlaylistRow]]:
    if user is None:
        return [], []
    return (
        list_playlists(conn, user_id=user.id),
        playlists_for_track(conn, track_id, user_id=user.id),
    )


def render_track_page(
    track: TrackRow,
    user: UserRow | None,
    playlists: list[PlaylistRow],
    track_playlists: list[PlaylistRow],
    *,
    library: LibraryContext | None = None,
    prev_url: str = "",
    next_url: str = "",
    notice: str = "",
    error: str = "",
) -> str:
    return render_track(
        track,
        playlists,
        track_playlists,
        current_user=user,
        is_admin=user_is_admin(user),
        can_fetch_art=user_can_fetch_art(user, track),
        library=library,
        prev_url=prev_url,
        next_url=next_url,
        notice=notice,
        error=error,
    )


def load_track_context(
    conn: sqlite3.Connection, track_id: int, user: UserRow | None
) -> tuple[TrackRow | None, list[PlaylistRow], list[PlaylistRow]]:
    track = get_track(conn, track_id)
    playlists, track_playlists = playlist_context(conn, track_id, user)
    return track, playlists, track_playlists


def track_page_with_library_nav(
    conn: sqlite3.Connection,
    track_id: int,
    user: UserRow | None,
    library: LibraryContext,
) -> tuple[TrackRow | None, list[PlaylistRow], list[PlaylistRow], str, str]:
    track, playlists, track_playlists = load_track_context(conn, track_id, user)
    prev_url, next_url = track_library_nav_urls(conn, track_id, library)
    return track, playlists, track_playlists, prev_url, next_url
