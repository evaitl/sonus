import unittest
from pathlib import Path

from sonus.console import format_scan_error, has_bad_filename_unicode, safe_console_text


class ConsoleTextTests(unittest.TestCase):
    def test_replaces_lone_surrogates(self) -> None:
        self.assertEqual(safe_console_text("song\udcb4name.mp3"), "song?name.mp3")

    def test_format_scan_error_sanitizes_path_and_message(self) -> None:
        err = format_scan_error("/music/\udcb4bad.mp3", "read failed")
        self.assertNotIn("\udcb4", err)
        self.assertIn("read failed", err)

    def test_detects_bad_filename_unicode(self) -> None:
        self.assertTrue(has_bad_filename_unicode(Path("track\udcb4.mp3")))
        self.assertFalse(has_bad_filename_unicode(Path("normal.mp3")))


if __name__ == "__main__":
    unittest.main()
