import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sonus.scanner import (
    collect_track_files,
    print_scan_progress,
    safe_console_text,
)


class SafeConsoleTextTests(unittest.TestCase):
    def test_replaces_lone_surrogates(self) -> None:
        self.assertEqual(safe_console_text("song\udcb4name.mp3"), "song?name.mp3")

    def test_print_scan_progress_handles_surrogate_filename(self) -> None:
        bad_name = "track\udcb4file.mp3"
        with mock.patch("builtins.print") as print_mock:
            print_scan_progress(1, 1, Path(bad_name), "error")
        printed = print_mock.call_args.args[0]
        self.assertNotIn("\udcb4", printed)
        self.assertIn("error:", printed)


class CollectTrackFilesTests(unittest.TestCase):
    def test_collects_supported_audio_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mp3 = root / "song.mp3"
            mp3.write_bytes(b"mp3")
            files, errors, transcoded = collect_track_files([root])
            self.assertEqual(errors, [])
            self.assertEqual(transcoded, 0)
            self.assertEqual(files, [mp3.resolve()])

    def test_verbose_reports_unsupported_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "song.mp3").write_bytes(b"mp3")
            cover = root / "cover.jpg"
            cover.write_bytes(b"jpg")
            skipped: list = []
            files, errors, transcoded = collect_track_files(
                [root], verbose=True, skipped=skipped
            )
            self.assertEqual(len(files), 1)
            self.assertEqual(errors, [])
            self.assertEqual(transcoded, 0)
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0].path, cover.resolve())
            self.assertIn("unsupported file type", skipped[0].reason)

    def test_verbose_reports_missing_scan_path(self) -> None:
        missing = Path("/nonexistent/sonus-scan-path")
        skipped: list = []
        files, errors, transcoded = collect_track_files(
            [missing], verbose=True, skipped=skipped
        )
        self.assertEqual(files, [])
        self.assertEqual(transcoded, 0)
        self.assertEqual(len(errors), 1)
        self.assertIn("path not found", errors[0])
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0].path, missing.resolve())
        self.assertEqual(skipped[0].reason, "path not found")

    def test_verbose_reports_mp3_when_companion_wma_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wma = root / "song.wma"
            mp3 = root / "song.mp3"
            wma.write_bytes(b"wma")
            mp3.write_bytes(b"mp3")
            skipped: list = []
            files, errors, transcoded = collect_track_files(
                [root], verbose=True, skipped=skipped
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0].path, mp3.resolve())
            self.assertEqual(skipped[0].reason, "companion WMA exists")
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].suffix.lower(), ".mp3")

    def test_does_not_record_skips_without_verbose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "song.mp3").write_bytes(b"mp3")
            (root / "notes.txt").write_bytes(b"txt")
            skipped: list = []
            collect_track_files([root], verbose=False, skipped=skipped)
            self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
