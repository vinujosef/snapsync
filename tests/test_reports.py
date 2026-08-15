from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import unittest

from config.settings import Settings
from syncsnap.reports import DuplicateGroup, write_duplicate_groups_report


class ReportTests(unittest.TestCase):
    def test_write_duplicate_groups_report_creates_csv(self):
        with TemporaryDirectory() as temp_dir:
            settings = Settings(
                destination_folder=Path(temp_dir),
                dry_run=True,
                log_level="INFO",
                exiftool_path="exiftool",
                filename_prefix="",
                hash_length=12,
                allowed_photo_extensions=frozenset({"jpg"}),
                allowed_video_extensions=frozenset({"mov"}),
                ignored_folders=frozenset(),
            )
            groups = {
                "abc123": DuplicateGroup(
                    file_hash="abc123",
                    kept_source=Path("/source/first.jpg"),
                    duplicate_sources=[Path("/source/copy.jpg")],
                    destination_path=Path("/destination/first.jpg"),
                )
            }

            report_path = write_duplicate_groups_report(
                settings,
                groups,
                datetime(2026, 5, 19, 14, 30, 0),
            )

            self.assertEqual(
                report_path,
                Path(temp_dir) / "_syncsnap_reports" / "20260519_143000_duplicate_groups.csv",
            )
            with report_path.open(newline="", encoding="utf-8") as report_file:
                rows = list(csv.DictReader(report_file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["sha256"], "abc123")
            self.assertEqual(rows[0]["kept_source"], "/source/first.jpg")
            self.assertEqual(rows[0]["duplicate_source"], "/source/copy.jpg")


if __name__ == "__main__":
    unittest.main()
