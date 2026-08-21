from datetime import datetime
import unittest

from snapsync.metadata import _metadata_from_exiftool


class MetadataTests(unittest.TestCase):
    def test_tracks_timezone_and_device_source_fields(self):
        metadata = _metadata_from_exiftool(
            {
                "DateTimeOriginal": "2026:05:18 14:22:11",
                "OffsetTimeOriginal": "+03:00",
                "Model": "iPhone 16 Pro",
            }
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.selected_datetime, datetime(2026, 5, 18, 14, 22, 11))
        self.assertEqual(metadata.timestamp_field, "DateTimeOriginal")
        self.assertEqual(metadata.timezone_offset, "+03:00")
        self.assertEqual(metadata.timezone_field, "OffsetTimeOriginal")
        self.assertEqual(metadata.device_name, "iPhone 16 Pro")
        self.assertEqual(metadata.device_field, "Model")

    def test_tracks_fallback_timezone_and_device_source_fields(self):
        metadata = _metadata_from_exiftool(
            {
                "CreateDate": "2026:05:18 14:22:11",
                "OffsetTime": "+03:00",
                "CameraModelName": "Canon EOS M50",
            }
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.timestamp_field, "CreateDate")
        self.assertEqual(metadata.timezone_field, "OffsetTime")
        self.assertEqual(metadata.device_field, "CameraModelName")


if __name__ == "__main__":
    unittest.main()
