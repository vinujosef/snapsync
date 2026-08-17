from datetime import datetime
from pathlib import Path
import unittest

from config.settings import Settings
from syncsnap.metadata import Metadata
from syncsnap.timezone_correction import (
    apply_timezone_correction,
    build_timezone_correction_plan,
    diagnose_timezone_correction,
    describe_shift,
)


class TimezoneCorrectionTests(unittest.TestCase):
    def test_infers_iphone_offset_and_shifts_canon_from_helsinki_to_spain(self):
        iphone = Path("/source/iphone.heic")
        canon = Path("/source/canon.jpg")
        settings = _settings()
        metadata_by_path = {
            iphone: Metadata(
                selected_datetime=datetime(2025, 12, 20, 10, 40, 24),
                timestamp_field="DateTimeOriginal",
                device_name="iPhone 16 Pro",
                quality="metadata",
                timezone_offset="+01:00",
            ),
            canon: Metadata(
                selected_datetime=datetime(2025, 12, 20, 11, 40, 24),
                timestamp_field="DateTimeOriginal",
                device_name="Canon EOS M50",
                quality="metadata",
                timezone_offset=None,
            ),
        }

        plan = build_timezone_correction_plan(metadata_by_path, settings)

        self.assertIsNotNone(plan)
        self.assertEqual(plan.iphone_offset, "+01:00")
        self.assertEqual(plan.canon_shift_minutes, -60)
        self.assertEqual(describe_shift(plan.canon_shift_minutes), "-1h")
        self.assertEqual(
            apply_timezone_correction(metadata_by_path[canon], plan),
            datetime(2025, 12, 20, 10, 40, 24),
        )

    def test_skips_when_iphone_offsets_are_mixed(self):
        settings = _settings()
        metadata_by_path = {
            Path("/source/one.heic"): Metadata(
                datetime(2025, 12, 20, 10, 0, 0),
                "DateTimeOriginal",
                "iPhone 16 Pro",
                "metadata",
                "+01:00",
            ),
            Path("/source/two.heic"): Metadata(
                datetime(2025, 12, 20, 11, 0, 0),
                "DateTimeOriginal",
                "iPhone 15 Pro",
                "metadata",
                "+02:00",
            ),
            Path("/source/canon.jpg"): Metadata(
                datetime(2025, 12, 20, 12, 0, 0),
                "DateTimeOriginal",
                "Canon EOS M50",
                "metadata",
                None,
            ),
        }

        self.assertIsNone(build_timezone_correction_plan(metadata_by_path, settings))

    def test_diagnostics_explain_missing_canon_candidates(self):
        settings = _settings()
        metadata_by_path = {
            Path("/source/one.heic"): Metadata(
                datetime(2025, 12, 20, 10, 0, 0),
                "DateTimeOriginal",
                "iPhone 16 Pro",
                "metadata",
                "+01:00",
            ),
            Path("/source/canon.jpg"): Metadata(
                datetime(2025, 12, 20, 12, 0, 0),
                "DateTimeOriginal",
                "Canon EOS M50",
                "metadata",
                "+02:00",
            ),
        }

        diagnostics = diagnose_timezone_correction(metadata_by_path, settings)

        self.assertEqual(diagnostics.iphone_files_with_offset, 1)
        self.assertEqual(diagnostics.canon_files_without_offset, 0)
        self.assertEqual(diagnostics.canon_files_with_offset, 1)
        self.assertEqual(diagnostics.canon_files_needing_correction, 1)
        self.assertEqual(
            diagnostics.reason,
            "Correction can be inferred",
        )

    def test_shifts_canon_when_metadata_offset_differs_from_iphone(self):
        iphone = Path("/source/iphone.heic")
        canon = Path("/source/canon.jpg")
        settings = _settings()
        metadata_by_path = {
            iphone: Metadata(
                datetime(2025, 12, 20, 10, 40, 24),
                "DateTimeOriginal",
                "iPhone 16 Pro",
                "metadata",
                "+01:00",
            ),
            canon: Metadata(
                datetime(2025, 12, 20, 11, 40, 24),
                "DateTimeOriginal",
                "Canon EOS M50",
                "metadata",
                "+02:00",
            ),
        }

        plan = build_timezone_correction_plan(metadata_by_path, settings)

        self.assertIsNotNone(plan)
        self.assertEqual(plan.canon_files, (canon,))
        self.assertEqual(plan.canon_shift_minutes, -60)
        self.assertEqual(
            apply_timezone_correction(metadata_by_path[canon], plan),
            datetime(2025, 12, 20, 10, 40, 24),
        )

    def test_repair_can_force_canon_home_timezone_even_when_canon_metadata_matches_iphone(self):
        iphone = Path("/source/iphone.heic")
        canon = Path("/source/canon.jpg")
        settings = _settings()
        metadata_by_path = {
            iphone: Metadata(
                datetime(2025, 12, 20, 10, 40, 24),
                "DateTimeOriginal",
                "iPhone 16 Pro",
                "metadata",
                "+01:00",
            ),
            canon: Metadata(
                datetime(2025, 12, 20, 11, 40, 24),
                "DateTimeOriginal",
                "Canon EOS M50",
                "metadata",
                "+01:00",
            ),
        }

        plan = build_timezone_correction_plan(
            metadata_by_path,
            settings,
            force_canon_home_timezone=True,
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan.canon_files, (canon,))
        self.assertEqual(plan.canon_shift_minutes, -60)
        self.assertEqual(
            apply_timezone_correction(metadata_by_path[canon], plan),
            datetime(2025, 12, 20, 10, 40, 24),
        )

    def test_copy_still_trusts_matching_canon_timezone_metadata(self):
        settings = _settings()
        metadata_by_path = {
            Path("/source/iphone.heic"): Metadata(
                datetime(2025, 12, 20, 10, 40, 24),
                "DateTimeOriginal",
                "iPhone 16 Pro",
                "metadata",
                "+01:00",
            ),
            Path("/source/canon.jpg"): Metadata(
                datetime(2025, 12, 20, 11, 40, 24),
                "DateTimeOriginal",
                "Canon EOS M50",
                "metadata",
                "+01:00",
            ),
        }

        self.assertIsNone(build_timezone_correction_plan(metadata_by_path, settings))


def _settings() -> Settings:
    return Settings(
        destination_folder=Path("/tmp/destination"),
        dry_run=True,
        log_level="INFO",
        exiftool_path="exiftool",
        filename_prefix="",
        hash_length=12,
        allowed_photo_extensions=frozenset({"jpg", "heic"}),
        allowed_video_extensions=frozenset({"mov"}),
        ignored_folders=frozenset(),
    )


if __name__ == "__main__":
    unittest.main()
