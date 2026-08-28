from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import re
import unittest

from config.settings import Settings
from snapsync.actions.audit_folder import run_folder_audit
from snapsync.metadata import Metadata


class AuditFolderTests(unittest.TestCase):
    def test_prints_file_count_and_metadata_table(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "IMG_0001.JPG"
            second = root / "clip.mov"
            first.write_bytes(b"photo")
            second.write_bytes(b"video")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                first: Metadata(
                    selected_datetime=datetime(2026, 5, 18, 14, 22, 11),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
                second: Metadata(
                    selected_datetime=datetime(2026, 5, 19, 9, 1, 2),
                    timestamp_field="MediaCreateDate",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            text = output.getvalue()
            plain_text = _strip_colors(text)
            self.assertEqual(exit_code, 0)
            self.assertIn("ℹ️ Info", plain_text)
            self.assertIn("Files  2", plain_text)
            self.assertIn("Legend", plain_text)
            self.assertIn("red = needs review", plain_text)
            self.assertIn("Rules", plain_text)
            self.assertIn("Timezone baseline  Europe/Helsinki", plain_text)
            self.assertIn("\033[36mHelsinki 2026: +03:00 from 29-03-2026, +02:00 from 25-10-2026\033[0m", text)
            self.assertIn(
                "Timestamp priority  DateTimeOriginal > CreateDate > MediaCreateDate > "
                "TrackCreateDate > FileModifyDate > FileCreateDate",
                plain_text,
            )
            self.assertIn("🔍 Audit Details", plain_text)
            self.assertIn(
                "Filename      Date        Time      Taken From",
                plain_text,
            )
            self.assertIn(
                "IMG_0001.JPG  18-05-2026  14:22:11  DateTimeOriginal  +03:00  iPhone 16 Pro  5 B res? 14:22:11",
                plain_text,
            )
            self.assertIn(
                "⚠️ clip.mov   19-05-2026  09:01:02  MediaCreateDate",
                plain_text,
            )
            self.assertIn("⚠️ Issues", plain_text)
            self.assertIn("Timezone mismatch/missing       1", plain_text)
            self.assertIn("Timestamp not DateTimeOriginal  1", plain_text)
            self.assertIn("Unknown device                  0", plain_text)
            self.assertGreater(
                plain_text.index("Issues"),
                plain_text.index("clip.mov"),
            )

    def test_prints_zero_count_for_empty_folder(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = run_folder_audit(root, _settings(root))

            self.assertEqual(exit_code, 0)
            plain_text = _strip_colors(output.getvalue())
            self.assertIn("Files  0", plain_text)
            self.assertIn("Timestamp priority", plain_text)
            self.assertNotIn("Helsinki 2025:", plain_text)
            self.assertNotIn("Audit Details", plain_text)
            self.assertNotIn("Issues", plain_text)

    def test_orders_details_by_date_time_then_filename(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            later = root / "A_later.jpg"
            early_b = root / "B_same_time.jpg"
            early_a = root / "A_same_time.jpg"
            for path in (later, early_b, early_a):
                path.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                later: Metadata(
                    selected_datetime=datetime(2026, 5, 6, 8, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
                early_b: Metadata(
                    selected_datetime=datetime(2026, 5, 5, 8, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
                early_a: Metadata(
                    selected_datetime=datetime(2026, 5, 5, 8, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertLess(text.index("A_same_time.jpg"), text.index("B_same_time.jpg"))
            self.assertLess(text.index("B_same_time.jpg"), text.index("A_later.jpg"))

    def test_prints_helsinki_dst_rules_for_each_file_year(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "IMG_2025.JPG"
            second = root / "IMG_2026.JPG"
            first.write_bytes(b"photo")
            second.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                first: Metadata(
                    selected_datetime=datetime(2025, 7, 3, 10, 30, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset=None,
                ),
                second: Metadata(
                    selected_datetime=datetime(2026, 7, 3, 10, 30, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            plain_text = _strip_colors(text)
            self.assertIn("Rules", plain_text)
            self.assertIn("Timezone baseline  Europe/Helsinki", plain_text)
            self.assertIn("Helsinki 2025: +03:00 from 30-03-2025, +02:00 from 26-10-2025", plain_text)
            self.assertIn("Helsinki 2026: +03:00 from 29-03-2026, +02:00 from 25-10-2026", plain_text)
            self.assertIn("\033[1m\033[36mRules\033[0m", text)

    def test_marks_timezone_red_when_it_does_not_match_helsinki_offset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_2025.JPG"
            photo.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2025, 7, 3, 10, 30, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertIn("\033[31m+02:00\033[0m", output.getvalue())
            self.assertIn("\033[31mIMG_2025.JPG\033[0m", output.getvalue())

    def test_keeps_timezone_plain_when_it_matches_helsinki_offset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_5537.JPG"
            photo.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2025, 12, 20, 16, 48, 24),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertIn(
                "IMG_5537.JPG  20-12-2025  16:48:24  DateTimeOriginal  +02:00  Canon EOS M50",
                _strip_colors(output.getvalue()),
            )
            self.assertNotIn("\033[31m+02:00\033[0m", output.getvalue())
            self.assertNotIn("\033[31mIMG_5537.JPG\033[0m", output.getvalue())

    def test_marks_unknown_device_red(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "mystery.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                    timestamp_field="FileModifyDate",
                    device_name="UnknownDevice",
                    quality="filesystem_fallback",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertIn("\033[31mUnknownDevice\033[0m", output.getvalue())

    def test_marks_taken_from_yellow_when_not_datetime_original(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "fallback.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                    timestamp_field="CreateDate",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            self.assertEqual(exit_code, 0)
            text = output.getvalue()
            self.assertIn("\033[33mCreateDate\033[0m", text)
            self.assertIn("\033[33mfallback.jpg\033[0m", text)
            self.assertNotIn("\033[31mCreateDate\033[0m", text)
            self.assertNotIn("\033[31mfallback.jpg\033[0m", text)

    def test_marks_missing_timezone_red(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "missing-timezone.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertIn("\033[31m(none)\033[0m", output.getvalue())

    def test_attention_summary_counts_each_file_once_and_counts_warning_types(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            clean = root / "clean.jpg"
            messy = root / "messy.jpg"
            missing_timezone = root / "missing-timezone.jpg"
            for path in (clean, messy, missing_timezone):
                path.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                clean: Metadata(
                    selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
                messy: Metadata(
                    selected_datetime=datetime(2026, 5, 5, 12, 0, 0),
                    timestamp_field="CreateDate",
                    device_name="UnknownDevice",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
                missing_timezone: Metadata(
                    selected_datetime=datetime(2026, 5, 5, 12, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            plain_text = _strip_colors(text)
            self.assertIn("Timezone mismatch/missing       2", plain_text)
            self.assertIn("Timestamp not DateTimeOriginal  1", plain_text)
            self.assertIn("Unknown device                  1", plain_text)

    def test_prints_divider_when_file_date_changes(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.jpg"
            second = root / "second.jpg"
            third = root / "third.jpg"
            for path in (first, second, third):
                path.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                first: Metadata(
                    selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
                second: Metadata(
                    selected_datetime=datetime(2026, 1, 5, 13, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
                third: Metadata(
                    selected_datetime=datetime(2026, 1, 6, 12, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.audit_folder.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                redirect_stdout(output),
            ):
                exit_code = run_folder_audit(root, settings)

            self.assertEqual(exit_code, 0)
            lines = _strip_colors(output.getvalue()).splitlines()
            header = next(line for line in lines if line.startswith("Filename"))
            divider_indexes = [
                index
                for index, line in enumerate(lines)
                if set(line) == {"─"} and len(line) == len(header)
            ]
            self.assertGreaterEqual(len(divider_indexes), 1)
            second_index = next(
                index for index, line in enumerate(lines)
                if line.startswith("second.jpg  05-01-2026  13:00:00  DateTimeOriginal  +02:00  iPhone 16 Pro")
            )
            third_index = next(
                index for index, line in enumerate(lines)
                if line.startswith("third.jpg   06-01-2026  12:00:00  DateTimeOriginal  +02:00  iPhone 16 Pro")
            )
            self.assertLess(second_index, divider_indexes[0])
            self.assertLess(divider_indexes[0], third_index)


def _settings(root: Path) -> Settings:
    return Settings(
        destination_folder=root / "destination",
        dry_run=True,
        log_level="INFO",
        exiftool_path="exiftool",
        filename_prefix="",
        hash_length=12,
        allowed_photo_extensions=frozenset({"jpg"}),
        allowed_video_extensions=frozenset({"mov"}),
        ignored_folders=frozenset(),
    )


def _strip_colors(value: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", value)


if __name__ == "__main__":
    unittest.main()
