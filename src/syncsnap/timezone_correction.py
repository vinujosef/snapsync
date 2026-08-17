# Infer and apply opt-in camera timezone corrections.
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
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
    iphone_offsets: tuple[tuple[str, int], ...] = ()
    force_canon_home_timezone: bool = False


@dataclass(frozen=True)
class TimezoneCorrectionDiagnostics:
    infer_enabled: bool
    iphone_offsets: tuple[tuple[str, int], ...]
    iphone_files_with_offset: int
    canon_files_without_offset: int
    canon_files_with_offset: int
    canon_files_needing_correction: int
    reason: str


def build_timezone_correction_plan(
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
    *,
    iphone_offset: str | None = None,
    force_canon_home_timezone: bool = False,
) -> TimezoneCorrectionPlan | None:
    if not settings.infer_timezone_from_iphone:
        return None

    iphone_offsets = _sample_iphone_offsets(metadata_by_path)
    if not iphone_offsets:
        return None

    offset_counts = Counter(iphone_offsets)
    if iphone_offset is None and len(offset_counts) != 1:
        return None

    if iphone_offset is None:
        iphone_offset = iphone_offsets[0]
    iphone_offset_minutes = parse_timezone_offset_minutes(iphone_offset)
    if iphone_offset_minutes is None:
        return None

    canon_files = _canon_files_needing_correction(
        metadata_by_path,
        settings,
        iphone_offset_minutes,
        force_canon_home_timezone=force_canon_home_timezone,
    )
    if not canon_files:
        return None

    first_canon_metadata = metadata_by_path[canon_files[0]]
    first_canon_offset = _canon_effective_offset_minutes(
        first_canon_metadata,
        settings,
        force_canon_home_timezone=force_canon_home_timezone,
    )
    if first_canon_offset is None:
        return None
    canon_shift_minutes = iphone_offset_minutes - first_canon_offset

    return TimezoneCorrectionPlan(
        iphone_offset=iphone_offset,
        iphone_offset_minutes=iphone_offset_minutes,
        canon_home_timezone=settings.canon_home_timezone,
        canon_shift_minutes=canon_shift_minutes,
        canon_files=canon_files,
        iphone_offsets=tuple(sorted(offset_counts.items())),
        force_canon_home_timezone=force_canon_home_timezone,
    )


def diagnose_timezone_correction(
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
    *,
    force_canon_home_timezone: bool = False,
) -> TimezoneCorrectionDiagnostics:
    iphone_offsets = _sample_iphone_offsets(metadata_by_path)
    offset_counts = Counter(iphone_offsets)
    canon_files_without_offset = sum(
        1
        for metadata in metadata_by_path.values()
        if _is_canon(metadata) and metadata.timezone_offset is None
    )
    canon_files_with_offset = sum(
        1
        for metadata in metadata_by_path.values()
        if _is_canon(metadata) and metadata.timezone_offset is not None
    )
    iphone_offset = iphone_offsets[0] if iphone_offsets else None
    iphone_offset_minutes = parse_timezone_offset_minutes(iphone_offset)
    canon_files_needing_correction = (
        len(
            _canon_files_needing_correction(
                metadata_by_path,
                settings,
                iphone_offset_minutes,
                force_canon_home_timezone=force_canon_home_timezone,
            )
        )
        if iphone_offset_minutes is not None
        else 0
    )

    reason = "Correction can be inferred"
    if not settings.infer_timezone_from_iphone:
        reason = "INFER_TIMEZONE_FROM_IPHONE is disabled"
    elif not iphone_offsets:
        reason = "No iPhone timezone offsets were found"
    elif len(offset_counts) != 1:
        reason = "Multiple iPhone timezone offsets were found"
    elif iphone_offset_minutes is None:
        reason = f"iPhone timezone offset is invalid: {iphone_offset}"
    elif canon_files_without_offset and not _canon_home_timezone_is_valid(metadata_by_path, settings):
        reason = f"Canon home timezone is invalid: {settings.canon_home_timezone}"
    elif canon_files_needing_correction == 0:
        reason = "Canon timezone already matches the iPhone offset"
    else:
        reason = "Correction can be inferred"

    return TimezoneCorrectionDiagnostics(
        infer_enabled=settings.infer_timezone_from_iphone,
        iphone_offsets=tuple(sorted(offset_counts.items())),
        iphone_files_with_offset=len(iphone_offsets),
        canon_files_without_offset=canon_files_without_offset,
        canon_files_with_offset=canon_files_with_offset,
        canon_files_needing_correction=canon_files_needing_correction,
        reason=reason,
    )


def apply_timezone_correction(metadata: Metadata, plan: TimezoneCorrectionPlan | None) -> datetime:
    if plan is None or not _is_canon(metadata):
        return metadata.selected_datetime

    source_offset_minutes = None
    if not plan.force_canon_home_timezone:
        source_offset_minutes = parse_timezone_offset_minutes(metadata.timezone_offset)
    if source_offset_minutes is None:
        source_offset_minutes = _timezone_offset_at(plan.canon_home_timezone, metadata.selected_datetime)
    if source_offset_minutes is None or source_offset_minutes == plan.iphone_offset_minutes:
        return metadata.selected_datetime

    source_zone = timezone(timedelta(minutes=source_offset_minutes))
    destination_zone = timezone(timedelta(minutes=plan.iphone_offset_minutes))
    return (
        metadata.selected_datetime.replace(tzinfo=source_zone)
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


def _sample_iphone_offsets(metadata_by_path: dict[Path, Metadata], sample_size: int = 5) -> list[str]:
    iphone_items = [
        (path, metadata)
        for path, metadata in metadata_by_path.items()
        if _is_iphone(metadata) and metadata.timezone_offset
    ]
    sampled_items = _stable_sample(iphone_items, sample_size)
    return [metadata.timezone_offset for _, metadata in sampled_items if metadata.timezone_offset]


def _stable_sample(items: list, sample_size: int) -> list:
    if len(items) <= sample_size:
        return items
    ordered_items = sorted(items, key=lambda item: str(item[0]) if isinstance(item, tuple) else str(item))
    seed = "|".join(str(item[0]) if isinstance(item, tuple) else str(item) for item in ordered_items)
    rng = random.Random(seed)
    return rng.sample(ordered_items, sample_size)


def _canon_files_needing_correction(
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
    iphone_offset_minutes: int | None,
    *,
    force_canon_home_timezone: bool = False,
) -> tuple[Path, ...]:
    if iphone_offset_minutes is None:
        return ()

    candidates = []
    for path, metadata in metadata_by_path.items():
        if not _is_canon(metadata):
            continue
        canon_offset_minutes = _canon_effective_offset_minutes(
            metadata,
            settings,
            force_canon_home_timezone=force_canon_home_timezone,
        )
        if canon_offset_minutes is None:
            continue
        if canon_offset_minutes != iphone_offset_minutes:
            candidates.append(path)
    return tuple(candidates)


def _canon_effective_offset_minutes(
    metadata: Metadata,
    settings: Settings,
    *,
    force_canon_home_timezone: bool = False,
) -> int | None:
    if not force_canon_home_timezone:
        metadata_offset = parse_timezone_offset_minutes(metadata.timezone_offset)
        if metadata_offset is not None:
            return metadata_offset
    return _timezone_offset_at(settings.canon_home_timezone, metadata.selected_datetime)


def _canon_home_timezone_is_valid(
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> bool:
    missing_offset_canon = next(
        (
            metadata
            for metadata in metadata_by_path.values()
            if _is_canon(metadata) and metadata.timezone_offset is None
        ),
        None,
    )
    if missing_offset_canon is None:
        return True
    return _timezone_offset_at(settings.canon_home_timezone, missing_offset_canon.selected_datetime) is not None


def _timezone_offset_at(timezone_name: str, selected_datetime: datetime) -> int | None:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None

    offset = selected_datetime.replace(tzinfo=zone).utcoffset()
    if offset is None:
        return None
    return int(offset.total_seconds() // 60)
