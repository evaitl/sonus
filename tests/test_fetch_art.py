from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sonus.cgi.common import track_ids_with_album
from sonus.fetch_art import apply_cover_bytes_to_tracks


class TrackIdsWithAlbumTests(unittest.TestCase):
    def test_finds_matching_albums_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tracks (
                    id INTEGER PRIMARY KEY,
                    album TEXT,
                    is_missing INTEGER NOT NULL DEFAULT 0,
                    art_path TEXT
                );
                INSERT INTO tracks (id, album, is_missing) VALUES
                    (1, 'Abbey Road', 0),
                    (2, 'abbey road', 0),
                    (3, 'Other', 0),
                    (4, 'Abbey Road', 1);
                """
            )
            ids = track_ids_with_album(conn, "Abbey Road")
            self.assertEqual(ids, [1, 2])
            conn.close()

    def test_empty_album_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE tracks (id INTEGER PRIMARY KEY, album TEXT, is_missing INTEGER)"
            )
            self.assertEqual(track_ids_with_album(conn, ""), [])
            self.assertEqual(track_ids_with_album(conn, None), [])
            conn.close()


class ApplyCoverBytesTests(unittest.TestCase):
    def test_writes_cover_for_each_track(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            art_root = root / "art"
            cover = b"\xff\xd8\xff\xd8" + b"x" * 600
            with mock.patch("sonus.fetch_art.PROJECT_ROOT", root):
                paths = apply_cover_bytes_to_tracks(
                    cover, [10, 11], art_dir=art_root
                )
            self.assertEqual(set(paths), {10, 11})
            self.assertTrue((art_root / "10" / "cover.jpg").is_file())
            self.assertTrue((art_root / "11" / "cover.jpg").is_file())


class PropagateGenreTests(unittest.TestCase):
    def test_fills_blank_genres_on_same_album(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tracks (
                    id INTEGER PRIMARY KEY,
                    album TEXT,
                    genre TEXT,
                    is_missing INTEGER NOT NULL DEFAULT 0
                );
                INSERT INTO tracks (id, album, genre, is_missing) VALUES
                    (1, 'Abbey Road', 'Rock', 0),
                    (2, 'abbey road', NULL, 0),
                    (3, 'Abbey Road', '', 0),
                    (4, 'Abbey Road', 'Jazz', 0),
                    (5, 'Other', NULL, 0);
                """
            )
            from sonus.cgi.common import propagate_genre_to_album_mates

            updated = propagate_genre_to_album_mates(
                conn, track_id=1, album="Abbey Road", genre="Rock"
            )
            self.assertEqual(updated, 2)
            self.assertEqual(
                conn.execute("SELECT genre FROM tracks WHERE id = 2").fetchone()[0],
                "Rock",
            )
            self.assertEqual(
                conn.execute("SELECT genre FROM tracks WHERE id = 3").fetchone()[0],
                "Rock",
            )
            self.assertEqual(
                conn.execute("SELECT genre FROM tracks WHERE id = 4").fetchone()[0],
                "Jazz",
            )
            conn.close()


class PropagateAlbumTests(unittest.TestCase):
    def test_updates_same_album_tracks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE tracks (
                    id INTEGER PRIMARY KEY,
                    album TEXT,
                    genre TEXT,
                    is_missing INTEGER NOT NULL DEFAULT 0
                );
                INSERT INTO tracks (id, album, genre, is_missing) VALUES
                    (1, 'Abbey Road', 'Rock', 0),
                    (2, 'abbey road', NULL, 0),
                    (3, 'Abbey Road', '', 0),
                    (4, 'Other', 'Jazz', 0),
                    (5, 'Abbey Road', 'Pop', 1);
                """
            )
            from sonus.cgi.common import propagate_album_to_album_mates

            updated = propagate_album_to_album_mates(
                conn,
                track_id=1,
                old_album="Abbey Road",
                new_album="Abbey Road (Remastered)",
            )
            self.assertEqual(updated, 2)
            self.assertEqual(
                conn.execute("SELECT album FROM tracks WHERE id = 2").fetchone()[0],
                "Abbey Road (Remastered)",
            )
            self.assertEqual(
                conn.execute("SELECT album FROM tracks WHERE id = 3").fetchone()[0],
                "Abbey Road (Remastered)",
            )
            self.assertEqual(
                conn.execute("SELECT album FROM tracks WHERE id = 4").fetchone()[0],
                "Other",
            )
            conn.close()

    def test_empty_old_album_does_not_propagate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "test.db"
            conn = sqlite3.connect(db)
            conn.execute(
                "CREATE TABLE tracks (id INTEGER PRIMARY KEY, album TEXT, genre TEXT, is_missing INTEGER)"
            )
            from sonus.cgi.common import propagate_album_to_album_mates

            updated = propagate_album_to_album_mates(
                conn, track_id=1, old_album="", new_album="New Album"
            )
            self.assertEqual(updated, 0)
            conn.close()


if __name__ == "__main__":
    unittest.main()
