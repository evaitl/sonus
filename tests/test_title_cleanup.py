import unittest

from sonus.title_cleanup import clean_leading_track_number_title


class CleanLeadingTrackNumberTitleTests(unittest.TestCase):
    def test_removes_number_dash_space_prefix(self) -> None:
        self.assertEqual(clean_leading_track_number_title("04 - Bonnie"), "Bonnie")

    def test_removes_number_space_prefix(self) -> None:
        self.assertEqual(clean_leading_track_number_title("01 Escape"), "Escape")

    def test_removes_number_underscore_prefix(self) -> None:
        self.assertEqual(
            clean_leading_track_number_title("01_Night at the Opera"),
            "Night at the Opera",
        )

    def test_leaves_number_only_title(self) -> None:
        self.assertIsNone(clean_leading_track_number_title("01"))
        self.assertIsNone(clean_leading_track_number_title("04"))

    def test_leaves_normal_titles(self) -> None:
        self.assertIsNone(clean_leading_track_number_title("Bonnie"))
        self.assertIsNone(clean_leading_track_number_title("Night at the Opera"))

    def test_removes_number_dash_without_spaces(self) -> None:
        self.assertEqual(clean_leading_track_number_title("04-Bonnie"), "Bonnie")

    def test_strips_surrounding_whitespace(self) -> None:
        self.assertEqual(clean_leading_track_number_title("  02 - Song  "), "Song")


if __name__ == "__main__":
    unittest.main()
