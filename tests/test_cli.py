from unittest.mock import patch
import unittest

from snapsync.cli import choose_interactive_action
from snapsync.constants import ACTION_AUDIT_FOLDER


class CliTests(unittest.TestCase):
    def test_option_three_selects_folder_audit(self):
        with (
            patch("builtins.input", return_value="3"),
            patch("builtins.print"),
        ):
            self.assertEqual(choose_interactive_action(), ACTION_AUDIT_FOLDER)


if __name__ == "__main__":
    unittest.main()
