# Extract capture metadata with ExifTool and safe fallbacks.
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


TIMESTAMP_FIELDS = (
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "FileModifyDate",
    "FileCreateDate",
)

DEVICE_FIELDS = (
    "Model",
    "CameraModelName",
    "Make",
    "DeviceManufacturer",
)


@dataclass(frozen=True)
class Metadata:
    selected_datetime: datetime
    timestamp_field: str
    device_name: str
    quality: str


def extract_metadata(path: Path, exiftool_path: str = "exiftool") -> Metadata:
    metadata = _read_exiftool_metadata(path, exiftool_path)
    if metadata:
        for field in TIMESTAMP_FIELDS:
            value = metadata.get(field)
            parsed = _parse_datetime(value)
            if parsed:
                return Metadata(
                    selected_datetime=parsed,
                    timestamp_field=field,
                    device_name=_extract_device_name(metadata),
                    quality="metadata" if not field.startswith("File") else "filesystem",
                )

    stat = path.stat()
    return Metadata(
        selected_datetime=datetime.fromtimestamp(stat.st_mtime),
        timestamp_field="FileModifyDate",
        device_name="UnknownDevice",
        quality="filesystem_fallback",
    )


def current_date_fallback() -> Metadata:
    return Metadata(
        selected_datetime=datetime.now(),
        timestamp_field="CurrentDate",
        device_name="UnknownDevice",
        quality="current_date_fallback",
    )


def _read_exiftool_metadata(path: Path, exiftool_path: str) -> dict[str, object] | None:
    command = [
        exiftool_path,
        "-json",
        "-api",
        "QuickTimeUTC=1",
        "-DateTimeOriginal",
        "-CreateDate",
        "-MediaCreateDate",
        "-TrackCreateDate",
        "-FileModifyDate",
        "-FileCreateDate",
        "-Model",
        "-CameraModelName",
        "-Make",
        "-DeviceManufacturer",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return None

    if not data:
        return None
    return data[0]


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"

    candidates = [cleaned, _strip_timezone(cleaned)]
    formats = (
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y:%m:%d %H:%M:%S%z",
    )

    for candidate in candidates:
        for date_format in formats:
            try:
                parsed = datetime.strptime(candidate, date_format)
                return parsed.replace(tzinfo=None)
            except ValueError:
                continue
    return None


def _strip_timezone(value: str) -> str:
    if len(value) >= 6 and value[-6] in {"+", "-"} and value[-3] == ":":
        return value[:-6].strip()
    return value


def _extract_device_name(metadata: dict[str, object]) -> str:
    for field in DEVICE_FIELDS:
        value = metadata.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "UnknownDevice"
