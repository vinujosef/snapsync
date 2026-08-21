# Repair selected audit issues in the current snapsync source folder.
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from config.settings import Settings
from snapsync.actions.audit_folder import (
    CYAN,
    RESET,
    _format_table_row,
    _helsinki_rule_line,
    _info_color,
    _metadata_warnings,
    _offset_at,
    _print_section_heading,
    _visible_len,
)
from snapsync.metadata import Metadata, TIMESTAMP_FIELDS, extract_metadata, parse_timezone_offset_minutes
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.scanner import scan_source
from snapsync.util import logger


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


@dataclass(frozen=True)
class DeviceChoice:
    name: str
    used_custom_name: bool


def run_audit_issue_fix(source_folder: Path, settings: Settings) -> int:
    try:
        candidates = scan_source(source_folder, settings)
        metadata_by_path = read_metadata_batch_or_fallback(candidates, settings)
    except OSError as exc:
        logger.error(f"Audit issue fix failed: {exc}")
        return 1

    timezone_fixes = _timezone_fixes(candidates, metadata_by_path)
    unknown_device_files = _unknown_device_files(candidates, metadata_by_path)
    _print_issue_menu(len(timezone_fixes), len(unknown_device_files))

    if not sys.stdin.isatty():
        print("No interactive input available; no audit issues fixed.")
        return 0

    choice = input("> ").strip().lower()
    if choice == "1":
        return _run_timezone_offset_fix(timezone_fixes, settings)
    if choice == "2":
        return _run_unknown_device_fix(unknown_device_files, settings)
    if choice == "3":
        return _run_manual_file_fix(source_folder, candidates, metadata_by_path, settings)

    logger.info("No audit issue fix selected")
    return 0


def _print_issue_menu(timezone_count: int, unknown_device_count: int) -> None:
    _print_section_heading("Issue(s)")
    _print_table(
        ["Option", "Issue", "Files"],
        [
            ["1", "Timezone mismatch/missing", str(timezone_count)],
            ["2", "Unknown device", str(unknown_device_count)],
            ["3", "Edit one file manually", "-"],
        ],
    )
    print("q. Back")
    print()
    print("Choose issue to fix:")


def _timezone_fixes(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[TimezoneFix]:
    fixes: list[TimezoneFix] = []
    zone = ZoneInfo("Europe/Helsinki")

    for path in candidates:
        metadata = metadata_by_path[path]
        if "timezone" not in _metadata_warnings(metadata):
            continue
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


def _unknown_device_files(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[DeviceFix]:
    fixes: list[DeviceFix] = []
    for path in candidates:
        metadata = metadata_by_path[path]
        if "device" not in _metadata_warnings(metadata):
            continue
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


def _run_timezone_offset_fix(fixes: list[TimezoneFix], settings: Settings) -> int:
    _print_section_heading("Timezone Offset Fix Preview")
    if not fixes:
        print("No timezone offsets need fixing.")
        return 0

    _print_step("i.", "Review timezone rules and preview")
    _print_timezone_rules(fixes)
    print()
    rows = [
        [
            fix.path.name,
            fix.selected_datetime.strftime("%Y-%m-%d"),
            fix.selected_datetime.strftime("%H:%M:%S"),
            fix.device_name,
            fix.current_offset,
            fix.expected_offset,
            _action_label("update offset", settings),
        ]
        for fix in fixes
    ]
    _print_table(["Filename", "Date", "Time", "Device", "Current Offset", "New Offset", "Action"], rows)
    print()
    if not _confirm_step("ii.", "Type yes to write timezone metadata"):
        logger.warning("Timezone offset fix was not confirmed; no files were changed")
        return 0

    errors = 0
    for fix in fixes:
        try:
            if not settings.dry_run:
                _write_timezone_offset(fix.path, fix.expected_offset, settings)
                _verify_timezone_offset(fix.path, fix.expected_offset, settings)
            print(
                f"{_completion_label('Updated', settings)} {fix.path.name}: "
                f"{fix.current_offset} -> {fix.expected_offset}"
            )
        except Exception as exc:
            errors += 1
            logger.error(f"Could not update timezone for {fix.path.name}: {exc}")

    return 0 if errors == 0 else 1


def _print_timezone_rules(fixes: list[TimezoneFix]) -> None:
    _print_section_heading("Rules")
    print(_info_color("Timezone baseline: Europe/Helsinki"))
    for year in sorted({fix.selected_datetime.year for fix in fixes}):
        print(_info_color(_helsinki_rule_line(year)))
    print(_info_color(f"Timestamp priority: {' > '.join(TIMESTAMP_FIELDS)}"))


def _run_unknown_device_fix(files: list[DeviceFix], settings: Settings) -> int:
    _print_section_heading("Unknown Device Fix")
    if not files:
        print("No unknown devices need fixing.")
        return 0

    errors = 0
    for fix in files:
        _print_step("i.", "Review file")
        _print_device_fix_metadata(fix)
        device_choice = _choose_batch_device_name()
        if not device_choice:
            print(f"Skipped {fix.path.name}")
            continue

        try:
            if not settings.dry_run:
                _write_device_model(fix.path, device_choice.name, settings)
            print(f"{_completion_label('Set Model', settings)} {fix.path.name}: {device_choice.name}")
        except Exception as exc:
            errors += 1
            logger.error(f"Could not update device for {fix.path.name}: {exc}")

    return 0 if errors == 0 else 1


def _print_device_fix_metadata(fix: DeviceFix) -> None:
    _print_table(
        ["File", "Date", "Time", "Taken From", "Offset", "Current Device"],
        [
            [
                fix.path.name,
                fix.selected_datetime.strftime("%Y-%m-%d"),
                fix.selected_datetime.strftime("%H:%M:%S"),
                fix.timestamp_field,
                fix.timezone_offset or "(none)",
                fix.device_name,
            ],
        ],
    )


def _run_manual_file_fix(
    source_folder: Path,
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    _print_section_heading("Manual Metadata Fix")
    filename = _step_input("i.", "Enter filename")
    if not filename:
        logger.info("No filename entered")
        return 0

    selected_path = _select_file_by_name(source_folder, candidates, filename)
    if selected_path is None:
        return 0

    metadata = metadata_by_path[selected_path]
    _print_current_metadata(selected_path, metadata)
    print()
    _print_step("ii.", "Choose metadata to edit")
    print("a. Date")
    print("b. Time")
    print("c. Offset")
    print("d. Device")
    print()
    choice = input("> ").strip().lower()

    try:
        if choice == "a":
            return _run_manual_date_fix(selected_path, metadata, settings)
        if choice == "b":
            return _run_manual_time_fix(selected_path, metadata, settings)
        if choice == "c":
            return _run_manual_offset_fix(selected_path, settings)
        if choice == "d":
            return _run_manual_device_fix(selected_path, settings)
    except Exception as exc:
        logger.error(f"Could not update metadata for {selected_path.name}: {exc}")
        return 1

    logger.info("No manual metadata field selected")
    return 0


def _select_file_by_name(source_folder: Path, candidates: list[Path], filename: str) -> Path | None:
    matches = [path for path in candidates if path.name == filename]
    if not matches:
        print(f"No file found with that name: {filename}")
        return None
    if len(matches) == 1:
        return matches[0]

    print("Multiple files found:")
    rows = [
        [str(index), str(path.relative_to(source_folder))]
        for index, path in enumerate(matches, start=1)
    ]
    _print_table(["Option", "File"], rows)
    choice = input("Choose file: ").strip()
    try:
        selected_index = int(choice)
    except ValueError:
        print("Skipped: invalid selection")
        return None
    if selected_index < 1 or selected_index > len(matches):
        print("Skipped: invalid selection")
        return None
    return matches[selected_index - 1]


def _print_current_metadata(path: Path, metadata: Metadata) -> None:
    taken_at = metadata.selected_datetime
    print()
    _print_table(
        ["File", "Date", "Time", "Taken From", "Offset", "Device"],
        [
            [
                path.name,
                taken_at.strftime("%Y-%m-%d"),
                taken_at.strftime("%H:%M:%S"),
                metadata.timestamp_field,
                metadata.timezone_offset or "(none)",
                metadata.device_name,
            ],
        ],
    )


def _run_manual_date_fix(path: Path, metadata: Metadata, settings: Settings) -> int:
    value = _step_input("iii.", "New date (YYYY-MM-DD)")
    new_date = _parse_date(value)
    new_datetime = datetime.combine(new_date, metadata.selected_datetime.time())
    return _write_manual_datetime_change(path, metadata, new_datetime, settings, "iv.")


def _run_manual_time_fix(path: Path, metadata: Metadata, settings: Settings) -> int:
    value = _step_input("iii.", "New time (HH:MM:SS)")
    new_time = _parse_time(value)
    new_datetime = datetime.combine(metadata.selected_datetime.date(), new_time)
    return _write_manual_datetime_change(path, metadata, new_datetime, settings, "iv.")


def _run_manual_offset_fix(path: Path, settings: Settings) -> int:
    offset = _step_input("iii.", "New offset (+HH:MM or -HH:MM)")
    if parse_timezone_offset_minutes(offset) is None:
        raise ValueError("offset must use +HH:MM or -HH:MM")

    print(f"Will change offset for {path.name} to {offset}")
    if not _confirm_step("iv.", "Type yes to write metadata"):
        logger.warning("Manual offset fix was not confirmed; no files were changed")
        return 0

    if not settings.dry_run:
        _write_timezone_offset(path, offset, settings)
        _verify_timezone_offset(path, offset, settings)
    print(f"{_completion_label('Updated', settings)} {path.name}: offset -> {offset}")
    return 0


def _run_manual_device_fix(path: Path, settings: Settings) -> int:
    device_choice = _choose_manual_device_name()
    if not device_choice:
        print(f"Skipped {path.name}")
        return 0

    print(f"Will set Model for {path.name} to {device_choice.name}")
    confirmation_step = "v." if device_choice.used_custom_name else "iv."
    if not _confirm_step(confirmation_step, "Type yes to write metadata"):
        logger.warning("Manual device fix was not confirmed; no files were changed")
        return 0

    if not settings.dry_run:
        _write_device_model(path, device_choice.name, settings)
        _verify_device_model(path, device_choice.name, settings)
    print(f"{_completion_label('Set Model', settings)} {path.name}: {device_choice.name}")
    return 0


def _write_manual_datetime_change(
    path: Path,
    metadata: Metadata,
    new_datetime: datetime,
    settings: Settings,
    confirmation_step: str,
) -> int:
    print(
        f"Will change {path.name}: "
        f"{metadata.selected_datetime:%Y-%m-%d %H:%M:%S} -> {new_datetime:%Y-%m-%d %H:%M:%S}"
    )
    if not _confirm_step(confirmation_step, "Type yes to write metadata"):
        logger.warning("Manual date/time fix was not confirmed; no files were changed")
        return 0

    if not settings.dry_run:
        _write_datetime(path, new_datetime, metadata.timezone_offset, settings)
        _verify_datetime(path, new_datetime, metadata.timezone_offset, settings)
    print(f"{_completion_label('Updated', settings)} {path.name}: date/time")
    return 0


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc


def _parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M:%S").time()
    except ValueError as exc:
        raise ValueError("time must use HH:MM:SS") from exc


def _choose_batch_device_name() -> DeviceChoice | None:
    _print_step("ii.", "Select one of the following")
    print("a. WhatsApp")
    print("b. Type the device name")
    print()
    choice = input("Choose device value, or leave blank to skip: ").strip().lower()
    if not choice:
        return None
    if choice == "a":
        return DeviceChoice("WhatsApp", used_custom_name=False)
    if choice == "b":
        device_name = _step_input("iii.", "Device name")
        if not device_name:
            return None
        return DeviceChoice(device_name, used_custom_name=True)

    print("Skipped: unknown choice")
    return None


def _choose_manual_device_name() -> DeviceChoice | None:
    _print_step("iii.", "Select one of the following")
    print("a. WhatsApp")
    print("b. Type the device name")
    print()
    choice = input("Choose device value, or leave blank to skip: ").strip().lower()
    if not choice:
        return None
    if choice == "a":
        return DeviceChoice("WhatsApp", used_custom_name=False)
    if choice == "b":
        device_name = _step_input("iv.", "Device name")
        if not device_name:
            return None
        return DeviceChoice(device_name, used_custom_name=True)

    print("Skipped: unknown choice")
    return None


def _confirm(prompt: str) -> bool:
    return input(prompt).strip().lower() == "yes"


def _confirm_step(marker: str, prompt: str) -> bool:
    return _step_input(marker, prompt).lower() == "yes"


def _step_input(marker: str, prompt: str) -> str:
    _print_step(marker, prompt)
    return input("> ").strip()


def _print_step(marker: str, text: str) -> None:
    print()
    print(f"{_step_color(marker)} {text}:")
    print()


def _step_color(value: str) -> str:
    return f"{CYAN}{value}{RESET}"


def _action_label(label: str, settings: Settings) -> str:
    return f"Will {label}" if settings.dry_run else label


def _completion_label(label: str, settings: Settings) -> str:
    if not settings.dry_run:
        return label
    if label == "Updated":
        return "Would update"
    if label == "Set Model":
        return "Would set Model"
    return f"Would {label.lower()}"


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(_visible_len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]
    print(_format_table_row(headers, widths))
    print(_format_table_row(["-" * width for width in widths], widths))
    for row in rows:
        print(_format_table_row(row, widths))


def _write_timezone_offset(path: Path, offset: str, settings: Settings) -> None:
    timestamp = ""
    if _is_video(path):
        metadata = extract_metadata(path, settings.exiftool_path)
        timestamp = metadata.selected_datetime.strftime("%Y:%m:%d %H:%M:%S")

    command = [
        settings.exiftool_path,
        "-overwrite_original",
        "-P",
        f"-OffsetTimeOriginal={offset}",
        f"-OffsetTime={offset}",
        f"-OffsetTimeDigitized={offset}",
    ]
    if timestamp:
        command.append(f"-Keys:CreationDate={timestamp}{offset}")
    command.append(str(path))

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def _verify_timezone_offset(path: Path, offset: str, settings: Settings) -> None:
    metadata = extract_metadata(path, settings.exiftool_path)
    if metadata.timezone_offset != offset:
        raise ValueError(f"metadata still reports {metadata.timezone_offset or '(none)'}")


def _verify_datetime(
    path: Path,
    expected_datetime: datetime,
    expected_offset: str | None,
    settings: Settings,
) -> None:
    metadata = extract_metadata(path, settings.exiftool_path)
    if metadata.selected_datetime != expected_datetime:
        raise ValueError(f"metadata still reports {metadata.selected_datetime:%Y-%m-%d %H:%M:%S}")
    if expected_offset and metadata.timezone_offset != expected_offset:
        raise ValueError(f"metadata offset still reports {metadata.timezone_offset or '(none)'}")


def _verify_device_model(path: Path, device_name: str, settings: Settings) -> None:
    metadata = extract_metadata(path, settings.exiftool_path)
    if metadata.device_name != device_name:
        raise ValueError(f"metadata still reports {metadata.device_name}")


def _is_video(path: Path) -> bool:
    return path.suffix.lower().lstrip(".") in {"mov", "mp4", "m4v", "avi", "mkv"}


def _write_datetime(
    path: Path,
    selected_datetime: datetime,
    timezone_offset: str | None,
    settings: Settings,
) -> None:
    timestamp = selected_datetime.strftime("%Y:%m:%d %H:%M:%S")
    command = [
        settings.exiftool_path,
        "-overwrite_original",
        "-P",
        f"-DateTimeOriginal={timestamp}",
        f"-CreateDate={timestamp}",
    ]
    if parse_timezone_offset_minutes(timezone_offset) is not None:
        command.extend(
            [
                f"-OffsetTimeOriginal={timezone_offset}",
                f"-OffsetTime={timezone_offset}",
                f"-OffsetTimeDigitized={timezone_offset}",
            ]
        )
    if _is_video(path) and parse_timezone_offset_minutes(timezone_offset) is not None:
        command.append(f"-Keys:CreationDate={timestamp}{timezone_offset}")
    command.append(str(path))

    subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def _write_device_model(path: Path, device_name: str, settings: Settings) -> None:
    subprocess.run(
        [
            settings.exiftool_path,
            "-overwrite_original",
            "-P",
            f"-Model={device_name}",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
