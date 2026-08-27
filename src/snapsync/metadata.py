# Talk to ExifTool and parse raw metadata.
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

EXIFTOOL_FIELDS = (
    "-DateTimeOriginal",
    "-CreateDate",
    "-CreationDate",
    "-OffsetTime",
    "-OffsetTimeOriginal",
    "-OffsetTimeDigitized",
    "-MediaCreateDate",
    "-TrackCreateDate",
    "-FileModifyDate",
    "-FileCreateDate",
    "-Model",
    "-CameraModelName",
    "-Make",
    "-DeviceManufacturer",
    "-ImageWidth",
    "-ImageHeight",
    "-ExifImageWidth",
    "-ExifImageHeight",
)


@dataclass(frozen=True)
class Metadata:
    selected_datetime: datetime
    timestamp_field: str
    device_name: str
    quality: str
    timezone_offset: str | None = None
    timezone_field: str | None = None
    device_field: str | None = None
    image_width: int | None = None
    image_height: int | None = None


def extract_metadata(path: Path, exiftool_path: str = "exiftool") -> Metadata:
    metadata = _read_exiftool_metadata(path, exiftool_path)
    parsed_metadata = _metadata_from_exiftool(metadata) if metadata else None
    if parsed_metadata:
        return parsed_metadata

    return _filesystem_metadata(path)


def extract_metadata_batch(paths: list[Path], exiftool_path: str = "exiftool") -> dict[Path, Metadata]:
    metadata_items = _read_exiftool_metadata_batch(paths, exiftool_path)
    metadata_by_path: dict[Path, Metadata] = {}

    for item in metadata_items:
        source_file = item.get("SourceFile")
        if not isinstance(source_file, str):
            continue
        parsed_metadata = _metadata_from_exiftool(item)
        if parsed_metadata:
            metadata_by_path[Path(source_file)] = parsed_metadata

    return metadata_by_path


def current_date_fallback() -> Metadata:
    return Metadata(
        selected_datetime=datetime.now(),
        timestamp_field="CurrentDate",
        device_name="UnknownDevice",
        quality="current_date_fallback",
        timezone_offset=None,
    )


def _metadata_from_exiftool(metadata: dict[str, object]) -> Metadata | None:
    for field in TIMESTAMP_FIELDS:
        value = metadata.get(field)
        parsed = _parse_datetime(value)
        if parsed:
            device_name, device_field = _extract_device_name(metadata)
            timezone_offset, timezone_field = _extract_timezone_offset(metadata)
            image_width, image_height = _extract_image_dimensions(metadata)
            return Metadata(
                selected_datetime=parsed,
                timestamp_field=field,
                device_name=device_name,
                quality="metadata" if not field.startswith("File") else "filesystem",
                timezone_offset=timezone_offset,
                timezone_field=timezone_field,
                device_field=device_field,
                image_width=image_width,
                image_height=image_height,
            )
    return None


def _filesystem_metadata(path: Path) -> Metadata:
    stat = path.stat()
    return Metadata(
        selected_datetime=datetime.fromtimestamp(stat.st_mtime),
        timestamp_field="FileModifyDate",
        device_name="UnknownDevice",
        quality="filesystem_fallback",
        timezone_offset=None,
    )


def _read_exiftool_metadata(path: Path, exiftool_path: str) -> dict[str, object] | None:
    data = _run_exiftool([path], exiftool_path)
    if not data:
        return None
    return data[0]


def _read_exiftool_metadata_batch(paths: list[Path], exiftool_path: str) -> list[dict[str, object]]:
    return _run_exiftool(paths, exiftool_path) or []


def _run_exiftool(paths: list[Path], exiftool_path: str) -> list[dict[str, object]] | None:
    if not paths:
        return []

    command = [
        exiftool_path,
        "-json",
        "-api",
        "QuickTimeUTC=1",
        *EXIFTOOL_FIELDS,
        *[str(path) for path in paths],
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return None

    if not data:
        return None
    return data


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


def _extract_device_name(metadata: dict[str, object]) -> tuple[str, str | None]:
    for field in DEVICE_FIELDS:
        value = metadata.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip(), field
    return "UnknownDevice", None


def _extract_timezone_offset(metadata: dict[str, object]) -> tuple[str | None, str | None]:
    for field in ("OffsetTimeOriginal", "OffsetTime", "OffsetTimeDigitized"):
        value = metadata.get(field)
        if isinstance(value, str) and _parse_timezone_offset_minutes(value) is not None:
            return value.strip(), field
    for field in ("CreationDate", "DateTimeOriginal"):
        value = metadata.get(field)
        offset = _extract_datetime_timezone_offset(value)
        if offset:
            return offset, field
    return None, None


def _extract_image_dimensions(metadata: dict[str, object]) -> tuple[int | None, int | None]:
    width = _parse_int(metadata.get("ImageWidth")) or _parse_int(metadata.get("ExifImageWidth"))
    height = _parse_int(metadata.get("ImageHeight")) or _parse_int(metadata.get("ExifImageHeight"))
    return width, height


def _parse_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _extract_datetime_timezone_offset(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        return "+00:00"
    if len(cleaned) >= 6 and cleaned[-6] in {"+", "-"} and cleaned[-3] == ":":
        offset = cleaned[-6:]
        if _parse_timezone_offset_minutes(offset) is not None:
            return offset
    return None


def parse_timezone_offset_minutes(value: str | None) -> int | None:
    return _parse_timezone_offset_minutes(value)


def _parse_timezone_offset_minutes(value: str | None) -> int | None:
    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) != 6 or cleaned[0] not in {"+", "-"} or cleaned[3] != ":":
        return None
    try:
        hours = int(cleaned[1:3])
        minutes = int(cleaned[4:6])
    except ValueError:
        return None
    if hours > 23 or minutes > 59:
        return None
    sign = 1 if cleaned[0] == "+" else -1
    return sign * ((hours * 60) + minutes)
