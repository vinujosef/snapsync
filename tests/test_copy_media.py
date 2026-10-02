from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from config.settings import Settings
from snapsync.actions.copy_media import run_media_copy
from snapsync.duplicate import calculate_hash
from snapsync.metadata import Metadata


class CopyMediaTests(unittest.TestCase):
    def test_existing_duplicate_with_different_filename_is_skipped(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_folder = root / "source"
            source_folder.mkdir()
            source = source_folder / "incoming.jpg"
            source.write_bytes(b"same photo")
            destination = root / "destination"
            destination.mkdir()
            (destination / "old-name.jpg").write_bytes(source.read_bytes())
            (destination / "unrelated.mov").write_bytes(b"a much larger unrelated video")
            metadata = Metadata(
                selected_datetime=datetime(2026, 5, 18),
                timestamp_field="DateTimeOriginal", device_name="iPhone",
                quality="metadata",
            )
            with (
                patch("snapsync.actions.copy_media.read_metadata_batch_or_fallback",
                      return_value={source: metadata}),
                patch("snapsync.duplicate.calculate_hash", wraps=calculate_hash) as hashing,
                redirect_stdout(StringIO()) as output,
            ):
                exit_code = run_media_copy(source_folder, _settings(destination, dry_run=False))
            self.assertEqual(exit_code, 0)
            hashing.assert_called_once_with(destination / "old-name.jpg")
            self.assertFalse((destination / "2026").exists())
            summary_text = output.getvalue().split("snapsync Summary", 1)[1]
            self.assertEqual(summary_text.count(str(source)), 2)

    def test_copies_current_filename_to_destination_folder(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "2026-05-18_142211_iPhone16Pro_abc123def456.jpg"
            source.write_bytes(b"photo")
            destination = root / "destination"
            settings = _settings(destination, dry_run=False)
            output = StringIO()
            metadata_by_path = {
                source: Metadata(
                    selected_datetime=datetime(2026, 5, 18, 14, 22, 11),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.copy_media.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_media_copy(root, settings)

            copied = destination / "2026" / "05 - May" / "photo" / source.name
            self.assertEqual(exit_code, 0)
            self.assertTrue(source.exists())
            self.assertTrue(copied.exists())
            self.assertIn("Copied", output.getvalue())


def _settings(destination: Path, *, dry_run: bool) -> Settings:
    return Settings(
        destination_folder=destination,
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
