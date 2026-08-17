from contextlib import redirect_stdout
from io import StringIO
import unittest

from syncsnap.summary import RunSummary


class SummaryTests(unittest.TestCase):
    def test_timezone_repair_summary_is_compact(self):
        summary = RunSummary(
            source_files_found=689,
            copied_files=240,
            duplicate_files_skipped=0,
            canon_files_found=240,
            errors=0,
            action_label="rename",
        )
        output = StringIO()

        with redirect_stdout(output):
            summary.print()

        text = _strip_colors(output.getvalue())
        self.assertIn("Timezone Repair Summary", text)
        self.assertIn("Files scanned: 689", text)
        self.assertIn("Canon files found: 240", text)
        self.assertIn("Canon files renamed: 240", text)
        self.assertIn("Skipped: 0", text)
        self.assertIn("Errors: 0", text)
        self.assertNotIn("Duplicate Details", text)


def _strip_colors(value: str) -> str:
    for color in ("\033[0m", "\033[1m", "\033[34m"):
        value = value.replace(color, "")
    return value


if __name__ == "__main__":
    unittest.main()
