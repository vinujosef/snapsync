from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import unittest

from config.settings import Settings
from snapsync.actions.repair_timezone import run_timezone_repair
from snapsync.metadata import Metadata


class TimezoneRepairTests(unittest.TestCase):
    def test_repairs_canon_filename_in_current_folder_after_confirmation(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphone = root / "iphone.jpg"
            canon = root / "2025-12-20_114024_CanonEOSM50_oldhash.jpg"
            iphone.write_bytes(b"iphone")
            canon.write_bytes(b"canon")
            settings = _settings(root, dry_run=False)

            def fake_metadata(path, settings):
                if path == iphone:
                    return _iphone_metadata()
                return _canon_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                patch("builtins.print"),
            ):
                exit_code = run_timezone_repair(root, settings)

            expected_hash = hashlib.sha256(b"canon").hexdigest()[:12]
            expected = root / f"2025-12-20_104024_CanonEOSM50_{expected_hash}.jpg"
            self.assertEqual(exit_code, 0)
            self.assertFalse(canon.exists())
            self.assertTrue(expected.exists())

    def test_does_not_rename_without_confirmation(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphone = root / "iphone.jpg"
            canon = root / "2025-12-20_114024_CanonEOSM50_oldhash.jpg"
            iphone.write_bytes(b"iphone")
            canon.write_bytes(b"canon")
            settings = _settings(root, dry_run=False)

            def fake_metadata(path, settings):
                if path == iphone:
                    return _iphone_metadata()
                return _canon_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="no"),
                patch("builtins.print"),
            ):
                exit_code = run_timezone_repair(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertTrue(canon.exists())

    def test_samples_only_five_likely_iphone_files_for_repair_timezone(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphones = [root / f"2025-12-20_10{i:02d}00_iPhone16Pro_hash{i}.jpg" for i in range(10)]
            canon = root / "2025-12-20_114024_CanonEOSM50_oldhash.jpg"
            for path in iphones:
                path.write_bytes(b"iphone")
            canon.write_bytes(b"canon")
            settings = _settings(root, dry_run=True)
            metadata_calls: list[Path] = []

            def fake_metadata(path, settings):
                metadata_calls.append(path)
                if "iphone" in path.name.lower():
                    return _iphone_metadata()
                return _canon_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                patch("builtins.print"),
            ):
                exit_code = run_timezone_repair(root, settings)

            iphone_calls = [path for path in metadata_calls if "iphone" in path.name.lower()]
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(iphone_calls), 5)
            self.assertIn(canon, metadata_calls)

    def test_mixed_sampled_iphone_offsets_require_confirmation_before_repair(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphones = [root / f"2025-12-20_10{i:02d}00_iPhone16Pro_hash{i}.jpg" for i in range(5)]
            canon = root / "2025-12-20_114024_CanonEOSM50_oldhash.jpg"
            for path in iphones:
                path.write_bytes(b"iphone")
            canon.write_bytes(b"canon")
            settings = _settings(root, dry_run=False)

            def fake_metadata(path, settings):
                if "iphone" in path.name.lower():
                    offset = "+02:00" if path == iphones[0] else "+01:00"
                    return _iphone_metadata(offset)
                return _canon_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="no"),
                patch("builtins.print"),
            ):
                exit_code = run_timezone_repair(root, settings)

            self.assertEqual(exit_code, 0)
            self.assertTrue(canon.exists())

    def test_keeps_discovering_canon_files_after_five_iphone_offsets(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphones = [root / f"2025-12-20_10{i:02d}00_iPhone16Pro_hash{i}.jpg" for i in range(8)]
            canon = root / "IMG_1234.JPG"
            for path in iphones:
                path.write_bytes(b"iphone")
            canon.write_bytes(b"canon")
            settings = _settings(root, dry_run=False)
            metadata_calls: list[Path] = []

            def fake_metadata(path, settings):
                metadata_calls.append(path)
                if "iphone" in path.name.lower():
                    return _iphone_metadata()
                return _canon_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                patch("builtins.print"),
            ):
                exit_code = run_timezone_repair(root, settings)

            expected_hash = hashlib.sha256(b"canon").hexdigest()[:12]
            expected = root / f"2025-12-20_104024_CanonEOSM50_{expected_hash}.jpg"
            iphone_calls = [path for path in metadata_calls if "iphone" in path.name.lower()]
            self.assertEqual(exit_code, 0)
            self.assertEqual(len(iphone_calls), 5)
            self.assertIn(canon, metadata_calls)
            self.assertTrue(expected.exists())

    def test_prints_progress_heartbeat_during_large_repair_scan(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for index in range(105):
                (root / f"IMG_{index:04d}.JPG").write_bytes(b"canon")
            settings = _settings(root, dry_run=True)

            def fake_metadata(path, settings):
                return _canon_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("builtins.print") as mocked_print,
            ):
                run_timezone_repair(root, settings)

            printed_lines = [call.args[0] for call in mocked_print.call_args_list if call.args]
            self.assertIn("⏳ Still working...", printed_lines)

    def test_repair_rename_log_uses_filenames_only(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphone = root / "iphone.jpg"
            canon = root / "2025-12-20_114024_CanonEOSM50_oldhash.jpg"
            iphone.write_bytes(b"iphone")
            canon.write_bytes(b"canon")
            settings = _settings(root, dry_run=True)

            def fake_metadata(path, settings):
                if path == iphone:
                    return _iphone_metadata()
                return _canon_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("sys.stdin.isatty", return_value=True),
                patch("builtins.input", return_value="yes"),
                patch("snapsync.actions.repair_timezone.logger.info") as mocked_info,
                patch("builtins.print"),
            ):
                run_timezone_repair(root, settings)

            expected_hash = hashlib.sha256(b"canon").hexdigest()[:12]
            expected_target = f"2025-12-20_104024_CanonEOSM50_{expected_hash}.jpg"
            mocked_info.assert_any_call(
                f"Will rename {canon.name} -> {expected_target}"
            )

    def test_no_canon_files_prints_simple_skip_message(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            iphone = root / "iphone.jpg"
            iphone.write_bytes(b"iphone")
            settings = _settings(root, dry_run=False)

            def fake_metadata(path, settings):
                return _iphone_metadata()

            with (
                patch("snapsync.timezone_sampler.read_metadata_batch_or_fallback", side_effect=_batch_metadata(fake_metadata)),
                patch("snapsync.actions.repair_timezone.logger.info") as mocked_info,
                patch("builtins.print") as mocked_print,
            ):
                exit_code = run_timezone_repair(root, settings)

            self.assertEqual(exit_code, 0)
            mocked_print.assert_any_call(
                "ℹ️  No Canon files available for timezone correction in this folder"
            )
            self.assertFalse(
                any(
                    call.args and call.args[0] == "Timezone scan diagnostics:"
                    for call in mocked_info.call_args_list
                )
            )


def _settings(root: Path, dry_run: bool) -> Settings:
    return Settings(
        destination_folder=root,
        dry_run=dry_run,
        log_level="INFO",
        exiftool_path="exiftool",
        filename_prefix="",
        hash_length=12,
        allowed_photo_extensions=frozenset({"jpg"}),
        allowed_video_extensions=frozenset({"mov"}),
        ignored_folders=frozenset(),
    )


def _iphone_metadata(offset: str = "+01:00") -> Metadata:
    return Metadata(
        datetime(2025, 12, 20, 10, 40, 24),
        "DateTimeOriginal",
        "iPhone 16 Pro",
        "metadata",
        offset,
    )


def _canon_metadata(offset: str | None = None) -> Metadata:
    return Metadata(
        datetime(2025, 12, 20, 11, 40, 24),
        "DateTimeOriginal",
        "Canon EOS M50",
        "metadata",
        offset,
    )


def _batch_metadata(fake_metadata):
    def fake_batch(paths, settings):
        return {path: fake_metadata(path, settings) for path in paths}

    return fake_batch


if __name__ == "__main__":
    unittest.main()
