from unittest.mock import patch
import unittest

from snapsync.cli import choose_interactive_action
from snapsync.constants import ACTION_AUDIT_FOLDER, ACTION_COPY, ACTION_FIX_AUDIT_ISSUES, ACTION_RENAME


class CliTests(unittest.TestCase):
    def test_option_one_selects_folder_audit(self):
        with (
            patch("builtins.input", return_value="1"),
            patch("builtins.print"),
        ):
            self.assertEqual(choose_interactive_action(), ACTION_AUDIT_FOLDER)

    def test_option_two_selects_audit_issue_fix(self):
        with (
            patch("builtins.input", return_value="2"),
            patch("builtins.print"),
        ):
            self.assertEqual(choose_interactive_action(), ACTION_FIX_AUDIT_ISSUES)

    def test_option_three_selects_rename(self):
        with (
            patch("builtins.input", return_value="3"),
            patch("builtins.print"),
        ):
            self.assertEqual(choose_interactive_action(), ACTION_RENAME)

    def test_option_four_selects_copy(self):
        with (
            patch("builtins.input", return_value="4"),
            patch("builtins.print"),
        ):
            self.assertEqual(choose_interactive_action(), ACTION_COPY)


if __name__ == "__main__":
    unittest.main()
