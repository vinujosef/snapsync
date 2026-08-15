from datetime import datetime
from pathlib import Path
import unittest

from config.settings import Settings
from syncsnap.util.paths import build_destination_folder, build_destination_path


class PathTests(unittest.TestCase):
    def test_build_destination_path_uses_destination_folder_directly(self):
        settings = Settings(
            destination_folder=Path("/tmp/destination"),
            dry_run=True,
            log_level="INFO",
            exiftool_path="exiftool",
            filename_prefix="",
            hash_length=12,
            allowed_photo_extensions=frozenset({"jpg"}),
            allowed_video_extensions=frozenset({"mov"}),
            ignored_folders=frozenset(),
        )

        folder = build_destination_folder(settings, datetime(2026, 5, 18), "photo")
        path = build_destination_path(settings, datetime(2026, 5, 18), "photo", "file.jpg")

        self.assertEqual(folder, Path("/tmp/destination/2026/05 - May/photo"))
        self.assertEqual(path, Path("/tmp/destination/2026/05 - May/photo/file.jpg"))


if __name__ == "__main__":
    unittest.main()
