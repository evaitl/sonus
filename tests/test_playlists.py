from __future__ import annotations

import unittest

from sonus.cgi.common import PlaylistRow, TrackRow
from sonus.cgi.render import render_playlist_detail


def _sample_track(**overrides: object) -> TrackRow:
    base = {
        "id": 1,
        "file_path": "/music/a.mp3",
        "file_name": "a.mp3",
        "format": "mp3",
        "file_size": 100,
        "file_mtime": 1.0,
        "content_hash": "abc",
        "title": "Song",
        "sort_title": None,
        "artist": "Artist",
        "album": "Album",
        "album_artist": None,
        "track_number": None,
        "disc_number": None,
        "year": None,
        "genre": "Rock",
        "duration_seconds": 120.0,
        "art_path": None,
        "first_seen_at": "2026-01-01T00:00:00Z",
        "last_scanned_at": "2026-01-01T00:00:00Z",
        "is_missing": 0,
    }
    base.update(overrides)
    return TrackRow(**base)


class RenderPlaylistDetailTests(unittest.TestCase):
    def test_renders_play_and_shuffle_buttons(self) -> None:
        playlist = PlaylistRow(
            id=1,
            name="Favorites",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            track_count=2,
        )
        tracks = [
            _sample_track(id=1, title="Alpha"),
            _sample_track(id=2, title="Beta"),
        ]
        html = render_playlist_detail(playlist, tracks)
        self.assertIn("Play all", html)
        self.assertIn("Play shuffle", html)
        self.assertIn("data-play-queue=", html)
        self.assertIn("data-shuffle", html)

    def test_empty_playlist_hides_play_buttons(self) -> None:
        playlist = PlaylistRow(
            id=1,
            name="Empty",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            track_count=0,
        )
        html = render_playlist_detail(playlist, [])
        self.assertNotIn("Play all", html)
        self.assertNotIn("Play shuffle", html)


if __name__ == "__main__":
    unittest.main()
