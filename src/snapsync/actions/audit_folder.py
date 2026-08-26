# Audit capture metadata for files in the current snapsync source folder.
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from config.settings import Settings
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


RESET = "\033[0m"
CYAN = "\033[36m"
RED = "\033[31m"
YELLOW = "\033[33m"
ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")


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
    _print_section_heading("Details")
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
        taken_at.strftime("%Y-%m-%d"),
        taken_at.strftime("%H:%M:%S"),
        _timestamp_field_cell(metadata),
        _timezone_cell(metadata),
        _device_cell(metadata),
    ]


def _file_cell(path: Path, metadata: Metadata) -> str:
    warnings = metadata_warnings(metadata)
    if warnings & {"timezone", "device"}:
        return _error_color(path.name)
    if "timestamp" in warnings:
        return _warning_color(path.name)
    return path.name


def _timestamp_field_cell(metadata: Metadata) -> str:
    if metadata.timestamp_field != "DateTimeOriginal":
        return _warning_color(metadata.timestamp_field)
    return metadata.timestamp_field


def _device_cell(metadata: Metadata) -> str:
    if metadata.device_name == "UnknownDevice":
        return _error_color(metadata.device_name)
    return metadata.device_name


def _timezone_cell(metadata: Metadata) -> str:
    if timezone_has_warning(metadata):
        return _error_color(metadata.timezone_offset or "(none)")
    return metadata.timezone_offset or "(none)"


def _print_info_section(file_count: int) -> None:
    _print_section_heading("Info")
    print(_info_color(f"Files: {file_count}"))
    print(_info_color("Legend:"))
    print(_info_color("- red = needs review"))


def _print_rules_section(metadata_by_path: dict[Path, Metadata]) -> None:
    _print_section_heading("Rules")
    print(_info_color("Timezone baseline: Europe/Helsinki"))
    for year in metadata_years(metadata_by_path):
        print(_info_color(helsinki_rule_line(year)))
    print(_info_color(f"Timestamp priority: {' > '.join(TIMESTAMP_FIELDS)}"))


def _print_issues_section(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> None:
    warning_counts: Counter[str] = Counter()

    for path in candidates:
        warnings = metadata_warnings(metadata_by_path[path])
        warning_counts.update(warnings)

    _print_section_heading("Issue(s)")
    print(_info_color(f"Timezone mismatch/missing: {warning_counts['timezone']}"))
    print(_info_color(f"Timestamp not DateTimeOriginal: {warning_counts['timestamp']}"))
    print(_info_color(f"Unknown device: {warning_counts['device']}"))


def _info_color(value: str) -> str:
    return f"{CYAN}{value}{RESET}"


def _error_color(value: str) -> str:
    return f"{RED}{value}{RESET}"


def _warning_color(value: str) -> str:
    return f"{YELLOW}{value}{RESET}"


def _print_section_heading(title: str) -> None:
    print()
    print(_info_color(f"{title}:"))
    print(_info_color("-" * (len(title) + 1)))


def _print_table(rows: list[list[str]]) -> None:
    headers = [
        "Filename",
        "Date",
        "Time",
        "Taken From",
        "Offset",
        "Device",
    ]
    widths = [
        max(_visible_len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]

    print(_format_table_row(headers, widths))
    print(_format_table_separator(widths))
    row_width = _visible_len(_format_table_row(headers, widths))
    previous_date: str | None = None
    for row in rows:
        current_date = row[1]
        if previous_date is not None and current_date != previous_date:
            print("-" * row_width)
        print(_format_table_row(row, widths))
        previous_date = current_date


def _format_table_row(values: list[str], widths: list[int]) -> str:
    cells = [_pad_cell(value, widths[index]) for index, value in enumerate(values)]
    return f"| {' | '.join(cells)} |"


def _format_table_separator(widths: list[int]) -> str:
    cells = ["-" * width for width in widths]
    return f"| {' | '.join(cells)} |"


def _pad_cell(value: str, width: int) -> str:
    return value + (" " * (width - _visible_len(value)))


def _visible_len(value: str) -> int:
    return len(ANSI_PATTERN.sub("", value))
