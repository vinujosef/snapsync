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
            self.assertIn("| 1      | Timezone mismatch/missing | 1     |", text)
            self.assertIn("i.\033[0m Review timezone rules and preview:", text)
            self.assertIn("Rules:", text)
            self.assertIn("Timezone baseline: Europe/Helsinki", text)
            self.assertIn("Helsinki 2026: +03:00 from 2026-03-29, +02:00 from 2026-10-25", text)
            self.assertIn(
                "Timestamp priority: DateTimeOriginal > CreateDate > MediaCreateDate > TrackCreateDate > FileModifyDate > FileCreateDate",
                text,
            )
            self.assertIn(
                "| IMG_2026.JPG | 2026-04-19 | 10:38:13 | Canon EOS M50 | +02:00         | +03:00     | update offset |",
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
            self.assertIn("| first.jpg | 2026-01-05 | 12:00:00 | DateTimeOriginal | +02:00 | UnknownDevice  |", text)
            self.assertIn("ii.\033[0m Select one of the following:", text)
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
            self.assertIn("ii.\033[0m Select one of the following:", text)
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
            self.assertIn("| Leya-Skiing-2.jpg | 2026-01-05 | 12:00:00 | DateTimeOriginal | +02:00 | UnknownDevice |", text)
            self.assertIn("ii.\033[0m Choose metadata to edit:", text)
            self.assertIn("iii.\033[0m Select one of the following:", text)
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
                patch("builtins.input", side_effect=["3", "Leya-Skiing-2.jpg", "a", "2026-02-06", "yes"]),
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
                    side_effect=["3", "0871a475-a7c9-4090-bc6e-68c47ca1ff4f.MP4", "a", "2026-05-02", "yes"],
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
                patch("builtins.input", side_effect=["3", "1911202200134_encoded.mp4", "a", "2022-11-19", "yes"]),
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
                patch("builtins.input", side_effect=["3", "Leya-Skiing-2.jpg", "a", "02-06-2026"]),
                patch("snapsync.actions.fix_audit_issues_prompts.logger.error") as error,
                redirect_stdout(output),
            ):
                exit_code = run_audit_issue_fix(root, settings)

            self.assertEqual(exit_code, 1)
            error.assert_called_once()


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
        allowed_photo_extensions=frozenset({"jpg"}),
        allowed_video_extensions=frozenset({"mov", "mp4"}),
        ignored_folders=frozenset(),
    )


if __name__ == "__main__":
    unittest.main()
