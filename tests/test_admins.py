from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sonus.admins import (
    admin_mode_enabled,
    parse_admins_text,
    user_is_admin,
    user_is_admin_listed,
)
from sonus.cgi.common import TrackRow, UserRow, parse_track_metadata_form
from sonus.cgi.form import CgiForm
from sonus.cgi.render import _header_auth, render_track


def _sample_track() -> TrackRow:
    return TrackRow(
        id=1,
        file_path="/music/a.mp3",
        file_name="a.mp3",
        format="mp3",
        file_size=100,
        file_mtime=1.0,
        content_hash="abc",
        title="Song",
        sort_title=None,
        artist="Artist",
        album="Album",
        album_artist=None,
        track_number=None,
        disc_number=None,
        year=None,
        genre="Rock",
        duration_seconds=120.0,
        art_path=None,
        first_seen_at="2026-01-01T00:00:00Z",
        last_scanned_at="2026-01-01T00:00:00Z",
        is_missing=0,
    )


class ParseAdminsTextTests(unittest.TestCase):
    def test_skips_comments_and_blank_lines(self) -> None:
        text = """
        # comment
        Alice
        bob

          carol
        """
        self.assertEqual(
            parse_admins_text(text),
            frozenset({"alice", "bob", "carol"}),
        )


class UserIsAdminTests(unittest.TestCase):
    def test_requires_login(self) -> None:
        self.assertFalse(user_is_admin(None))

    def test_requires_admin_mode_cookie(self) -> None:
        user = UserRow(id=1, username="alice")
        admins_file = None
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("alice\n")
            admins_file = handle.name
        try:
            with mock.patch("sonus.admins.admins_file_path", return_value=Path(admins_file)):
                self.assertTrue(user_is_admin_listed(user))
                with mock.patch.dict(os.environ, {}, clear=True):
                    self.assertFalse(user_is_admin(user))
                with mock.patch.dict(
                    os.environ,
                    {"HTTP_COOKIE": "sonus_admin_mode=1"},
                    clear=True,
                ):
                    self.assertTrue(user_is_admin(user))
        finally:
            if admins_file:
                Path(admins_file).unlink(missing_ok=True)


class HeaderAdminToggleTests(unittest.TestCase):
    def test_listed_user_sees_admin_checkbox(self) -> None:
        user = UserRow(id=1, username="alice")
        with mock.patch("sonus.cgi.render.user_is_admin_listed", return_value=True):
            with mock.patch("sonus.cgi.render.admin_mode_enabled", return_value=False):
                html = _header_auth(user)
        self.assertIn("admin_mode.py", html)
        self.assertIn('name="enable"', html)

    def test_non_listed_user_has_no_checkbox(self) -> None:
        user = UserRow(id=2, username="bob")
        with mock.patch("sonus.cgi.render.user_is_admin_listed", return_value=False):
            html = _header_auth(user)
        self.assertNotIn("admin_mode.py", html)


class TrackAdminUiTests(unittest.TestCase):
    def test_admin_mode_sees_fetch_and_edit(self) -> None:
        track = _sample_track()
        user = UserRow(id=1, username="admin")
        html = render_track(track, [], [], current_user=user, is_admin=True)
        self.assertIn("Fetch album art", html)
        self.assertIn("Edit metadata", html)
        self.assertIn('name="title"', html)
        self.assertIn('name="genre"', html)
        self.assertIn("track_edit.py", html)

    def test_non_admin_hides_admin_controls(self) -> None:
        track = _sample_track()
        user = UserRow(id=2, username="regular")
        html = render_track(track, [], [], current_user=user, is_admin=False)
        self.assertNotIn("Fetch album art", html)
        self.assertNotIn("Edit metadata", html)


class ParseTrackMetadataFormTests(unittest.TestCase):
    def test_parses_and_trims_fields(self) -> None:
        form = CgiForm(
            {
                "title": ["  New Title  "],
                "artist": ["Artist"],
                "album": [""],
                "genre": ["Jazz"],
            }
        )
        self.assertEqual(
            parse_track_metadata_form(form),
            {
                "title": "New Title",
                "artist": "Artist",
                "album": None,
                "genre": "Jazz",
            },
        )


if __name__ == "__main__":
    unittest.main()
