from __future__ import annotations

import unittest

from sonus.identify import IdentifiedMetadata, metadata_updates_from_identification


class MetadataUpdatesFromIdentificationTests(unittest.TestCase):
    def test_updates_title_and_only_blank_optional_fields(self) -> None:
        identified = IdentifiedMetadata(
            title="New Title",
            artist="New Artist",
            album="New Album",
            genre="Rock",
        )
        updates = metadata_updates_from_identification(
            current_title="Old Title",
            current_artist="",
            current_album=None,
            current_genre="Existing",
            identified=identified,
        )
        self.assertEqual(
            updates,
            {
                "title": "New Title",
                "artist": "New Artist",
                "album": "New Album",
            },
        )

    def test_no_title_means_no_title_update(self) -> None:
        identified = IdentifiedMetadata(artist="Artist")
        updates = metadata_updates_from_identification(
            current_title="Old Title",
            current_artist="Present",
            current_album="Present",
            current_genre="Present",
            identified=identified,
        )
        self.assertEqual(updates, {})


if __name__ == "__main__":
    unittest.main()
