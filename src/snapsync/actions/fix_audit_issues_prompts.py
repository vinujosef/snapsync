# Print prompts and run the selected audit issue repair flow.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from config.settings import Settings
from snapsync.actions.audit_folder import (
    CYAN,
    RESET,
    _format_table_row,
    _helsinki_rule_line,
    _info_color,
    _print_section_heading,
    _visible_len,
)
from snapsync.actions.fix_audit_issues_finder import DeviceFix, TimezoneFix
from snapsync.actions.fix_audit_issues_writer import (
    verify_datetime,
    verify_device_model,
    verify_timezone_offset,
    write_datetime,
    write_device_model,
    write_timezone_offset,
)
from snapsync.metadata import Metadata, TIMESTAMP_FIELDS, parse_timezone_offset_minutes
from snapsync.util import logger


@dataclass(frozen=True)
class DeviceChoice:
    name: str
    used_custom_name: bool


def print_issue_menu(timezone_count: int, unknown_device_count: int) -> None:
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


def run_timezone_offset_fix(fixes: list[TimezoneFix], settings: Settings) -> int:
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
                write_timezone_offset(fix.path, fix.expected_offset, settings)
                verify_timezone_offset(fix.path, fix.expected_offset, settings)
            print(
                f"{_completion_label('Updated', settings)} {fix.path.name}: "
                f"{fix.current_offset} -> {fix.expected_offset}"
            )
        except Exception as exc:
            errors += 1
            logger.error(f"Could not update timezone for {fix.path.name}: {exc}")

    return 0 if errors == 0 else 1


def run_unknown_device_fix(files: list[DeviceFix], settings: Settings) -> int:
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
                write_device_model(fix.path, device_choice.name, settings)
            print(f"{_completion_label('Set Model', settings)} {fix.path.name}: {device_choice.name}")
        except Exception as exc:
            errors += 1
            logger.error(f"Could not update device for {fix.path.name}: {exc}")

    return 0 if errors == 0 else 1


def run_manual_file_fix(
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


def _print_timezone_rules(fixes: list[TimezoneFix]) -> None:
    _print_section_heading("Rules")
    print(_info_color("Timezone baseline: Europe/Helsinki"))
    for year in sorted({fix.selected_datetime.year for fix in fixes}):
        print(_info_color(_helsinki_rule_line(year)))
    print(_info_color(f"Timestamp priority: {' > '.join(TIMESTAMP_FIELDS)}"))


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
        write_timezone_offset(path, offset, settings)
        verify_timezone_offset(path, offset, settings)
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
        write_device_model(path, device_choice.name, settings)
        verify_device_model(path, device_choice.name, settings)
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
        write_datetime(path, new_datetime, metadata.timezone_offset, settings)
        verify_datetime(path, new_datetime, metadata.timezone_offset, settings)
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
