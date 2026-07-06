import unittest

from scan_music import _ensure_scan_command


class EnsureScanCommandTests(unittest.TestCase):
    def test_inserts_scan_for_verbose_path(self) -> None:
        argv = ["scan_music.py", "-v", "/media/music"]
        _ensure_scan_command(argv)
        self.assertEqual(argv, ["scan_music.py", "scan", "-v", "/media/music"])

    def test_inserts_scan_for_bare_path(self) -> None:
        argv = ["scan_music.py", "/media/music"]
        _ensure_scan_command(argv)
        self.assertEqual(argv, ["scan_music.py", "scan", "/media/music"])

    def test_inserts_scan_when_no_args(self) -> None:
        argv = ["scan_music.py"]
        _ensure_scan_command(argv)
        self.assertEqual(argv, ["scan_music.py", "scan"])

    def test_leaves_explicit_scan_command(self) -> None:
        argv = ["scan_music.py", "scan", "-v", "/media/music"]
        _ensure_scan_command(argv)
        self.assertEqual(argv, ["scan_music.py", "scan", "-v", "/media/music"])

    def test_leaves_other_commands(self) -> None:
        argv = ["scan_music.py", "user", "list"]
        _ensure_scan_command(argv)
        self.assertEqual(argv, ["scan_music.py", "user", "list"])


if __name__ == "__main__":
    unittest.main()
