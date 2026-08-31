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
                "ImageWidth": 4032,
                "ImageHeight": "3024",
                "FileCreateDate": "2026:05:18 14:22:11+03:00",
            }
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.selected_datetime, datetime(2026, 5, 18, 14, 22, 11))
        self.assertEqual(metadata.timestamp_field, "DateTimeOriginal")
        self.assertEqual(metadata.timezone_offset, "+03:00")
        self.assertEqual(metadata.timezone_field, "OffsetTimeOriginal")
        self.assertEqual(metadata.device_name, "iPhone 16 Pro")
        self.assertEqual(metadata.device_field, "Model")
        self.assertEqual(metadata.image_width, 4032)
        self.assertEqual(metadata.image_height, 3024)
        self.assertEqual(metadata.file_create_datetime, datetime(2026, 5, 18, 14, 22, 11))

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

    def test_extracts_timezone_from_creation_date_when_offset_fields_are_missing(self):
        metadata = _metadata_from_exiftool(
            {
                "CreateDate": "2026:05:17 12:15:45",
                "CreationDate": "2026:05:17 12:15:45+03:00",
            }
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.timestamp_field, "CreateDate")
        self.assertEqual(metadata.timezone_offset, "+03:00")
        self.assertEqual(metadata.timezone_field, "CreationDate")

    def test_prefers_creation_date_offset_over_quicktime_utc_converted_create_date(self):
        metadata = _metadata_from_exiftool(
            {
                "CreateDate": "2026:05:17 12:15:45+05:30",
                "CreationDate": "2026:05:17 12:15:45+03:00",
                "MediaCreateDate": "2026:05:17 12:15:45+05:30",
                "TrackCreateDate": "2026:05:17 12:15:45+05:30",
            }
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.timestamp_field, "CreateDate")
        self.assertEqual(metadata.timezone_offset, "+03:00")
        self.assertEqual(metadata.timezone_field, "CreationDate")

    def test_prefers_creation_date_offset_over_local_datetime_original_offset(self):
        metadata = _metadata_from_exiftool(
            {
                "DateTimeOriginal": "2026:05:02 12:15:45+05:30",
                "CreationDate": "2026:05:02 12:15:45+03:00",
            }
        )

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.timestamp_field, "DateTimeOriginal")
        self.assertEqual(metadata.selected_datetime, datetime(2026, 5, 2, 12, 15, 45))
        self.assertEqual(metadata.timezone_offset, "+03:00")
        self.assertEqual(metadata.timezone_field, "CreationDate")


if __name__ == "__main__":
    unittest.main()
