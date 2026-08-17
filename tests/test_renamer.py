from datetime import datetime
from pathlib import Path
import unittest

from snapsync.renamer import generate_filename, sanitize_device_name, sanitize_prefix


class RenamerTests(unittest.TestCase):
    def test_generate_filename_uses_configured_hash_length_and_lowercase_extension(self):
        filename = generate_filename(
            datetime(2026, 5, 18, 14, 22, 11),
            "iPhone 15 Pro",
            "a8f31c9e71d4abcdef",
            Path("IMG_0001.JPG"),
            "Test Prefix!",
            12,
        )

        self.assertEqual(
            filename,
            "TestPrefix_2026-05-18_142211_iPhone15Pro_a8f31c9e71d4.jpg",
        )

    def test_sanitize_device_name_defaults_when_empty(self):
        self.assertEqual(sanitize_device_name(""), "UnknownDevice")

    def test_sanitize_prefix_allows_dashes_and_underscores(self):
        self.assertEqual(sanitize_prefix(" test_prefix-2026! "), "test_prefix-2026")


if __name__ == "__main__":
    unittest.main()
