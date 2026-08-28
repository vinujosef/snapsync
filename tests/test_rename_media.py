from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import re
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
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                redirect_stdout(output),
            ):
                exit_code = run_media_rename(root, settings)

            expected_hash = hashlib.sha256(content).hexdigest()[:12]
            expected = root / f"2026-05-18_142211_iPhone16Pro_{expected_hash}.jpg"
            self.assertEqual(exit_code, 0)
            self.assertFalse(photo.exists())
            self.assertTrue(expected.exists())
            text = _strip_colors(output.getvalue())
            self.assertIn("#  Old name", text)
            self.assertIn("Date", output.getvalue())
            self.assertIn("Fingerprint", output.getvalue())
            self.assertIn(f"1  IMG_0001.JPG  {expected.name}", text)

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
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                redirect_stdout(output),
            ):
                exit_code = run_media_rename(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertTrue(photo.exists())
            expected_hash = hashlib.sha256(b"photo").hexdigest()[:12]
            expected_name = f"2026-05-18_142211_iPhone16Pro_{expected_hash}.jpg"
            text = _strip_colors(output.getvalue())
            self.assertIn("#  Old name", text)
            self.assertIn("Fingerprint", output.getvalue())
            self.assertIn(f"1  IMG_0001.JPG  {expected_name}", text)

    def test_rename_does_not_run_timezone_correction_prompt(self):
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
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.rename_media.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("snapsync.cli.confirm_timezone_correction") as confirm,
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                redirect_stdout(output),
            ):
                exit_code = run_media_rename(root, settings)

            self.assertEqual(exit_code, 0)
            confirm.assert_not_called()
            self.assertNotIn("Timezone correction", output.getvalue())

    def test_rename_lists_files_by_metadata_datetime(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            later = root / "A_LATER.JPG"
            earlier = root / "Z_EARLIER.JPG"
            later.write_bytes(b"later")
            earlier.write_bytes(b"earlier")
            settings = _settings(root, dry_run=True)
            output = StringIO()
            metadata_by_path = {
                later: Metadata(
                    selected_datetime=datetime(2026, 5, 18, 14, 22, 11),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
                earlier: Metadata(
                    selected_datetime=datetime(2026, 5, 17, 14, 22, 11),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
            }

            with (
                patch("snapsync.actions.rename_media.scan_source", return_value=[later, earlier]),
                patch(
                    "snapsync.actions.rename_media.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                redirect_stdout(output),
            ):
                exit_code = run_media_rename(root, settings)

            self.assertEqual(exit_code, 0)
            text = _strip_colors(output.getvalue())
            self.assertLess(text.index("1  Z_EARLIER.JPG"), text.index("2  A_LATER.JPG"))
            first_row = next(line for line in text.splitlines() if line.startswith("1  Z_EARLIER.JPG"))
            second_row = next(line for line in text.splitlines() if line.startswith("2  A_LATER.JPG"))
            separator = "─" * len(first_row)
            self.assertLess(text.index(first_row), text.index(separator))
            self.assertLess(text.index(separator), text.index(second_row))

    def test_rename_requires_yes_before_scanning_or_changing_files(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_0001.JPG"
            content = b"photo"
            photo.write_bytes(content)
            settings = _settings(root, dry_run=False)
            output = StringIO()

            with (
                patch("snapsync.actions.rename_media.scan_source") as scan_source,
                patch("snapsync.actions.rename_media.read_metadata_batch_or_fallback") as read_metadata,
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="no"),
                patch("snapsync.actions.rename_media.logger.warning") as warning,
                redirect_stdout(output),
            ):
                exit_code = run_media_rename(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertTrue(photo.exists())
            scan_source.assert_not_called()
            read_metadata.assert_not_called()
            warning.assert_any_call("Rename was not confirmed; no files were renamed")


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


def _strip_colors(value: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", value)


if __name__ == "__main__":
    unittest.main()
