from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import unittest

from config.settings import Settings
from snapsync.actions.rename_media import run_media_rename
from snapsync.metadata import Metadata


class RenameMediaTests(unittest.TestCase):
    def test_renames_media_in_place_using_snapsync_filename_rules(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_0001.JPG"
            content = b"photo"
            photo.write_bytes(content)
            settings = _settings(root, dry_run=False)
            output = StringIO()
            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 5, 18, 14, 22, 11),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.rename_media.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_media_rename(root, settings)

            expected_hash = hashlib.sha256(content).hexdigest()[:12]
            expected = root / f"2026-05-18_142211_iPhone16Pro_{expected_hash}.jpg"
            self.assertEqual(exit_code, 0)
            self.assertFalse(photo.exists())
            self.assertTrue(expected.exists())
            self.assertIn("Renamed", output.getvalue())

    def test_rename_respects_dry_run(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_0001.JPG"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()
            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 5, 18, 14, 22, 11),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.rename_media.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_media_rename(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertTrue(photo.exists())
            self.assertIn("Will rename", output.getvalue())


def _settings(root: Path, *, dry_run: bool) -> Settings:
    return Settings(
        destination_folder=root / "destination",
        dry_run=dry_run,
        log_level="INFO",
        exiftool_path="exiftool",
        filename_prefix="",
        hash_length=12,
        allowed_photo_extensions=frozenset({"jpg"}),
        allowed_video_extensions=frozenset({"mov", "mp4"}),
        ignored_folders=frozenset(),
    )


if __name__ == "__main__":
    unittest.main()
