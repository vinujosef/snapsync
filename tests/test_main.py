from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from config.settings import Settings
from snapsync.constants import (
    ACTION_AUDIT_FOLDER,
    ACTION_COPY,
    ACTION_FIX_AUDIT_ISSUES,
    ACTION_RENAME,
)
from snapsync.main import _format_duration, main


class MainTests(unittest.TestCase):
    def test_prints_run_time_after_action_finishes(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = _settings(root)
            output = StringIO()

            with (
                patch("snapsync.main.get_settings", return_value=settings),
                patch("snapsync.main.run_media_copy", return_value=0),
                patch("snapsync.main.perf_counter", side_effect=[100.0, 102.345]),
                redirect_stdout(output),
            ):
                exit_code = main([str(root)])

            self.assertEqual(exit_code, 0)
            self.assertIn("Run time: 2.34s", output.getvalue())

    def test_prints_run_time_for_each_interactive_action(self):
        action_cases = (
            (ACTION_COPY, "run_media_copy"),
            (ACTION_AUDIT_FOLDER, "run_folder_audit"),
            (ACTION_FIX_AUDIT_ISSUES, "run_audit_issue_fix"),
            (ACTION_RENAME, "run_media_rename"),
        )

        for action, runner_name in action_cases:
            with self.subTest(action=action):
                with TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    settings = _settings(root)
                    output = StringIO()

                    with (
                        patch("snapsync.main.Path.cwd", return_value=root),
                        patch("snapsync.main.get_settings", return_value=settings),
                        patch("snapsync.main.choose_interactive_action", return_value=action),
                        patch("snapsync.main.print_action_context"),
                        patch(f"snapsync.main.{runner_name}", return_value=0),
                        patch("snapsync.main.perf_counter", side_effect=[100.0, 101.5]),
                        redirect_stdout(output),
                    ):
                        exit_code = main([])

                    self.assertEqual(exit_code, 0)
                    self.assertIn("Run time: 1.50s", output.getvalue())

    def test_formats_longer_durations(self):
        self.assertEqual(_format_duration(2.345), "2.35s")
        self.assertEqual(_format_duration(62.345), "1m 2.34s")
        self.assertEqual(_format_duration(3662.345), "1h 1m 2.34s")


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


if __name__ == "__main__":
    unittest.main()
