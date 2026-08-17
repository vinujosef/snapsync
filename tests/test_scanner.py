from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from config.settings import Settings
from snapsync.scanner import scan_source


class ScannerTests(unittest.TestCase):
    def test_scan_source_ignores_hidden_and_configured_folders(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "photo.jpg").write_bytes(b"photo")
            (root / ".DS_Store").write_bytes(b"finder")
            ignored = root / "skipme"
            ignored.mkdir()
            (ignored / "ignored.jpg").write_bytes(b"ignored")

            settings = Settings(
                destination_folder=root / "destination",
                dry_run=True,
                log_level="INFO",
                exiftool_path="exiftool",
                filename_prefix="",
                hash_length=12,
                allowed_photo_extensions=frozenset({"jpg"}),
                allowed_video_extensions=frozenset({"mov"}),
                ignored_folders=frozenset({"skipme"}),
            )

            self.assertEqual(scan_source(root, settings), [root / "photo.jpg"])


if __name__ == "__main__":
    unittest.main()
