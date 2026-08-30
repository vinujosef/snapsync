# Find files that match the audit issues we know how to repair.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from snapsync.metadata import Metadata
from snapsync.metadata_audit import expected_helsinki_offset, metadata_warnings


@dataclass(frozen=True)
class TimezoneFix:
    path: Path
    selected_datetime: datetime
    timestamp_field: str
    device_name: str
    current_offset: str
    expected_offset: str
    image_width: int | None = None
    image_height: int | None = None


@dataclass(frozen=True)
class DeviceFix:
    path: Path
    selected_datetime: datetime
    timestamp_field: str
    timezone_offset: str | None
    device_name: str
    image_width: int | None = None
    image_height: int | None = None


def timezone_fixes(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[TimezoneFix]:
    fixes: list[TimezoneFix] = []

    for path in candidates:
        metadata = metadata_by_path[path]
        if "timezone" not in metadata_warnings(metadata):
            continue

        # Store everything the preview needs so the prompt layer stays simple.
        fixes.append(
            TimezoneFix(
                path=path,
                selected_datetime=metadata.selected_datetime,
                timestamp_field=metadata.timestamp_field,
                device_name=metadata.device_name,
                current_offset=metadata.timezone_offset or "(none)",
                expected_offset=expected_helsinki_offset(metadata.selected_datetime),
                image_width=metadata.image_width,
                image_height=metadata.image_height,
            )
        )

    return sorted(fixes, key=_timezone_fix_sort_key)


def unknown_device_files(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[DeviceFix]:
    fixes: list[DeviceFix] = []

    for path in candidates:
        metadata = metadata_by_path[path]
        if "device" not in metadata_warnings(metadata):
            continue

        # Keep the displayed metadata beside the path so later code does not
        # have to reach back into the full metadata map.
        fixes.append(
            DeviceFix(
                path=path,
                selected_datetime=metadata.selected_datetime,
                timestamp_field=metadata.timestamp_field,
                timezone_offset=metadata.timezone_offset,
                device_name=metadata.device_name,
                image_width=metadata.image_width,
                image_height=metadata.image_height,
            )
        )

    return sorted(fixes, key=_device_fix_sort_key)


def _timezone_fix_sort_key(fix: TimezoneFix) -> tuple[datetime, str, str]:
    return (fix.selected_datetime, fix.path.name.lower(), str(fix.path).lower())


def _device_fix_sort_key(fix: DeviceFix) -> tuple[datetime, str, str]:
    return (fix.selected_datetime, fix.path.name.lower(), str(fix.path).lower())
