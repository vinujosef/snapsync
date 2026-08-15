import os
from pathlib import Path
from unittest.mock import patch
import unittest

from config.settings import get_settings


class SettingsTests(unittest.TestCase):
    def test_get_settings_reads_destination_folder_and_hash_length(self):
        env = {
            "DESTINATION_FOLDER": "/tmp/destination",
            "DRY_RUN": "true",
            "LOG_LEVEL": "warning",
            "EXIFTOOL_PATH": "python3",
            "HASH_LENGTH": "16",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = get_settings()

        self.assertEqual(settings.destination_folder, Path("/tmp/destination"))
        self.assertTrue(settings.dry_run)
        self.assertEqual(settings.log_level, "WARNING")
        self.assertEqual(settings.hash_length, 16)

    def test_get_settings_accepts_vault_root_legacy_alias(self):
        env = {
            "DESTINATION_FOLDER": "",
            "VAULT_ROOT": "/tmp/legacy",
            "EXIFTOOL_PATH": "python3",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = get_settings()

        self.assertEqual(settings.destination_folder, Path("/tmp/legacy"))

    def test_invalid_hash_length_fails_fast(self):
        env = {
            "DESTINATION_FOLDER": "/tmp/destination",
            "EXIFTOOL_PATH": "python3",
            "HASH_LENGTH": "7",
        }

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError):
                get_settings()


if __name__ == "__main__":
    unittest.main()
