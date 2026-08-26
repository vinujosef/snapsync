# Write the small metadata changes chosen by the audit issue fixer.
from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from config.settings import Settings
from snapsync.metadata import extract_metadata, parse_timezone_offset_minutes


def write_timezone_offset(path: Path, offset: str, settings: Settings) -> None:
    timestamp = ""
    if _is_video(path):
        metadata = extract_metadata(path, settings.exiftool_path)
        timestamp = metadata.selected_datetime.strftime("%Y:%m:%d %H:%M:%S")

    command = [
        settings.exiftool_path,
        "-overwrite_original",
        "-P",
        f"-OffsetTimeOriginal={offset}",
        f"-OffsetTime={offset}",
        f"-OffsetTimeDigitized={offset}",
    ]
    if timestamp:
        # QuickTime files need CreationDate to include the offset in one value.
        command.append(f"-Keys:CreationDate={timestamp}{offset}")
    command.append(str(path))

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def verify_timezone_offset(path: Path, offset: str, settings: Settings) -> None:
    metadata = extract_metadata(path, settings.exiftool_path)
    if metadata.timezone_offset != offset:
        raise ValueError(f"metadata still reports {metadata.timezone_offset or '(none)'}")


def verify_datetime(
    path: Path,
    expected_datetime: datetime,
    expected_offset: str | None,
    settings: Settings,
) -> None:
    metadata = extract_metadata(path, settings.exiftool_path)
    if metadata.selected_datetime != expected_datetime:
        raise ValueError(f"metadata still reports {metadata.selected_datetime:%Y-%m-%d %H:%M:%S}")
    if expected_offset and metadata.timezone_offset != expected_offset:
        raise ValueError(f"metadata offset still reports {metadata.timezone_offset or '(none)'}")


def verify_device_model(path: Path, device_name: str, settings: Settings) -> None:
    metadata = extract_metadata(path, settings.exiftool_path)
    if metadata.device_name != device_name:
        raise ValueError(f"metadata still reports {metadata.device_name}")


def write_datetime(
    path: Path,
    selected_datetime: datetime,
    timezone_offset: str | None,
    settings: Settings,
) -> None:
    timestamp = selected_datetime.strftime("%Y:%m:%d %H:%M:%S")
    command = [
        settings.exiftool_path,
        "-overwrite_original",
        "-P",
        f"-DateTimeOriginal={timestamp}",
        f"-CreateDate={timestamp}",
    ]
    if parse_timezone_offset_minutes(timezone_offset) is not None:
        command.extend(
            [
                f"-OffsetTimeOriginal={timezone_offset}",
                f"-OffsetTime={timezone_offset}",
                f"-OffsetTimeDigitized={timezone_offset}",
            ]
        )
    if _is_video(path) and parse_timezone_offset_minutes(timezone_offset) is not None:
        command.append(f"-Keys:CreationDate={timestamp}{timezone_offset}")
    command.append(str(path))

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def write_device_model(path: Path, device_name: str, settings: Settings) -> None:
    subprocess.run(
        [
            settings.exiftool_path,
            "-overwrite_original",
            "-P",
            f"-Model={device_name}",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _is_video(path: Path) -> bool:
    return path.suffix.lower().lstrip(".") in {"mov", "mp4", "m4v", "avi", "mkv"}
