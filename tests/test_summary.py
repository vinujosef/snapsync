from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import os
from unittest.mock import patch
import unittest

from snapsync.summary import RunSummary


class SummaryTests(unittest.TestCase):
    def test_rename_summary_aligns_counts_and_lists_details_under_their_rows(self):
        summary = RunSummary(
            action_label="rename", source_files_found=120, media_files_processed=118,
            copied_files=95, already_named=21, unknown_files=2, errors=2,
            identical_groups=3, labelled_files=["old.jpg → new_copy1.jpg"],
            already_labelled_files=["existing_copy1.jpg"],
            skipped_files=["notes.txt — unsupported file type"],
            error_files=["bad.jpg — permission denied"],
        )
        with redirect_stdout(StringIO()) as output:
            summary.print()
        text = _strip_colors(output.getvalue())
        for heading in ("1️⃣  Scanned", "2️⃣  Results", "3️⃣  Duplicate Details", "4️⃣  Filename Conflict"):
            self.assertIn(heading, text)
        self.assertLess(text.index("Skipped Unknown"), text.index("• notes.txt"))
        self.assertLess(text.index("• notes.txt"), text.index("Errors"))
        self.assertLess(text.index("• bad.jpg"), text.index("3️⃣  Duplicate Details"))
        self.assertIn("• old.jpg → new_copy1.jpg", text)
        self.assertIn("• existing_copy1.jpg", text)
        rows = [line for line in text.splitlines() if line.startswith(("Renamed (", "Already Correctly", "Skipped Unknown", "Errors"))]
        self.assertEqual(len({re.search(r"[0-9]+(?=\s|$)", row).end() for row in rows}), 1)

    def test_summary_table_wraps_file_lists_in_narrow_terminal(self):
        from snapsync.util.console import print_summary_table
        for rich_enabled in (False, True):
            output = StringIO()
            with (
                patch("shutil.get_terminal_size", return_value=os.terminal_size((80, 24))),
                redirect_stdout(output),
            ):
                if rich_enabled:
                    print_summary_table([("2️⃣  Results", "", [("Errors", 2, "• first.jpg — cannot read file\n• second.jpg — permission denied")])])
                else:
                    with patch("snapsync.util.console._rich_enabled", return_value=False):
                        print_summary_table([("2️⃣  Results", "", [("Errors", 2, "• first.jpg — cannot read file\n• second.jpg — permission denied")])])
            lines = _strip_colors(output.getvalue()).splitlines()
            self.assertTrue(all(len(line) <= 80 for line in lines))
            self.assertIn("first.jpg", output.getvalue())
            self.assertIn("second.jpg", output.getvalue())

    def test_copy_summary_lists_written_folders_by_media_type(self):
        summary = RunSummary(copied_files=3)
        summary.record_output_folder(
            "photo",
            Path("/vault/2026/12 - December/photo/one.jpg"),
        )
        summary.record_output_folder(
            "photo",
            Path("/vault/2026/01 - January/photo/two.jpg"),
        )
        summary.record_output_folder(
            "video",
            Path("/vault/2026/12 - December/video/clip.mov"),
        )
        output = StringIO()

        with redirect_stdout(output):
            summary.print()

        text = _strip_colors(output.getvalue())
        self.assertIn("3 files written to:", text)
        self.assertIn("(📸 photo)", text)
        self.assertIn("/vault/2026/01 - January/photo/", text)
        self.assertIn("/vault/2026/12 - December/photo/", text)
        self.assertIn("(🎞️ video)", text)
        self.assertIn("/vault/2026/12 - December/video/", text)

    def test_dry_run_summary_lists_folders_as_would_be_written(self):
        summary = RunSummary(audit_mode=True, planned_copies=1)
        summary.record_output_folder(
            "photo",
            Path("/vault/2026/12 - December/photo/one.jpg"),
        )
        output = StringIO()

        with redirect_stdout(output):
            summary.print()

        text = _strip_colors(output.getvalue())
        self.assertIn("1 file would be written to:", text)
        self.assertIn("(📸 photo)", text)
        self.assertIn("/vault/2026/12 - December/photo/", text)


def _strip_colors(value: str) -> str:
    return re.sub(r"\033\[[0-9;]*m", "", value)


if __name__ == "__main__":
    unittest.main()
