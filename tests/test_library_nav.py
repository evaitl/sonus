from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sonus.cgi.common import (
    LibraryContext,
    adjacent_library_tracks,
    effective_library_for_track_nav,
    library_context_from_form,
    parse_library_context,
    track_href,
    track_library_nav_urls,
)
from sonus.cgi.form import CgiForm
from sonus.cgi.render import _library_context_hidden_inputs, render_track
from sonus.cgi.common import TrackRow


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
        "sort_title": "song",
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


class AdjacentLibraryTracksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                format TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_mtime REAL NOT NULL,
                content_hash TEXT,
                title TEXT,
                sort_title TEXT,
                artist TEXT,
                album TEXT,
                album_artist TEXT,
                track_number INTEGER,
                disc_number INTEGER,
                year TEXT,
                genre TEXT,
                duration_seconds REAL,
                art_path TEXT,
                first_seen_at TEXT NOT NULL,
                last_scanned_at TEXT NOT NULL,
                is_missing INTEGER NOT NULL DEFAULT 0
            );
            INSERT INTO tracks (
                id, file_path, file_name, format, file_size, file_mtime,
                title, sort_title, artist, album, genre,
                first_seen_at, last_scanned_at, is_missing
            ) VALUES
                (1, '/a.mp3', 'a.mp3', 'mp3', 1, 1.0, 'Alpha', 'alpha', 'A', 'One', 'Rock', 't', 't', 0),
                (2, '/b.mp3', 'b.mp3', 'mp3', 1, 1.0, 'Beta', 'beta', 'B', 'One', 'Rock', 't', 't', 0),
                (3, '/c.mp3', 'c.mp3', 'mp3', 1, 1.0, 'Gamma', 'gamma', 'C', 'Two', 'Jazz', 't', 't', 0);
            """
        )

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_adjacent_tracks_in_title_order(self) -> None:
        library = parse_library_context()
        self.assertEqual(adjacent_library_tracks(self.conn, 2, library), (1, 3))

    def test_adjacent_respects_genre_filter(self) -> None:
        library = parse_library_context(genre="Rock")
        self.assertEqual(adjacent_library_tracks(self.conn, 2, library), (1, None))
        self.assertEqual(adjacent_library_tracks(self.conn, 1, library), (None, 2))

    def test_random_sort_has_no_adjacent_tracks(self) -> None:
        library = parse_library_context(sort="random")
        self.assertEqual(adjacent_library_tracks(self.conn, 2, library), (None, None))

    def test_track_href_preserves_library_context(self) -> None:
        library = LibraryContext(genre="Rock", sort="artist", sort_dir="desc")
        href = track_href(2, library=library)
        self.assertIn("id=2", href)
        self.assertIn("genre=Rock", href)
        self.assertIn("sort=artist", href)
        self.assertIn("sort_dir=desc", href)

    def test_track_library_nav_urls(self) -> None:
        library = parse_library_context()
        prev_url, next_url = track_library_nav_urls(self.conn, 2, library)
        self.assertIn("id=1", prev_url)
        self.assertIn("id=3", next_url)

    def test_nav_falls_back_when_track_not_in_filter(self) -> None:
        self.conn.execute("UPDATE tracks SET genre = 'Jazz' WHERE id = 2")
        self.conn.commit()
        filtered = parse_library_context(genre="Rock")
        self.assertEqual(adjacent_library_tracks(self.conn, 2, filtered), (1, 3))
        effective = effective_library_for_track_nav(self.conn, 2, filtered)
        self.assertEqual(effective.genre, "")
        prev_url, next_url = track_library_nav_urls(self.conn, 2, filtered)
        self.assertIn("id=1", prev_url)
        self.assertIn("id=3", next_url)
        self.assertNotIn("genre=", prev_url)


class LibraryContextFormTests(unittest.TestCase):
    def test_hidden_inputs_use_prefixed_names(self) -> None:
        html = _library_context_hidden_inputs(LibraryContext(title="quee", genre="Rock"))
        self.assertIn('name="lib_title"', html)
        self.assertIn('value="quee"', html)
        self.assertIn('name="lib_genre"', html)
        self.assertNotIn('name="title"', html)

    def test_library_context_from_form_reads_prefixed_post_fields(self) -> None:
        form = CgiForm(
            {
                "lib_title": ["quee"],
                "lib_genre": ["Rock"],
                "title": ["Bonnie"],
            }
        )
        library = library_context_from_form(form)
        self.assertEqual(library.title, "quee")
        self.assertEqual(library.genre, "Rock")

    def test_library_context_from_form_reads_get_query_fields(self) -> None:
        form = CgiForm({"title": ["quee"], "genre": ["Rock"]})
        library = library_context_from_form(form)
        self.assertEqual(library.title, "quee")
        self.assertEqual(library.genre, "Rock")


class RenderTrackNavTests(unittest.TestCase):
    def test_renders_track_navigation_markup(self) -> None:
        track = _sample_track()
        html = render_track(
            track,
            [],
            [],
            prev_url="track.py?id=0",
            next_url="track.py?id=2",
        )
        self.assertIn('data-page-nav', html)
        self.assertIn('data-prev-url="track.py?id=0"', html)
        self.assertIn('data-next-url="track.py?id=2"', html)
        self.assertIn("Previous track", html)
        self.assertIn("Next track", html)


if __name__ == "__main__":
    unittest.main()
