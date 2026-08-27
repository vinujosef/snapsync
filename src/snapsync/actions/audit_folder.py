# Audit capture metadata for files in the current snapsync source folder.
from __future__ import annotations

from collections import Counter
from pathlib import Path

from config.settings import Settings
from snapsync.file_fingerprint import file_fingerprint
from snapsync.metadata import Metadata, TIMESTAMP_FIELDS
from snapsync.metadata_audit import (
    helsinki_rule_line,
    metadata_warnings,
    metadata_years,
    timezone_has_warning,
)
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.scanner import scan_source
from snapsync.util import logger
from snapsync.util.console import (
    cyan,
    format_display_date,
    print_grouped_table,
    print_section_heading,
    red,
    yellow,
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
    rows = [_metadata_row(path, metadata_by_path[path]) for path in sorted_candidates]
    print_section_heading("Details")
    _print_table(rows)
    _print_issues_section(sorted_candidates, metadata_by_path)
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


def _metadata_row(path: Path, metadata: Metadata) -> list[str]:
    taken_at = metadata.selected_datetime
    return [
        _file_cell(path, metadata),
        format_display_date(taken_at),
        taken_at.strftime("%H:%M:%S"),
        _timestamp_field_cell(metadata),
        _timezone_cell(metadata),
        _device_cell(metadata),
        file_fingerprint(path, metadata),
    ]


def _file_cell(path: Path, metadata: Metadata) -> str:
    warnings = metadata_warnings(metadata)
    if warnings & {"timezone", "device"}:
        return red(path.name)
    if "timestamp" in warnings:
        return yellow(path.name)
    return path.name


def _timestamp_field_cell(metadata: Metadata) -> str:
    if metadata.timestamp_field != "DateTimeOriginal":
        return yellow(metadata.timestamp_field)
    return metadata.timestamp_field


def _device_cell(metadata: Metadata) -> str:
    if metadata.device_name == "UnknownDevice":
        return red(metadata.device_name)
    return metadata.device_name


def _timezone_cell(metadata: Metadata) -> str:
    if timezone_has_warning(metadata):
        return red(metadata.timezone_offset or "(none)")
    return metadata.timezone_offset or "(none)"


def _print_info_section(file_count: int) -> None:
    print_section_heading("Info")
    print(cyan(f"Files: {file_count}"))
    print(cyan("Legend:"))
    print(cyan("- red = needs review"))


def _print_rules_section(metadata_by_path: dict[Path, Metadata]) -> None:
    print_section_heading("Rules")
    print(cyan("Timezone baseline: Europe/Helsinki"))
    for year in metadata_years(metadata_by_path):
        print(cyan(helsinki_rule_line(year)))
    print(cyan(f"Timestamp priority: {' > '.join(TIMESTAMP_FIELDS)}"))


def _print_issues_section(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> None:
    warning_counts: Counter[str] = Counter()

    for path in candidates:
        warnings = metadata_warnings(metadata_by_path[path])
        warning_counts.update(warnings)

    print_section_heading("Issue(s)")
    print(cyan(f"Timezone mismatch/missing: {warning_counts['timezone']}"))
    print(cyan(f"Timestamp not DateTimeOriginal: {warning_counts['timestamp']}"))
    print(cyan(f"Unknown device: {warning_counts['device']}"))


def _print_table(rows: list[list[str]]) -> None:
    headers = [
        "Filename",
        "Date",
        "Time",
        "Taken From",
        "Offset",
        "Device",
        "Fingerprint",
    ]
    print_grouped_table(headers, rows, [row[1] for row in rows])
