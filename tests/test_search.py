from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from sonus.cgi.common import _like_contains_pattern, list_tracks


class LikePatternTests(unittest.TestCase):
    def test_wraps_term_for_substring_match(self) -> None:
        self.assertEqual(_like_contains_pattern("quee"), "%quee%")

    def test_escapes_like_wildcards(self) -> None:
        self.assertEqual(_like_contains_pattern("100%"), "%100\\%%")


class ListTracksSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(Path(self.tmp.name) / "test.db")
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
                (1, '/q.mp3', 'q.mp3', 'mp3', 1, 1.0,
                 'Bohemian Rhapsody', 'bohemian rhapsody', 'Queen', 'News of the World', 'Rock',
                 't', 't', 0),
                (2, '/b.mp3', 'b.mp3', 'mp3', 1, 1.0,
                 'Barracuda', 'barracuda', 'Heart', 'Little Queen', 'Rock',
                 't', 't', 0);
            """
        )

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def test_partial_artist_match(self) -> None:
        tracks, count, _, _, _ = list_tracks(self.conn, artist="quee")
        self.assertEqual(count, 1)
        self.assertEqual(tracks[0].artist, "Queen")

    def test_partial_album_match(self) -> None:
        tracks, count, _, _, _ = list_tracks(self.conn, album="news")
        self.assertEqual(count, 1)
        self.assertEqual(tracks[0].album, "News of the World")

    def test_partial_title_match(self) -> None:
        tracks, count, _, _, _ = list_tracks(self.conn, title="bohe")
        self.assertEqual(count, 1)
        self.assertEqual(tracks[0].title, "Bohemian Rhapsody")

    def test_partial_title_word_match(self) -> None:
        tracks, count, _, _, _ = list_tracks(self.conn, title="rhaps")
        self.assertEqual(count, 1)
        self.assertEqual(tracks[0].title, "Bohemian Rhapsody")

    def test_random_sort_supports_pagination(self) -> None:
        for track_id in range(3, 31):
            self.conn.execute(
                """
                INSERT INTO tracks (
                    id, file_path, file_name, format, file_size, file_mtime,
                    title, sort_title, artist, album, genre,
                    first_seen_at, last_scanned_at, is_missing
                ) VALUES (?, ?, ?, 'mp3', 1, 1.0, ?, ?, 'Artist', 'Album', 'Rock', 't', 't', 0)
                """,
                (track_id, f"/{track_id}.mp3", f"{track_id}.mp3", f"Song {track_id}", f"song {track_id}"),
            )
        self.conn.commit()

        page_one, count, _, page, _ = list_tracks(
            self.conn, sort="random", page=1, page_size=25
        )
        page_two, _, _, page_two_num, _ = list_tracks(
            self.conn, sort="random", page=2, page_size=25
        )
        self.assertEqual(count, 30)
        self.assertEqual(page, 1)
        self.assertEqual(page_two_num, 2)
        self.assertEqual(len(page_one), 25)
        self.assertEqual(len(page_two), 5)


if __name__ == "__main__":
    unittest.main()
