from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from config.settings import Settings
from snapsync.metadata import Metadata
from snapsync.metadata_reader import read_metadata_batch_or_fallback


class MetadataReaderTests(unittest.TestCase):
    def test_batch_reader_uses_batch_result_without_single_file_fallback(self):
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.jpg"
            second = Path(temp_dir) / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            settings = _settings()
            batch_metadata = {
                first: _metadata("iPhone 16 Pro"),
                second: _metadata("Canon EOS M50"),
            }

            with (
                patch("snapsync.metadata_reader.extract_metadata_batch", return_value=batch_metadata),
                patch("snapsync.metadata_reader.read_metadata_or_fallback") as fallback,
            ):
                result = read_metadata_batch_or_fallback([first, second], settings)

            self.assertEqual(result, batch_metadata)
            fallback.assert_not_called()

    def test_batch_reader_falls_back_for_missing_files(self):
        with TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first.jpg"
            second = Path(temp_dir) / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            settings = _settings()
            fallback_metadata = _metadata("UnknownDevice")

            with (
                patch(
                    "snapsync.metadata_reader.extract_metadata_batch",
                    return_value={first: _metadata("iPhone 16 Pro")},
                ),
                patch(
                    "snapsync.metadata_reader.read_metadata_or_fallback",
                    return_value=fallback_metadata,
                ) as fallback,
            ):
                result = read_metadata_batch_or_fallback([first, second], settings)

            self.assertEqual(result[second], fallback_metadata)
            fallback.assert_called_once_with(second, settings)

    def test_batch_reader_chunks_large_file_lists(self):
        paths = [Path(f"/source/{index}.jpg") for index in range(3)]
        settings = _settings()

        def fake_batch(batch, exiftool_path):
            return {path: _metadata(path.name) for path in batch}

        with patch("snapsync.metadata_reader.extract_metadata_batch", side_effect=fake_batch) as batch:
            read_metadata_batch_or_fallback(paths, settings, batch_size=2)

        self.assertEqual(batch.call_count, 2)


def _metadata(device_name: str) -> Metadata:
    return Metadata(
        datetime(2025, 12, 20, 10, 40, 24),
        "DateTimeOriginal",
        device_name,
        "metadata",
        "+01:00",
    )


def _settings() -> Settings:
    return Settings(
        destination_folder=Path("/tmp/destination"),
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
