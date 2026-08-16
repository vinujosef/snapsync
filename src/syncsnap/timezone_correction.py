# Infer and apply opt-in camera timezone corrections.
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config.settings import Settings
from syncsnap.metadata import Metadata, parse_timezone_offset_minutes


@dataclass(frozen=True)
class TimezoneCorrectionPlan:
    iphone_offset: str
    iphone_offset_minutes: int
    canon_home_timezone: str
    canon_shift_minutes: int
    canon_files: tuple[Path, ...]


def build_timezone_correction_plan(
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> TimezoneCorrectionPlan | None:
    if not settings.infer_timezone_from_iphone:
        return None

    iphone_offsets = [
        metadata.timezone_offset
        for metadata in metadata_by_path.values()
        if _is_iphone(metadata) and metadata.timezone_offset
    ]
    if not iphone_offsets:
        return None

    offset_counts = Counter(iphone_offsets)
    if len(offset_counts) != 1:
        return None

    iphone_offset = iphone_offsets[0]
    iphone_offset_minutes = parse_timezone_offset_minutes(iphone_offset)
    if iphone_offset_minutes is None:
        return None

    canon_files = tuple(
        path
        for path, metadata in metadata_by_path.items()
        if _is_canon(metadata) and metadata.timezone_offset is None
    )
    if not canon_files:
        return None

    sample_datetime = metadata_by_path[canon_files[0]].selected_datetime
    home_offset_minutes = _timezone_offset_at(settings.canon_home_timezone, sample_datetime)
    if home_offset_minutes is None:
        return None

    canon_shift_minutes = iphone_offset_minutes - home_offset_minutes
    if canon_shift_minutes == 0:
        return None

    return TimezoneCorrectionPlan(
        iphone_offset=iphone_offset,
        iphone_offset_minutes=iphone_offset_minutes,
        canon_home_timezone=settings.canon_home_timezone,
        canon_shift_minutes=canon_shift_minutes,
        canon_files=canon_files,
    )


def apply_timezone_correction(metadata: Metadata, plan: TimezoneCorrectionPlan | None) -> datetime:
    if plan is None or not _is_canon(metadata) or metadata.timezone_offset is not None:
        return metadata.selected_datetime

    try:
        home_zone = ZoneInfo(plan.canon_home_timezone)
    except ZoneInfoNotFoundError:
        return metadata.selected_datetime

    destination_zone = timezone(timedelta(minutes=plan.iphone_offset_minutes))
    return (
        metadata.selected_datetime.replace(tzinfo=home_zone)
        .astimezone(destination_zone)
        .replace(tzinfo=None)
    )


def describe_shift(minutes: int) -> str:
    sign = "+" if minutes > 0 else "-"
    absolute = abs(minutes)
    hours, remainder = divmod(absolute, 60)
    if remainder:
        return f"{sign}{hours}h {remainder}m"
    return f"{sign}{hours}h"


def _is_iphone(metadata: Metadata) -> bool:
    return "iphone" in metadata.device_name.lower()


def _is_canon(metadata: Metadata) -> bool:
    return "canon" in metadata.device_name.lower()


def _timezone_offset_at(timezone_name: str, selected_datetime: datetime) -> int | None:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None

    offset = selected_datetime.replace(tzinfo=zone).utcoffset()
    if offset is None:
        return None
    return int(offset.total_seconds() // 60)
