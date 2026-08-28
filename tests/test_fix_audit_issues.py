from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from config.settings import Settings
from snapsync.actions.fix_audit_issues import run_audit_issue_fix
from snapsync.metadata import Metadata


class FixAuditIssuesTests(unittest.TestCase):
    def test_fixes_timezone_offsets_after_confirmation(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_2026.JPG"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 4, 19, 10, 38, 13),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["1", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=Metadata(
                        selected_datetime=datetime(2026, 4, 19, 10, 38, 13),
                        timestamp_field="DateTimeOriginal",
                        device_name="Canon EOS M50",
                        quality="metadata",
                        timezone_offset="+03:00",
                    ),
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-OffsetTimeOriginal=+03:00",
                    "-OffsetTime=+03:00",
                    "-OffsetTimeDigitized=+03:00",
                    str(photo),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            text = output.getvalue()
            self.assertIn("snapsync > Fix audit issues", text)
            self.assertIn("| 1      | Fix timezone mismatch or missing offset | 1 file", text)
            self.assertIn("i.\033[0m Review timezone rules and preview:", text)
            self.assertIn("Rules:", text)
            self.assertIn("Timezone baseline: Europe/Helsinki", text)
            self.assertIn("Helsinki 2026: +03:00 from 29-03-2026, +02:00 from 25-10-2026", text)
            self.assertIn(
                "Timestamp priority: DateTimeOriginal > CreateDate > MediaCreateDate > TrackCreateDate > FileModifyDate > FileCreateDate",
                text,
            )
            self.assertIn(
                "| IMG_2026.JPG | 19-04-2026 | 10:38:13 | Canon EOS M50 | \033[31m+02:00\033[0m         | \033[32m+03:00\033[0m     | update offset |",
                text,
            )
            self.assertIn("ii.\033[0m Type yes to write timezone metadata:", text)
            self.assertIn("Updated IMG_2026.JPG: +02:00 -> +03:00", text)

    def test_fixes_missing_video_timezone_with_creation_date_and_verifies_readback(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "clip.mp4"
            video.write_bytes(b"video")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                video: Metadata(
                    selected_datetime=datetime(2026, 5, 17, 12, 15, 45),
                    timestamp_field="CreateDate",
                    device_name="UnknownDevice",
                    quality="metadata",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["1", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    side_effect=[
                        metadata_by_path[video],
                        Metadata(
                            selected_datetime=datetime(2026, 5, 17, 12, 15, 45),
                            timestamp_field="CreateDate",
                            device_name="UnknownDevice",
                            quality="metadata",
                            timezone_offset="+03:00",
                            timezone_field="CreationDate",
                        ),
                    ],
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-OffsetTimeOriginal=+03:00",
                    "-OffsetTime=+03:00",
                    "-OffsetTimeDigitized=+03:00",
                    "-Keys:CreationDate=2026:05:17 12:15:45+03:00",
                    str(video),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Updated clip.mp4: (none) -> +03:00", output.getvalue())

    def test_reports_error_when_timezone_write_does_not_read_back(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_2026.JPG"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 4, 19, 10, 38, 13),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset="+02:00",
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["1", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run"),
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=metadata_by_path[photo],
                ),
                patch("snapsync.actions.fix_audit_issues_prompts.logger.error") as error,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 1)
            self.assertNotIn("Updated IMG_2026.JPG", output.getvalue())
            error.assert_called_once()

    def test_timezone_fix_respects_dry_run(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "IMG_2026.JPG"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {
                photo: Metadata(
                    selected_datetime=datetime(2026, 4, 19, 10, 38, 13),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS M50",
                    quality="metadata",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["1", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_not_called()
            self.assertIn("DRY RUN: no metadata will be written.", output.getvalue())
            self.assertIn("Would update IMG_2026.JPG: (none) -> +03:00", output.getvalue())

    def test_timezone_fix_preview_orders_by_date_time_then_filename(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            later = root / "A_later.jpg"
            early_b = root / "B_same_time.jpg"
            early_a = root / "A_same_time.jpg"
            for path in (later, early_b, early_a):
                path.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {
                later: _metadata_with_timezone_issue(datetime(2026, 5, 6, 8, 0, 0)),
                early_b: _metadata_with_timezone_issue(datetime(2026, 5, 5, 8, 0, 0)),
                early_a: _metadata_with_timezone_issue(datetime(2026, 5, 5, 8, 0, 0)),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["1", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            run.assert_not_called()
            self.assertLess(text.index("A_same_time.jpg"), text.index("B_same_time.jpg"))
            self.assertLess(text.index("B_same_time.jpg"), text.index("A_later.jpg"))
            self.assertIn("Fingerprint", text)

    def test_timezone_fix_preview_groups_files_by_date(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.jpg"
            second = root / "second.jpg"
            third = root / "third.jpg"
            for path in (first, second, third):
                path.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {
                first: _metadata_with_timezone_issue(datetime(2026, 5, 5, 12, 0, 0)),
                second: _metadata_with_timezone_issue(datetime(2026, 5, 5, 13, 0, 0)),
                third: _metadata_with_timezone_issue(datetime(2026, 5, 6, 12, 0, 0)),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["1", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run"),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            lines = output.getvalue().splitlines()
            header_index = next(index for index, line in enumerate(lines) if line.startswith("| Filename"))
            first_index = next(index for index, line in enumerate(lines) if line.startswith("| first.jpg"))
            second_index = next(index for index, line in enumerate(lines) if line.startswith("| second.jpg"))
            third_index = next(index for index, line in enumerate(lines) if line.startswith("| third.jpg"))
            divider_indexes = [
                index
                for index, line in enumerate(lines)
                if set(line) == {"-"} and len(line) == len(lines[header_index])
            ]
            preview_dividers = [index for index in divider_indexes if second_index < index < third_index]
            self.assertEqual(len(preview_dividers), 1)
            self.assertLess(first_index, second_index)

    def test_fixes_unknown_devices_per_file_and_exits(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.jpg"
            second = root / "second.jpg"
            first.write_bytes(b"photo")
            second.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                first: _unknown_device_metadata(),
                second: _unknown_device_metadata(),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["2", "b", "Canon EOS M50", ""]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-Model=Canon EOS M50",
                    str(first),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            text = output.getvalue()
            self.assertIn("i.\033[0m Review file:", text)
            self.assertIn("| File      | Date       | Time     | Taken From       | Offset | Current Device |", text)
            self.assertIn("| first.jpg | 05-01-2026 | 12:00:00 | DateTimeOriginal | +02:00 | UnknownDevice  |", text)
            self.assertIn("ii.\033[0m Choose device value:", text)
            self.assertIn("iii.\033[0m Device name:", text)
            self.assertIn("Set Model first.jpg: Canon EOS M50", text)
            self.assertIn("Skipped second.jpg", text)
            self.assertNotIn("Timezone Offset Fix Preview", text)

    def test_unknown_device_fix_orders_files_by_date_time_then_filename(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            later = root / "A_later.jpg"
            early_b = root / "B_same_time.jpg"
            early_a = root / "A_same_time.jpg"
            for path in (later, early_b, early_a):
                path.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {
                later: _unknown_device_metadata_at(datetime(2026, 5, 6, 8, 0, 0)),
                early_b: _unknown_device_metadata_at(datetime(2026, 5, 5, 8, 0, 0)),
                early_a: _unknown_device_metadata_at(datetime(2026, 5, 5, 8, 0, 0)),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["2", "", "", ""]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            run.assert_not_called()
            self.assertLess(text.index("A_same_time.jpg"), text.index("B_same_time.jpg"))
            self.assertLess(text.index("B_same_time.jpg"), text.index("A_later.jpg"))

    def test_unknown_device_fix_can_use_whatsapp_shortcut(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "shared.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                photo: _unknown_device_metadata(),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["2", "a"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-Model=WhatsApp",
                    str(photo),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            text = output.getvalue()
            self.assertIn("i.\033[0m Review file:", text)
            self.assertIn("ii.\033[0m Choose device value:", text)
            self.assertIn("a. WhatsApp", text)
            self.assertIn("b. Type the device name", text)
            self.assertIn("Set Model shared.jpg: WhatsApp", text)

    def test_manual_fix_can_update_one_file_device(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "Leya-Skiing-2.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["3", "Leya-Skiing-2.jpg", "d", "b", "Canon EOS M50", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=Metadata(
                        selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                        timestamp_field="DateTimeOriginal",
                        device_name="Canon EOS M50",
                        quality="metadata",
                        timezone_offset="+02:00",
                    ),
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-Model=Canon EOS M50",
                    str(photo),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            text = output.getvalue()
            self.assertIn("i.\033[0m Enter filename:", text)
            self.assertIn("| File              | Date       | Time     | Taken From       | Offset | Device        |", text)
            self.assertIn("| Leya-Skiing-2.jpg | 05-01-2026 | 12:00:00 | DateTimeOriginal | +02:00 | UnknownDevice |", text)
            self.assertIn("ii.\033[0m Choose what to change:", text)
            self.assertIn("iii.\033[0m Choose device value:", text)
            self.assertIn("iv.\033[0m Device name:", text)
            self.assertIn("v.\033[0m Type yes to write metadata:", text)
            self.assertIn("Set Model Leya-Skiing-2.jpg: Canon EOS M50", text)

    def test_manual_fix_can_update_one_file_offset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "Leya-Skiing-2.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["3", "Leya-Skiing-2.jpg", "c", "+03:00", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=Metadata(
                        selected_datetime=datetime(2026, 1, 5, 12, 0, 0),
                        timestamp_field="DateTimeOriginal",
                        device_name="UnknownDevice",
                        quality="metadata",
                        timezone_offset="+03:00",
                    ),
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once()
            self.assertIn("Updated Leya-Skiing-2.jpg: offset -> +03:00", output.getvalue())

    def test_manual_fix_can_update_one_file_date(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "Leya-Skiing-2.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["3", "Leya-Skiing-2.jpg", "a", "06-02-2026", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=Metadata(
                        selected_datetime=datetime(2026, 2, 6, 12, 0, 0),
                        timestamp_field="DateTimeOriginal",
                        device_name="UnknownDevice",
                        quality="metadata",
                        timezone_offset="+02:00",
                    ),
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-DateTimeOriginal=2026:02:06 12:00:00",
                    "-CreateDate=2026:02:06 12:00:00",
                    "-OffsetTimeOriginal=+02:00",
                    "-OffsetTime=+02:00",
                    "-OffsetTimeDigitized=+02:00",
                    str(photo),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn(
                "Will change Leya-Skiing-2.jpg: 05-01-2026 12:00:00 -> 06-02-2026 12:00:00",
                output.getvalue(),
            )
            self.assertIn("Updated Leya-Skiing-2.jpg: date/time", output.getvalue())

    def test_manual_video_date_fix_preserves_existing_offset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "0871a475-a7c9-4090-bc6e-68c47ca1ff4f.MP4"
            video.write_bytes(b"video")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                video: Metadata(
                    selected_datetime=datetime(2026, 5, 17, 12, 15, 45),
                    timestamp_field="CreateDate",
                    device_name="UnknownDevice",
                    quality="metadata",
                    timezone_offset="+03:00",
                    timezone_field="CreationDate",
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch(
                    "builtins.input",
                    side_effect=["3", "0871a475-a7c9-4090-bc6e-68c47ca1ff4f.MP4", "a", "02-05-2026", "yes"],
                ),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=Metadata(
                        selected_datetime=datetime(2026, 5, 2, 12, 15, 45),
                        timestamp_field="DateTimeOriginal",
                        device_name="UnknownDevice",
                        quality="metadata",
                        timezone_offset="+03:00",
                        timezone_field="OffsetTimeOriginal",
                    ),
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-DateTimeOriginal=2026:05:02 12:15:45",
                    "-CreateDate=2026:05:02 12:15:45",
                    "-OffsetTimeOriginal=+03:00",
                    "-OffsetTime=+03:00",
                    "-OffsetTimeDigitized=+03:00",
                    "-Keys:CreationDate=2026:05:02 12:15:45+03:00",
                    str(video),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Updated 0871a475-a7c9-4090-bc6e-68c47ca1ff4f.MP4: date/time", output.getvalue())

    def test_manual_video_date_fix_does_not_create_local_machine_offset_when_missing(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            video = root / "1911202200134_encoded.mp4"
            video.write_bytes(b"video")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                video: Metadata(
                    selected_datetime=datetime(2022, 11, 21, 2, 0, 34),
                    timestamp_field="FileModifyDate",
                    device_name="UnknownDevice",
                    quality="metadata",
                    timezone_offset=None,
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["3", "1911202200134_encoded.mp4", "a", "19-11-2022", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=Metadata(
                        selected_datetime=datetime(2022, 11, 19, 2, 0, 34),
                        timestamp_field="DateTimeOriginal",
                        device_name="UnknownDevice",
                        quality="metadata",
                        timezone_offset=None,
                    ),
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_called_once_with(
                [
                    "exiftool",
                    "-overwrite_original",
                    "-P",
                    "-DateTimeOriginal=2022:11:19 02:00:34",
                    "-CreateDate=2022:11:19 02:00:34",
                    str(video),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Updated 1911202200134_encoded.mp4: date/time", output.getvalue())

    def test_manual_fix_can_update_one_file_time(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "Leya-Skiing-2.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["3", "Leya-Skiing-2.jpg", "b", "13:14:15", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run"),
                patch(
                    "snapsync.actions.fix_audit_issues_writer.extract_metadata",
                    return_value=Metadata(
                        selected_datetime=datetime(2026, 1, 5, 13, 14, 15),
                        timestamp_field="DateTimeOriginal",
                        device_name="UnknownDevice",
                        quality="metadata",
                        timezone_offset="+02:00",
                    ),
                ),
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertIn("Updated Leya-Skiing-2.jpg: date/time", output.getvalue())

    def test_manual_fix_handles_duplicate_filenames_by_prompting_for_one_match(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_folder = root / "one"
            second_folder = root / "two"
            first_folder.mkdir()
            second_folder.mkdir()
            first = first_folder / "same.jpg"
            second = second_folder / "same.jpg"
            first.write_bytes(b"photo")
            second.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {
                first: _unknown_device_metadata(),
                second: _unknown_device_metadata(),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["3", "same.jpg", "2", "d", "a", "yes"]),
                patch("snapsync.actions.fix_audit_issues_writer.subprocess.run") as run,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            run.assert_not_called()
            text = output.getvalue()
            self.assertIn("Multiple files found:", text)
            self.assertIn("| 2      | two/same.jpg |", text)
            self.assertIn("Would set Model same.jpg: WhatsApp", text)

    def test_manual_fix_rejects_invalid_date(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "Leya-Skiing-2.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["3", "Leya-Skiing-2.jpg", "a", "not-a-date"]),
                patch("snapsync.actions.fix_audit_issues_prompts.logger.error") as error,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 1)
            error.assert_called_once()

    def test_bulk_date_fix_previews_change_and_highlights_final_date(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "wrong-day.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["4", "1", "26-08-2026", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_datetime") as write_datetime,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            write_datetime.assert_not_called()
            self.assertIn("DRY RUN: no metadata will be written.", text)
            self.assertIn("DRY RUN: preview tables show planned values only.", text)
            self.assertIn("DRY RUN: no metadata was written.", text)
            self.assertIn("| 4      | Repair all scanned files", text)
            self.assertIn("snapsync > Fix audit issues > Repair all scanned files > Change date", text)
            self.assertIn("| Filename      | Old Date   | New Date   |", text)
            self.assertIn("| wrong-day.jpg | \033[31m05-01-2026\033[0m | \033[32m26-08-2026\033[0m |", text)
            self.assertIn("| wrong-day.jpg | \033[33m26-08-2026\033[0m | 12:00:00 | DateTimeOriginal | +02:00 | UnknownDevice |", text)

    def test_bulk_time_fix_previews_change_and_highlights_final_time(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "wrong-time.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["4", "2", "08:09:10", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_datetime") as write_datetime,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            write_datetime.assert_not_called()
            self.assertIn("DRY RUN: no metadata will be written.", text)
            self.assertIn("DRY RUN: no metadata was written.", text)
            self.assertIn("| Filename       | Old Time | New Time |", text)
            self.assertIn("| wrong-time.jpg | \033[31m12:00:00\033[0m | \033[32m08:09:10\033[0m |", text)
            self.assertIn("| wrong-time.jpg | 05-01-2026 | \033[33m08:09:10\033[0m | DateTimeOriginal | +02:00 | UnknownDevice |", text)

    def test_bulk_timezone_fix_moves_time_and_highlights_time_and_offset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "wrong-offset.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["4", "3", "+05:30", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_datetime") as write_datetime,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            write_datetime.assert_not_called()
            self.assertIn("DRY RUN: no metadata will be written.", text)
            self.assertIn("DRY RUN: no metadata was written.", text)
            self.assertIn("| Filename         | Old Date/Time       | New Date/Time       | Old Offset | New Offset |", text)
            self.assertIn(
                "| wrong-offset.jpg | \033[31m05-01-2026 12:00:00\033[0m | \033[32m05-01-2026 15:30:00\033[0m | \033[31m+02:00\033[0m     | \033[32m+05:30\033[0m     |",
                text,
            )
            self.assertIn(
                "| wrong-offset.jpg | 05-01-2026 | \033[33m15:30:00\033[0m | DateTimeOriginal | \033[33m+05:30\033[0m | UnknownDevice |",
                text,
            )

    def test_bulk_timezone_fix_reads_metadata_back_in_one_batch_after_writes(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.jpg"
            second = root / "second.jpg"
            first.write_bytes(b"photo")
            second.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                first: _unknown_device_metadata(),
                second: _unknown_device_metadata_at(datetime(2026, 1, 5, 12, 1, 0)),
            }
            final_metadata_by_path = {
                path: Metadata(
                    selected_datetime=metadata.selected_datetime.replace(
                        hour=metadata.selected_datetime.hour + 3,
                        minute=metadata.selected_datetime.minute + 30,
                    ),
                    timestamp_field=metadata.timestamp_field,
                    device_name=metadata.device_name,
                    quality=metadata.quality,
                    timezone_offset="+05:30",
                )
                for path, metadata in metadata_by_path.items()
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch(
                    "snapsync.actions.fix_audit_issues_prompts.read_metadata_batch_or_fallback",
                    return_value=final_metadata_by_path,
                ) as readback,
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["4", "3", "+05:30", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_datetime") as write_datetime,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertEqual(write_datetime.call_count, 2)
            write_datetime.assert_any_call(first, datetime(2026, 1, 5, 15, 30, 0), "+05:30", settings)
            write_datetime.assert_any_call(second, datetime(2026, 1, 5, 15, 31, 0), "+05:30", settings)
            readback.assert_called_once_with([first, second], settings)
            self.assertIn("Updated Metadata", output.getvalue())

    def test_batch_date_repair_changes_matching_date_and_device_only(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphone = root / "IMG_7780.heic"
            canon = root / "Canon.jpg"
            iphone.write_bytes(b"photo")
            canon.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {
                iphone: Metadata(
                    selected_datetime=datetime(2026, 7, 26, 9, 41, 37),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+05:30",
                ),
                canon: Metadata(
                    selected_datetime=datetime(2026, 7, 26, 11, 28, 3),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS 700D",
                    quality="metadata",
                    timezone_offset="+05:30",
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["5", "1", "26-07-2026", "26-08-2026", "iPhone", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_datetime") as write_datetime,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            write_datetime.assert_not_called()
            self.assertIn("Batch Date Repair Preview", text)
            self.assertIn(
                "| IMG_7780.heic | \033[31m26-07-2026\033[0m | \033[32m26-08-2026\033[0m | 09:41:37 | +05:30 | iPhone 16 Pro |",
                text,
            )
            self.assertNotIn("Canon.jpg |", text)

    def test_bulk_datetime_timezone_move_shifts_matching_iphone_files_only(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphone = root / "IMG_7780.heic"
            canon = root / "2026-08-26_112803_CanonEOS700D_1ac860b024d9.jpg"
            iphone.write_bytes(b"photo")
            canon.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {
                iphone: Metadata(
                    selected_datetime=datetime(2026, 8, 26, 9, 41, 37),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
                canon: Metadata(
                    selected_datetime=datetime(2026, 8, 26, 11, 28, 3),
                    timestamp_field="DateTimeOriginal",
                    device_name="Canon EOS 700D",
                    quality="metadata",
                    timezone_offset="+05:30",
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["5", "3", "+03:00", "+05:30", "iPhone", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_datetime") as write_datetime,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            write_datetime.assert_not_called()
            self.assertIn("| 5      | Repair matching files", text)
            self.assertIn("Use this option when you need to fix metadata for only some files in this folder.", text)
            self.assertIn("1. Change date", text)
            self.assertIn("3. Change timezone offset", text)
            self.assertIn("snapsync > Fix audit issues > Repair matching files > Change timezone offset", text)
            self.assertIn(
                "| IMG_7780.heic | \033[31m26-08-2026 09:41:37\033[0m | \033[32m26-08-2026 12:11:37\033[0m | \033[31m+03:00\033[0m     | \033[32m+05:30\033[0m     | iPhone 16 Pro |",
                text,
            )
            self.assertNotIn("CanonEOS700D", text)
            self.assertIn(
                "| IMG_7780.heic | \033[33m26-08-2026\033[0m | \033[33m12:11:37\033[0m | DateTimeOriginal | \033[33m+05:30\033[0m | iPhone 16 Pro |",
                text,
            )

    def test_bulk_datetime_timezone_move_writes_shifted_datetime_and_new_offset(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphone = root / "IMG_7780.heic"
            iphone.write_bytes(b"photo")
            settings = _settings(root, dry_run=False)
            output = StringIO()

            metadata_by_path = {
                iphone: Metadata(
                    selected_datetime=datetime(2026, 8, 26, 9, 41, 37),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+03:00",
                ),
            }
            final_metadata_by_path = {
                iphone: Metadata(
                    selected_datetime=datetime(2026, 8, 26, 12, 11, 37),
                    timestamp_field="DateTimeOriginal",
                    device_name="iPhone 16 Pro",
                    quality="metadata",
                    timezone_offset="+05:30",
                ),
            }

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch(
                    "snapsync.actions.fix_audit_issues_prompts.read_metadata_batch_or_fallback",
                    return_value=final_metadata_by_path,
                ) as readback,
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["5", "3", "+03:00", "+05:30", "iPhone", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_datetime") as write_datetime,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 0)
            write_datetime.assert_called_once_with(
                iphone,
                datetime(2026, 8, 26, 12, 11, 37),
                "+05:30",
                settings,
            )
            readback.assert_called_once_with([iphone], settings)
            self.assertIn("Updated Metadata", output.getvalue())

    def test_bulk_device_fix_previews_change_and_highlights_final_device(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            photo = root / "wrong-device.jpg"
            photo.write_bytes(b"photo")
            settings = _settings(root, dry_run=True)
            output = StringIO()

            metadata_by_path = {photo: _unknown_device_metadata()}

            with (
                patch(
                    "snapsync.actions.fix_audit_issues.read_metadata_batch_or_fallback",
                    return_value=metadata_by_path,
                ),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", side_effect=["4", "4", "b", "Canon EOS R50", "yes"]),
                patch("snapsync.actions.fix_audit_issues_prompts.write_device_model") as write_device_model,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            write_device_model.assert_not_called()
            self.assertIn("DRY RUN: no metadata will be written.", text)
            self.assertIn("DRY RUN: no metadata was written.", text)
            self.assertIn("| Filename         | Old Device    | New Device    |", text)
            self.assertIn("| wrong-device.jpg | \033[31mUnknownDevice\033[0m | \033[32mCanon EOS R50\033[0m |", text)
            self.assertIn("| wrong-device.jpg | 05-01-2026 | 12:00:00 | DateTimeOriginal | +02:00 | \033[33mCanon EOS R50\033[0m |", text)


def _unknown_device_metadata() -> Metadata:
    return _unknown_device_metadata_at(datetime(2026, 1, 5, 12, 0, 0))


def _unknown_device_metadata_at(selected_datetime: datetime) -> Metadata:
    return Metadata(
        selected_datetime=selected_datetime,
        timestamp_field="DateTimeOriginal",
        device_name="UnknownDevice",
        quality="metadata",
        timezone_offset="+02:00",
    )


def _metadata_with_timezone_issue(selected_datetime: datetime) -> Metadata:
    return Metadata(
        selected_datetime=selected_datetime,
        timestamp_field="DateTimeOriginal",
        device_name="Canon EOS M50",
        quality="metadata",
        timezone_offset="+02:00",
    )


def _settings(root: Path, *, dry_run: bool) -> Settings:
    return Settings(
        destination_folder=root / "destination",
        dry_run=dry_run,
        log_level="INFO",
        exiftool_path="exiftool",
        filename_prefix="",
        hash_length=12,
        allowed_photo_extensions=frozenset({"jpg", "heic"}),
        allowed_video_extensions=frozenset({"mov", "mp4"}),
        ignored_folders=frozenset(),
    )


if __name__ == "__main__":
    unittest.main()
