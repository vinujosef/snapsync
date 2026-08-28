from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import re
import unittest

from snapsync.summary import RunSummary


class SummaryTests(unittest.TestCase):
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
