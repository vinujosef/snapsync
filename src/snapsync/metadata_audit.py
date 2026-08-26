# Shared rules for deciding which metadata needs review.
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from snapsync.metadata import Metadata


HELSINKI_TIMEZONE = ZoneInfo("Europe/Helsinki")


def metadata_warnings(metadata: Metadata) -> set[str]:
    warnings: set[str] = set()
    if metadata.timestamp_field != "DateTimeOriginal":
        warnings.add("timestamp")
    if metadata.device_name == "UnknownDevice":
        warnings.add("device")
    if timezone_has_warning(metadata):
        warnings.add("timezone")
    return warnings


def metadata_has_warning(metadata: Metadata) -> bool:
    return bool(metadata_warnings(metadata))


def timezone_has_warning(metadata: Metadata) -> bool:
    if not metadata.timezone_offset:
        return True

    return metadata.timezone_offset != expected_helsinki_offset(metadata.selected_datetime)


def metadata_years(metadata_by_path: dict[Path, Metadata]) -> list[int]:
    return sorted({metadata.selected_datetime.year for metadata in metadata_by_path.values()})


def helsinki_rule_line(year: int) -> str:
    start, end = _dst_transition_dates(year, HELSINKI_TIMEZONE)
    return (
        f"Helsinki {year}: {offset_at(start, HELSINKI_TIMEZONE)} from {start:%Y-%m-%d}, "
        f"{offset_at(end, HELSINKI_TIMEZONE)} from {end:%Y-%m-%d}"
    )


def expected_helsinki_offset(selected_datetime: datetime) -> str:
    return offset_at(selected_datetime, HELSINKI_TIMEZONE)


def offset_at(day: datetime, zone: ZoneInfo) -> str:
    offset = day.replace(tzinfo=zone).utcoffset()
    if offset is None:
        return "(unknown)"

    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _dst_transition_dates(year: int, zone: ZoneInfo) -> tuple[datetime, datetime]:
    # Walk through the year at noon. That is enough to find the days where the
    # timezone offset changes, without caring about the exact transition hour.
    transitions: list[datetime] = []
    previous = datetime(year, 1, 1, 12, tzinfo=zone).utcoffset()
    day = datetime(year, 1, 2, 12)
    end = datetime(year + 1, 1, 1, 12)

    while day < end:
        current = day.replace(tzinfo=zone).utcoffset()
        if current != previous:
            transitions.append(day)
        previous = current
        day += timedelta(days=1)

    if len(transitions) < 2:
        raise ValueError(f"Could not find Helsinki daylight saving dates for {year}")
    return transitions[0], transitions[1]
