from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
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
            self.assertEqual(exit_code, 0)
            self.assertIn("\033[36mInfo:\033[0m", text)
            self.assertIn("\033[36mFiles: 2\033[0m", text)
            self.assertIn("\033[36mLegend:\033[0m", text)
            self.assertIn("\033[36m- red = needs review\033[0m", text)
            self.assertIn("\033[36mRules:\033[0m", text)
            self.assertIn("\033[36mTimezone baseline: Europe/Helsinki\033[0m", text)
            self.assertIn("\033[36mHelsinki 2026: +03:00 from 2026-03-29, +02:00 from 2026-10-25\033[0m", text)
            self.assertIn(
                "\033[36mTimestamp priority: DateTimeOriginal > CreateDate > MediaCreateDate > "
                "TrackCreateDate > FileModifyDate > FileCreateDate\033[0m",
                text,
            )
            self.assertIn("\033[36mDetails:\033[0m", text)
            self.assertIn(
                "| Filename     | Date       | Time     | Taken From       | Offset | Device        |",
                text,
            )
            self.assertIn(
                "| IMG_0001.JPG | 2026-05-18 | 14:22:11 | DateTimeOriginal | +03:00 | iPhone 16 Pro |",
                text,
            )
            self.assertIn(
                "| \033[31mclip.mov\033[0m     | 2026-05-19 | 09:01:02 | \033[31mMediaCreateDate\033[0m  | \033[31m(none)\033[0m | Canon EOS M50 |",
                text,
            )
            self.assertIn("\033[36mIssue(s):\033[0m", text)
            self.assertIn("\033[36mTimezone mismatch/missing: 1\033[0m", text)
            self.assertIn("\033[36mTimestamp not DateTimeOriginal: 1\033[0m", text)
            self.assertIn("\033[36mUnknown device: 0\033[0m", text)
            self.assertGreater(
                text.index("Issue(s):"),
                text.index("| \033[31mclip.mov\033[0m"),
            )

    def test_prints_zero_count_for_empty_folder(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output = StringIO()

            with redirect_stdout(output):
                exit_code = run_folder_audit(root, _settings(root))

            self.assertEqual(exit_code, 0)
            self.assertIn("\033[36mFiles: 0\033[0m", output.getvalue())
            self.assertIn("\033[36mTimestamp priority:", output.getvalue())
            self.assertNotIn("Helsinki 2025:", output.getvalue())
            self.assertNotIn("Details:", output.getvalue())
            self.assertNotIn("Issue(s):", output.getvalue())

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
            self.assertIn("Rules:", plain_text)
            self.assertIn("Timezone baseline: Europe/Helsinki", plain_text)
            self.assertIn("Helsinki 2025: +03:00 from 2025-03-30, +02:00 from 2025-10-26", plain_text)
            self.assertIn("Helsinki 2026: +03:00 from 2026-03-29, +02:00 from 2026-10-25", plain_text)
            self.assertIn("\033[36mRules:\033[0m", text)

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
                "| IMG_5537.JPG | 2025-12-20 | 16:48:24 | DateTimeOriginal | +02:00 | Canon EOS M50 |",
                output.getvalue(),
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

    def test_marks_taken_from_red_when_not_datetime_original(self):
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
            self.assertIn("\033[31mCreateDate\033[0m", output.getvalue())

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
            self.assertIn("\033[36mTimezone mismatch/missing: 2\033[0m", text)
            self.assertIn("\033[36mTimestamp not DateTimeOriginal: 1\033[0m", text)
            self.assertIn("\033[36mUnknown device: 1\033[0m", text)

    def test_prints_divider_after_every_50_file_rows(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = [root / f"IMG_{index:04d}.JPG" for index in range(51)]
            for path in paths:
                path.write_bytes(b"photo")
            settings = _settings(root)
            output = StringIO()

            metadata_by_path = {
                path: Metadata(
                    selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+02:00",
                )
                for path in paths
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
            lines = output.getvalue().splitlines()
            header = next(line for line in lines if line.startswith("| Filename"))
            divider = next(line for line in lines if set(line) == {"-"} and len(line) > 32)
            self.assertEqual(len(divider), len(header))


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
    for color in (
        "\033[0m",
        "\033[31m",
        "\033[36m",
    ):
        value = value.replace(color, "")
    return value


if __name__ == "__main__":
    unittest.main()
