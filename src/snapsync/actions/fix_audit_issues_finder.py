# Find files that match the audit issues we know how to repair.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from snapsync.actions.audit_folder import _metadata_warnings, _offset_at
from snapsync.metadata import Metadata


@dataclass(frozen=True)
class TimezoneFix:
    path: Path
    selected_datetime: datetime
    device_name: str
    current_offset: str
    expected_offset: str


@dataclass(frozen=True)
class DeviceFix:
    path: Path
    selected_datetime: datetime
    timestamp_field: str
    timezone_offset: str | None
    device_name: str


def timezone_fixes(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[TimezoneFix]:
    fixes: list[TimezoneFix] = []
    zone = ZoneInfo("Europe/Helsinki")

    for path in candidates:
        metadata = metadata_by_path[path]
        if "timezone" not in _metadata_warnings(metadata):
            continue

        # Store everything the preview needs so the prompt layer stays simple.
        fixes.append(
            TimezoneFix(
                path=path,
                selected_datetime=metadata.selected_datetime,
                device_name=metadata.device_name,
                current_offset=metadata.timezone_offset or "(none)",
                expected_offset=_offset_at(metadata.selected_datetime, zone),
            )
        )

    return sorted(fixes, key=_timezone_fix_sort_key)


def unknown_device_files(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[DeviceFix]:
    fixes: list[DeviceFix] = []

    for path in candidates:
        metadata = metadata_by_path[path]
        if "device" not in _metadata_warnings(metadata):
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
            )
        )

    return sorted(fixes, key=_device_fix_sort_key)


def _timezone_fix_sort_key(fix: TimezoneFix) -> tuple[datetime, str, str]:
    return (fix.selected_datetime, fix.path.name.lower(), str(fix.path).lower())


def _device_fix_sort_key(fix: DeviceFix) -> tuple[datetime, str, str]:
    return (fix.selected_datetime, fix.path.name.lower(), str(fix.path).lower())
