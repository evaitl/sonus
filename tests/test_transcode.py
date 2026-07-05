from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sonus.transcode import (
    mp3_path_for_wma,
    needs_transcode,
    transcode_wma_to_mp3,
)


class NeedsTranscodeTests(unittest.TestCase):
    def test_returns_true_when_expected_mp3_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wma = Path(tmp) / "07_Track Name.wma"
            wma.write_bytes(b"wma")
            mp3 = mp3_path_for_wma(wma)
            self.assertFalse(mp3.exists())
            self.assertTrue(needs_transcode(wma, mp3))

    def test_returns_false_when_mp3_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wma = Path(tmp) / "07_Track Name.wma"
            mp3 = mp3_path_for_wma(wma)
            wma.write_bytes(b"wma")
            mp3.write_bytes(b"mp3")
            self.assertFalse(needs_transcode(wma, mp3))

    def test_transcode_runs_when_expected_mp3_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wma = Path(tmp) / "07_Track Name.wma"
            wma.write_bytes(b"wma")
            mp3 = mp3_path_for_wma(wma)

            def fake_run(*_args, **_kwargs):
                mp3.write_bytes(b"mp3")
                return mock.Mock(returncode=0, stdout="", stderr="")

            with mock.patch("sonus.transcode.subprocess.run", side_effect=fake_run):
                with mock.patch("sonus.transcode.find_ffmpeg", return_value="ffmpeg"):
                    mp3_path, was_transcoded = transcode_wma_to_mp3(wma)

            self.assertTrue(was_transcoded)
            self.assertEqual(mp3_path, mp3)
            self.assertTrue(mp3.is_file())
            self.assertFalse(wma.exists())


if __name__ == "__main__":
    unittest.main()
