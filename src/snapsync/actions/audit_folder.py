# Audit capture metadata for files in the current snapsync source folder.
from __future__ import annotations

from collections import Counter
from pathlib import Path

from config.settings import Settings
from snapsync.file_fingerprint import file_fingerprint
from snapsync.metadata import Metadata, TIMESTAMP_FIELDS
from snapsync.metadata_audit import (
    expected_helsinki_offset,
    file_create_date_has_warning,
    helsinki_rule_line,
    metadata_warnings,
    metadata_years,
    timezone_has_warning,
)
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.scanner import scan_source
from snapsync.util import logger
from snapsync.util.console import (
    ICONS,
    cyan,
    format_display_date,
    muted,
    print_key_values,
    print_grouped_table,
    print_section_heading,
    danger,
    warning,
)


def run_folder_audit(source_folder: Path, settings: Settings) -> int:
    try:
        candidates = scan_source(source_folder, settings)
        metadata_by_path = read_metadata_batch_or_fallback(candidates, settings)
    except OSError as exc:
        logger.error(f"Audit failed: {exc}")
        return 1

    print()
    _print_info_section(len(candidates))
    _print_rules_section(metadata_by_path)
    if not candidates:
        return 0

    sorted_candidates = _sort_paths_by_taken_at(candidates, metadata_by_path)
    timezone_reference_offsets = _timezone_reference_offsets(metadata_by_path)
    rows = [_metadata_row(path, metadata_by_path[path], timezone_reference_offsets) for path in sorted_candidates]
    group_values = [format_display_date(metadata_by_path[path].selected_datetime) for path in sorted_candidates]
    print_section_heading("Audit Details", icon=ICONS["audit"])
    _print_table(rows, group_values)
    _print_issues_section(sorted_candidates, metadata_by_path, timezone_reference_offsets)
    return 0


def _sort_paths_by_taken_at(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[Path]:
    return sorted(
        candidates,
        key=lambda path: (
            metadata_by_path[path].selected_datetime,
            path.name.lower(),
            str(path).lower(),
        ),
    )


def _metadata_row(path: Path, metadata: Metadata, timezone_reference_offsets: set[str]) -> list[str]:
    return [
        _file_cell(path, metadata, timezone_reference_offsets),
        _capture_date_cell(metadata),
        _capture_time_cell(metadata),
        _timestamp_field_cell(metadata),
        _file_create_date_cell(metadata),
        _timezone_cell(metadata, timezone_reference_offsets),
        _device_cell(metadata),
        file_fingerprint(path, metadata),
    ]


def _file_cell(path: Path, metadata: Metadata, timezone_reference_offsets: set[str]) -> str:
    warnings = _audit_warnings(metadata, timezone_reference_offsets)
    if warnings & {"timezone", "device", "file_create_date"}:
        return f"{ICONS['warning']} {danger(path.name)}"
    if "timestamp" in warnings:
        return f"{ICONS['warning']} {warning(path.name)}"
    return path.name


def _capture_date_cell(metadata: Metadata) -> str:
    value = format_display_date(metadata.selected_datetime)
    if file_create_date_has_warning(metadata):
        return danger(value)
    return value


def _capture_time_cell(metadata: Metadata) -> str:
    value = metadata.selected_datetime.strftime("%H:%M:%S")
    if file_create_date_has_warning(metadata):
        return danger(value)
    return value


def _timestamp_field_cell(metadata: Metadata) -> str:
    if metadata.timestamp_field != "DateTimeOriginal":
        return warning(metadata.timestamp_field)
    return metadata.timestamp_field


def _file_create_date_cell(metadata: Metadata) -> str:
    if metadata.file_create_datetime is None:
        return "(none)"

    value = metadata.file_create_datetime.strftime("%d-%m-%Y %H:%M:%S")
    if file_create_date_has_warning(metadata):
        return danger(value)
    return value


def _device_cell(metadata: Metadata) -> str:
    if metadata.device_name == "UnknownDevice":
        return danger(metadata.device_name)
    return metadata.device_name


def _timezone_cell(metadata: Metadata, timezone_reference_offsets: set[str]) -> str:
    if _timezone_warning_is_supported(metadata, timezone_reference_offsets):
        return danger(metadata.timezone_offset or "(none)")
    return metadata.timezone_offset or "(none)"


def _audit_warnings(metadata: Metadata, timezone_reference_offsets: set[str]) -> set[str]:
    warnings = metadata_warnings(metadata)
    if not _timezone_warning_is_supported(metadata, timezone_reference_offsets):
        warnings.discard("timezone")
    return warnings


def _timezone_warning_is_supported(metadata: Metadata, timezone_reference_offsets: set[str]) -> bool:
    expected_offset = expected_helsinki_offset(metadata.selected_datetime)
    return expected_offset in timezone_reference_offsets and timezone_has_warning(metadata)


def _timezone_reference_offsets(metadata_by_path: dict[Path, Metadata]) -> set[str]:
    return {
        metadata.timezone_offset
        for metadata in metadata_by_path.values()
        if metadata.timezone_offset in {"+02:00", "+03:00"}
    }


def _print_info_section(file_count: int) -> None:
    print_section_heading("Info", icon=ICONS["info"])
    print()
    print_key_values([("Files", file_count)])
    print()
    print(cyan("Legend"))
    print(warning(f"{ICONS['warning']} yellow = review timestamp source"))
    print(danger(f"{ICONS['warning']} red = needs review"))


def _print_rules_section(metadata_by_path: dict[Path, Metadata]) -> None:
    print_section_heading("Rules")
    print_key_values([("Timezone baseline", "Europe/Helsinki")])
    for year in metadata_years(metadata_by_path):
        label, separator, detail = helsinki_rule_line(year).partition(": ")
        print(f"{muted(label + separator)}{detail}")
    print_key_values([("Timestamp priority", " > ".join(TIMESTAMP_FIELDS))])


def _print_issues_section(
    candidates: list[Path], metadata_by_path: dict[Path, Metadata], timezone_reference_offsets: set[str]
) -> None:
    warning_counts: Counter[str] = Counter()

    for path in candidates:
        warnings = _audit_warnings(metadata_by_path[path], timezone_reference_offsets)
        warning_counts.update(warnings)

    print_section_heading("Issues", icon=ICONS["warning"])
    print_key_values(
        [
            ("Timezone mismatch/missing", warning_counts["timezone"]),
            ("File created date differs", warning_counts["file_create_date"]),
            ("Timestamp not DateTimeOriginal", warning_counts["timestamp"]),
            ("Unknown device", warning_counts["device"]),
        ]
    )


def _print_table(rows: list[list[str]], group_values: list[str]) -> None:
    headers = [
        "Filename",
        "Date",
        "Time",
        "Taken From",
        "File Created",
        "Offset",
        "Device",
        "Fingerprint",
    ]
    print_grouped_table(headers, rows, group_values)
