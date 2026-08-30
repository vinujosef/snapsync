# Print prompts and run the selected audit issue repair flow.
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Callable

from config.settings import Settings
from snapsync.actions.fix_audit_issues_finder import DeviceFix, TimezoneFix
from snapsync.actions.fix_audit_issues_writer import (
    verify_datetime,
    verify_device_model,
    verify_timezone_offset,
    write_datetime,
    write_device_model,
    write_timezone_offset,
)
from snapsync.file_fingerprint import file_fingerprint
from snapsync.metadata import Metadata, TIMESTAMP_FIELDS, parse_timezone_offset_minutes
from snapsync.metadata_audit import helsinki_rule_line
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.util import logger
from snapsync.util.console import (
    ICONS,
    changed_new,
    changed_old,
    cyan,
    format_display_date,
    format_display_datetime,
    muted,
    print_key_values,
    print_grouped_table,
    print_notice,
    print_section_heading,
    print_table,
)


@dataclass(frozen=True)
class DeviceChoice:
    name: str
    used_custom_name: bool


@dataclass(frozen=True)
class TimezoneFixSelection:
    fixes: list[TimezoneFix]
    preview_marker: str = "ii."
    preview_step_count: str = "2 of 3"
    confirmation_marker: str = "iii."
    confirmation_step_count: str = "3 of 3"


ROOT_PATH = ("snapsync",)
FIX_AUDIT_PATH = (*ROOT_PATH, "Fix audit issues")
REPAIR_ALL_PATH = (*FIX_AUDIT_PATH, "Repair all scanned files")
REPAIR_MATCHING_PATH = (*FIX_AUDIT_PATH, "Repair matching files")
EDIT_ONE_PATH = (*FIX_AUDIT_PATH, "Edit one file")


def print_issue_menu(timezone_count: int, unknown_device_count: int, bulk_count: int) -> None:
    _print_workflow_header(FIX_AUDIT_PATH)
    print_section_heading("Available Repairs", icon=ICONS["fix"])
    _print_table(
        ["Option", "Repair", "Files"],
        [
            ["1", "Fix timezone mismatch or missing offset", _files_label(timezone_count)],
            ["2", "Set unknown device name", _files_label(unknown_device_count)],
            ["3", "Edit metadata for one file", "-"],
            ["4", "Repair all scanned files", _files_label(bulk_count)],
            ["5", "Repair matching files", _files_label(bulk_count)],
        ],
    )
    print()
    if timezone_count == 0:
        print("No timezone mismatch or missing offset issues found.")
    if unknown_device_count == 0:
        print("No unknown device name issues found.")
    print("q. Back")
    print()
    print("Choose repair:")


def run_timezone_offset_fix(fixes: list[TimezoneFix], settings: Settings) -> int:
    path = (*FIX_AUDIT_PATH, "Fix timezone mismatch")
    _print_workflow_header(path)
    print_section_heading("Timezone Offset Fix", icon=ICONS["fix"])
    _print_dry_run_notice(settings)
    if not fixes:
        print("No timezone offsets need fixing.")
        return 0

    selection = _choose_timezone_offset_fixes(fixes, path)
    if selection is None:
        logger.info("No timezone offset fix mode selected")
        return 0
    selected_fixes = selection.fixes
    if not selected_fixes:
        print("No files matched that timezone offset fix mode.")
        return 0

    _print_step(
        selection.preview_marker,
        "Review timezone rules and preview",
        path=path,
        step_count=selection.preview_step_count,
    )
    _print_timezone_rules(selected_fixes)
    print()
    rows = [
        [
            fix.path.name,
            format_display_date(fix.selected_datetime),
            fix.selected_datetime.strftime("%H:%M:%S"),
            fix.device_name,
            fix.current_offset,
            fix.expected_offset,
            _action_label("update offset", settings),
            file_fingerprint(fix.path, _metadata_from_timezone_fix(fix)),
        ]
        for fix in selected_fixes
    ]
    headers = ["Filename", "Date", "Time", "Device", "Current Offset", "New Offset", "Action", "Fingerprint"]
    _print_file_table(
        headers,
        _color_preview_rows(headers, rows),
        [format_display_date(fix.selected_datetime) for fix in selected_fixes],
    )
    print()
    if not _confirm_step(
        selection.confirmation_marker,
        "Type yes to write timezone metadata",
        path=path,
        step_count=selection.confirmation_step_count,
    ):
        logger.warning("Timezone offset fix was not confirmed; no files were changed")
        return 0

    errors = 0
    for fix in selected_fixes:
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


def _choose_timezone_offset_fixes(
    fixes: list[TimezoneFix],
    path: tuple[str, ...],
) -> TimezoneFixSelection | None:
    _print_step("i.", "Choose timezone offset fix mode", path=path, step_count="1 of 3")
    print("1. Set only files with offset (none) to Helsinki timezone for each file date")
    print("2. Set only files with offset (none) to a custom offset")
    print("3. Change all timezone audit matches to Helsinki timezone")
    print()
    print("b. Back")
    print("q. Quit")
    print()

    choice = input("> ").strip().lower()
    if choice == "1":
        return TimezoneFixSelection(_missing_offset_fixes(fixes))
    if choice == "2":
        custom_offset = _step_input(
            "ii.",
            "Custom offset for files with offset (none) (+HH:MM or -HH:MM)",
            path=path,
            step_count="2 of 4",
        )
        if parse_timezone_offset_minutes(custom_offset) is None:
            raise ValueError("custom offset must use +HH:MM or -HH:MM")
        return TimezoneFixSelection(
            [replace(fix, expected_offset=custom_offset) for fix in _missing_offset_fixes(fixes)],
            preview_marker="iii.",
            preview_step_count="3 of 4",
            confirmation_marker="iv.",
            confirmation_step_count="4 of 4",
        )
    if choice == "3":
        return TimezoneFixSelection(fixes)
    return None


def _missing_offset_fixes(fixes: list[TimezoneFix]) -> list[TimezoneFix]:
    return [fix for fix in fixes if fix.current_offset == "(none)"]


def run_unknown_device_fix(files: list[DeviceFix], settings: Settings) -> int:
    path = (*FIX_AUDIT_PATH, "Set unknown device name")
    _print_workflow_header(path)
    print_section_heading("Unknown Device Fix", icon=ICONS["fix"])
    _print_dry_run_notice(settings)
    if not files:
        print("No unknown devices need fixing.")
        return 0

    errors = 0
    for fix in files:
        _print_step("i.", "Review file", path=path, step_count="1 of 3")
        _print_device_fix_metadata(fix)
        device_choice = _choose_batch_device_name(path, step_marker="ii.", step_count="2 of 3")
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
    path = EDIT_ONE_PATH
    _print_workflow_header(path)
    print_section_heading("Manual Metadata Fix", icon=ICONS["rename"])
    _print_dry_run_notice(settings)
    filename = _step_input("i.", "Enter filename", path=path, step_count="1 of 3")
    if not filename:
        logger.info("No filename entered")
        return 0

    selected_path = _select_file_by_name(source_folder, candidates, filename)
    if selected_path is None:
        return 0

    metadata = metadata_by_path[selected_path]
    _print_current_metadata(selected_path, metadata)
    print()
    _print_step("ii.", "Choose what to change", path=path, step_count="2 of 3")
    print("1. Change date")
    print("2. Change time")
    print("3. Change timezone offset")
    print("4. Change device name")
    print()
    choice = input("> ").strip().lower()

    try:
        if choice in {"1", "a"}:
            return _run_manual_date_fix(selected_path, metadata, settings)
        if choice in {"2", "b"}:
            return _run_manual_time_fix(selected_path, metadata, settings)
        if choice in {"3", "c"}:
            return _run_manual_offset_fix(selected_path, metadata, settings)
        if choice in {"4", "d"}:
            return _run_manual_device_fix(selected_path, metadata, settings)
    except Exception as exc:
        logger.error(f"Could not update metadata for {selected_path.name}: {exc}")
        return 1

    logger.info("No manual metadata field selected")
    return 0


def run_bulk_metadata_fix(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = REPAIR_ALL_PATH
    _print_workflow_header(path)
    print_section_heading("Repair All Scanned Files", icon=ICONS["fix"])
    _print_dry_run_notice(settings)
    if not candidates:
        print("No files found to fix.")
        return 0

    _print_step("i.", "Choose what to change", path=path, step_count="1 of 3")
    print("1. Change date")
    print("2. Change time")
    print("3. Change timezone offset")
    print("4. Change device name")
    print()
    print("b. Back")
    print("q. Quit")
    print()

    choice = input("> ").strip().lower()
    try:
        if choice == "1":
            return _run_bulk_date_fix(candidates, metadata_by_path, settings)
        if choice == "2":
            return _run_bulk_time_fix(candidates, metadata_by_path, settings)
        if choice == "3":
            return _run_bulk_timezone_fix(candidates, metadata_by_path, settings)
        if choice == "4":
            return _run_bulk_device_fix(candidates, metadata_by_path, settings)
    except Exception as exc:
        logger.error(f"Could not bulk update metadata: {exc}")
        return 1

    logger.info("No bulk metadata field selected")
    return 0


def run_batch_metadata_repair(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = REPAIR_MATCHING_PATH
    _print_workflow_header(path)
    print_section_heading("Repair Matching Files", icon=ICONS["fix"])
    _print_dry_run_notice(settings)
    if not candidates:
        print("No files found to fix.")
        return 0

    print("Use this option when you need to fix metadata for only some files in this folder.")
    _print_step("i.", "Choose what to change", path=path, step_count="1 of 5")
    print("1. Change date")
    print("2. Change time")
    print("3. Change timezone offset")
    print("4. Change device name")
    print()
    print("b. Back")
    print("q. Quit")
    print()

    choice = input("> ").strip().lower()
    try:
        if choice == "1":
            return _run_batch_date_repair(candidates, metadata_by_path, settings)
        if choice == "2":
            return _run_batch_time_repair(candidates, metadata_by_path, settings)
        if choice == "3":
            return _run_batch_timezone_repair(candidates, metadata_by_path, settings)
        if choice == "4":
            return _run_batch_device_repair(candidates, metadata_by_path, settings)
    except Exception as exc:
        logger.error(f"Could not batch update metadata: {exc}")
        return 1

    logger.info("No batch metadata field selected")
    return 0


def _run_batch_date_repair(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_MATCHING_PATH, "Change date")
    old_date = _parse_date(_step_input("ii.", "Current date to find (DD-MM-YYYY or YYYY-MM-DD)", path=path, step_count="2 of 5"))
    new_date = _parse_date(_step_input("iii.", "New date (DD-MM-YYYY or YYYY-MM-DD)", path=path, step_count="3 of 5"))
    device_filter = _step_input("iv.", "Device name contains", path=path, step_count="4 of 5")
    changes = _sort_candidates(
        [
            path
            for path in candidates
            if metadata_by_path[path].selected_datetime.date() == old_date
            and _metadata_matches_device_filter(metadata_by_path[path], device_filter)
        ],
        metadata_by_path,
    )
    if not changes:
        print("No files matched that date and device filter.")
        return 0

    rows = [
        [
            path.name,
            format_display_date(old_date),
            format_display_date(new_date),
            metadata_by_path[path].selected_datetime.strftime("%H:%M:%S"),
            metadata_by_path[path].timezone_offset or "(none)",
            metadata_by_path[path].device_name,
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]
    _print_bulk_preview(
        "Batch Date Repair Preview",
        ["Filename", "Old Date", "New Date", "Time", "Offset", "Device", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    if not _confirm_step("v.", _metadata_confirmation_prompt(settings), path=path, step_count="5 of 5"):
        logger.warning("Batch date repair was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        new_datetime = datetime.combine(new_date, metadata.selected_datetime.time())
        if not settings.dry_run:
            write_datetime(path, new_datetime, metadata.timezone_offset, settings)
        return replace(metadata, selected_datetime=new_datetime)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Date", apply)


def _run_batch_time_repair(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_MATCHING_PATH, "Change time")
    old_time = _parse_time(_step_input("ii.", "Current time to find (HH:MM:SS)", path=path, step_count="2 of 5"))
    new_time = _parse_time(_step_input("iii.", "New time (HH:MM:SS)", path=path, step_count="3 of 5"))
    device_filter = _step_input("iv.", "Device name contains", path=path, step_count="4 of 5")
    changes = _sort_candidates(
        [
            path
            for path in candidates
            if metadata_by_path[path].selected_datetime.time() == old_time
            and _metadata_matches_device_filter(metadata_by_path[path], device_filter)
        ],
        metadata_by_path,
    )
    if not changes:
        print("No files matched that time and device filter.")
        return 0

    rows = [
        [
            path.name,
            format_display_date(metadata_by_path[path].selected_datetime),
            old_time.strftime("%H:%M:%S"),
            new_time.strftime("%H:%M:%S"),
            metadata_by_path[path].timezone_offset or "(none)",
            metadata_by_path[path].device_name,
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]
    _print_bulk_preview(
        "Batch Time Repair Preview",
        ["Filename", "Date", "Old Time", "New Time", "Offset", "Device", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    if not _confirm_step("v.", _metadata_confirmation_prompt(settings), path=path, step_count="5 of 5"):
        logger.warning("Batch time repair was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        new_datetime = datetime.combine(metadata.selected_datetime.date(), new_time)
        if not settings.dry_run:
            write_datetime(path, new_datetime, metadata.timezone_offset, settings)
        return replace(metadata, selected_datetime=new_datetime)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Time", apply)


def _run_batch_timezone_repair(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_MATCHING_PATH, "Change timezone offset")
    old_offset = _step_input("ii.", "Current offset to find (+HH:MM or -HH:MM)", path=path, step_count="2 of 5")
    old_offset_minutes = parse_timezone_offset_minutes(old_offset)
    if old_offset_minutes is None:
        raise ValueError("current offset must use +HH:MM or -HH:MM")

    new_offset = _step_input("iii.", "New offset (+HH:MM or -HH:MM)", path=path, step_count="3 of 5")
    new_offset_minutes = parse_timezone_offset_minutes(new_offset)
    if new_offset_minutes is None:
        raise ValueError("new offset must use +HH:MM or -HH:MM")

    device_filter = _step_input("iv.", "Device name contains", path=path, step_count="4 of 5")
    changes = _sort_candidates(
        [
            path
            for path in candidates
            if metadata_by_path[path].timezone_offset == old_offset
            and _metadata_matches_device_filter(metadata_by_path[path], device_filter)
        ],
        metadata_by_path,
    )
    if not changes:
        print("No files matched that offset and device filter.")
        return 0

    shift = timedelta(minutes=new_offset_minutes - old_offset_minutes)
    rows = [
        [
            path.name,
            format_display_datetime(metadata_by_path[path].selected_datetime),
            format_display_datetime(metadata_by_path[path].selected_datetime + shift),
            metadata_by_path[path].timezone_offset or "(none)",
            new_offset,
            metadata_by_path[path].device_name,
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]

    _print_bulk_preview(
        "Batch Timezone Repair Preview",
        ["Filename", "Old Date/Time", "New Date/Time", "Old Offset", "New Offset", "Device", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    if not _confirm_step("v.", _metadata_confirmation_prompt(settings), path=path, step_count="5 of 5"):
        logger.warning("Batch timezone repair was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        new_datetime = metadata.selected_datetime + shift
        if not settings.dry_run:
            write_datetime(path, new_datetime, new_offset, settings)
        return replace(metadata, selected_datetime=new_datetime, timezone_offset=new_offset)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Date/Time/Offset", apply)


def _run_batch_device_repair(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_MATCHING_PATH, "Change device name")
    old_device_filter = _step_input("ii.", "Current device name contains", path=path, step_count="2 of 4")
    if not old_device_filter:
        raise ValueError("current device filter is required")
    new_device_name = _step_input("iii.", "New device name", path=path, step_count="3 of 4")
    if not new_device_name:
        raise ValueError("new device name is required")

    changes = _sort_candidates(
        [
            path
            for path in candidates
            if _metadata_matches_device_filter(metadata_by_path[path], old_device_filter)
        ],
        metadata_by_path,
    )
    if not changes:
        print("No files matched that device filter.")
        return 0

    rows = [
        [
            path.name,
            metadata_by_path[path].device_name,
            new_device_name,
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]
    _print_bulk_preview(
        "Batch Device Repair Preview",
        ["Filename", "Old Device", "New Device", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    if not _confirm_step("iv.", _metadata_confirmation_prompt(settings), path=path, step_count="4 of 4"):
        logger.warning("Batch device repair was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        if not settings.dry_run:
            write_device_model(path, new_device_name, settings)
        return replace(metadata, device_name=new_device_name)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Device", apply)


def _run_bulk_date_fix(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_ALL_PATH, "Change date")
    value = _step_input("ii.", "New date (DD-MM-YYYY or YYYY-MM-DD)", path=path, step_count="2 of 3")
    new_date = _parse_date(value)
    changes = _sort_candidates(candidates, metadata_by_path)
    rows = [
        [
            path.name,
            format_display_date(metadata_by_path[path].selected_datetime),
            format_display_date(new_date),
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]

    _print_bulk_preview(
        "Date Fix Preview",
        ["Filename", "Old Date", "New Date", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    if not _confirm_step("iii.", _metadata_confirmation_prompt(settings), path=path, step_count="3 of 3"):
        logger.warning("Bulk date fix was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        new_datetime = datetime.combine(new_date, metadata.selected_datetime.time())
        if not settings.dry_run:
            write_datetime(path, new_datetime, metadata.timezone_offset, settings)
        return replace(metadata, selected_datetime=new_datetime)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Date", apply)


def _run_bulk_time_fix(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_ALL_PATH, "Change time")
    value = _step_input("ii.", "New time (HH:MM:SS)", path=path, step_count="2 of 3")
    new_time = _parse_time(value)
    changes = _sort_candidates(candidates, metadata_by_path)
    rows = [
        [
            path.name,
            metadata_by_path[path].selected_datetime.strftime("%H:%M:%S"),
            new_time.strftime("%H:%M:%S"),
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]

    _print_bulk_preview(
        "Time Fix Preview",
        ["Filename", "Old Time", "New Time", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    if not _confirm_step("iii.", _metadata_confirmation_prompt(settings), path=path, step_count="3 of 3"):
        logger.warning("Bulk time fix was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        new_datetime = datetime.combine(metadata.selected_datetime.date(), new_time)
        if not settings.dry_run:
            write_datetime(path, new_datetime, metadata.timezone_offset, settings)
        return replace(metadata, selected_datetime=new_datetime)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Time", apply)


def _run_bulk_timezone_fix(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_ALL_PATH, "Change timezone offset")
    new_offset = _step_input("ii.", "New offset (+HH:MM or -HH:MM)", path=path, step_count="2 of 3")
    new_offset_minutes = parse_timezone_offset_minutes(new_offset)
    if new_offset_minutes is None:
        raise ValueError("offset must use +HH:MM or -HH:MM")

    changes = _sort_candidates(
        [
            path
            for path in candidates
            if parse_timezone_offset_minutes(metadata_by_path[path].timezone_offset) is not None
        ],
        metadata_by_path,
    )
    rows = [
        [
            path.name,
            format_display_datetime(metadata_by_path[path].selected_datetime),
            format_display_datetime(_shift_datetime_to_offset(metadata_by_path[path], new_offset_minutes)),
            metadata_by_path[path].timezone_offset or "(none)",
            new_offset,
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]

    _print_bulk_preview(
        "Timezone Fix Preview",
        ["Filename", "Old Date/Time", "New Date/Time", "Old Offset", "New Offset", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    if not _confirm_step("iii.", _metadata_confirmation_prompt(settings), path=path, step_count="3 of 3"):
        logger.warning("Bulk timezone fix was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        new_datetime = _shift_datetime_to_offset(metadata, new_offset_minutes)
        if not settings.dry_run:
            write_datetime(path, new_datetime, new_offset, settings)
        return replace(metadata, selected_datetime=new_datetime, timezone_offset=new_offset)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Time/Offset", apply)


def _run_bulk_device_fix(
    candidates: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
) -> int:
    path = (*REPAIR_ALL_PATH, "Change device name")
    device_choice = _choose_bulk_device_name(path)
    if not device_choice:
        print("Skipped bulk device fix")
        return 0

    changes = _sort_candidates(candidates, metadata_by_path)
    rows = [
        [
            path.name,
            metadata_by_path[path].device_name,
            device_choice.name,
            file_fingerprint(path, metadata_by_path[path]),
        ]
        for path in changes
    ]

    _print_bulk_preview(
        "Device Fix Preview",
        ["Filename", "Old Device", "New Device", "Fingerprint"],
        rows,
        _group_values(changes, metadata_by_path),
    )
    confirmation_step = "iv." if device_choice.used_custom_name else "iii."
    confirmation_count = "4 of 4" if device_choice.used_custom_name else "3 of 3"
    if not _confirm_step(confirmation_step, _metadata_confirmation_prompt(settings), path=path, step_count=confirmation_count):
        logger.warning("Bulk device fix was not confirmed; no files were changed")
        return 0

    def apply(path: Path, metadata: Metadata) -> Metadata:
        if not settings.dry_run:
            write_device_model(path, device_choice.name, settings)
        return replace(metadata, device_name=device_choice.name)

    return _write_bulk_changes(changes, metadata_by_path, settings, "Device", apply)


def _write_bulk_changes(
    changes: list[Path],
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
    changed_field: str,
    apply_change: Callable[[Path, Metadata], Metadata],
) -> int:
    errors = 0
    final_rows: list[list[str]] = []
    changed_paths: list[Path] = []
    planned_metadata_by_path: dict[Path, Metadata] = {}

    for path in changes:
        metadata = metadata_by_path[path]
        try:
            # In dry-run mode, this returns the metadata as it would look after
            # the fix. In real mode, it performs the write and returns the same
            # planned shape so we can remember which files succeeded.
            final_metadata = apply_change(path, metadata)
            changed_paths.append(path)
            planned_metadata_by_path[path] = final_metadata
        except Exception as exc:
            errors += 1
            logger.error(f"Could not update metadata for {path.name}: {exc}")

    if settings.dry_run:
        print_section_heading("Dry Run Metadata Preview")
        print("DRY RUN: no metadata was written.")
    else:
        print_section_heading("Updated Metadata")

    if not settings.dry_run and changed_paths:
        # Read once in batch after the writes. This is much faster than starting
        # exiftool again for every single file.
        read_metadata_by_path = read_metadata_batch_or_fallback(changed_paths, settings)
        verified_paths: list[Path] = []
        for path in changed_paths:
            planned_metadata = planned_metadata_by_path[path]
            read_metadata = read_metadata_by_path[path]
            if not _bulk_change_was_written(read_metadata, planned_metadata, changed_field):
                errors += 1
                logger.error(f"Metadata readback did not match planned {changed_field.lower()} for {path.name}")
                continue
            planned_metadata_by_path[path] = read_metadata
            verified_paths.append(path)
        changed_paths = verified_paths

    for path in changed_paths:
        final_rows.append(_metadata_readback_row(path, planned_metadata_by_path[path], changed_field))

    if final_rows:
        _print_file_table(
            ["Filename", "Date", "Time", "Taken From", "Offset", "Device", "Fingerprint"],
            final_rows,
            [format_display_date(planned_metadata_by_path[path].selected_datetime) for path in changed_paths],
        )
    else:
        print("No metadata was updated.")
    return 0 if errors == 0 else 1


def _metadata_readback_row(path: Path, metadata: Metadata, changed_field: str) -> list[str]:
    taken_at = metadata.selected_datetime
    values = {
        "Date": format_display_date(taken_at),
        "Time": taken_at.strftime("%H:%M:%S"),
        "Taken From": metadata.timestamp_field,
        "Offset": metadata.timezone_offset or "(none)",
        "Device": metadata.device_name,
    }
    for field in changed_field.split("/"):
        if field in values:
            values[field] = _changed_color(values[field])

    return [
        path.name,
        values["Date"],
        values["Time"],
        values["Taken From"],
        values["Offset"],
        values["Device"],
        file_fingerprint(path, metadata),
    ]


def _bulk_change_was_written(read_metadata: Metadata, planned_metadata: Metadata, changed_field: str) -> bool:
    # Use the one batch readback to confirm the value changed. This avoids a
    # second exiftool read for every file.
    if changed_field == "Date":
        return read_metadata.selected_datetime.date() == planned_metadata.selected_datetime.date()
    if changed_field == "Time":
        return read_metadata.selected_datetime.time() == planned_metadata.selected_datetime.time()
    if changed_field == "Offset":
        return read_metadata.timezone_offset == planned_metadata.timezone_offset
    if changed_field == "Time/Offset":
        return (
            read_metadata.selected_datetime == planned_metadata.selected_datetime
            and read_metadata.timezone_offset == planned_metadata.timezone_offset
        )
    if changed_field == "Date/Time/Offset":
        return (
            read_metadata.selected_datetime == planned_metadata.selected_datetime
            and read_metadata.timezone_offset == planned_metadata.timezone_offset
        )
    if changed_field == "Device":
        return read_metadata.device_name == planned_metadata.device_name
    return True


def _shift_datetime_to_offset(metadata: Metadata, new_offset_minutes: int) -> datetime:
    current_offset_minutes = parse_timezone_offset_minutes(metadata.timezone_offset)
    if current_offset_minutes is None:
        raise ValueError("current metadata offset must use +HH:MM or -HH:MM")
    shift = timedelta(minutes=new_offset_minutes - current_offset_minutes)
    return metadata.selected_datetime + shift


def _metadata_matches_device_filter(
    metadata: Metadata,
    device_filter: str,
) -> bool:
    if not device_filter:
        return True
    return device_filter.lower() in metadata.device_name.lower()


def _print_bulk_preview(title: str, headers: list[str], rows: list[list[str]], group_values: list[str]) -> None:
    print_section_heading(title, icon=ICONS["audit"])
    print(muted("Previewing affected files"))
    print()
    _print_file_table(headers, _color_preview_rows(headers, rows), group_values)


def _sort_candidates(candidates: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[Path]:
    return sorted(
        candidates,
        key=lambda path: (
            metadata_by_path[path].selected_datetime,
            path.name.lower(),
            str(path).lower(),
        ),
    )


def _changed_color(value: str) -> str:
    return changed_new(value)


def _old_value_color(value: str) -> str:
    return changed_old(value)


def _new_value_color(value: str) -> str:
    return changed_new(value)


def _color_preview_rows(headers: list[str], rows: list[list[str]]) -> list[list[str]]:
    return [
        [
            _preview_value_color(headers[index], value)
            for index, value in enumerate(row)
        ]
        for row in rows
    ]


def _preview_value_color(header: str, value: str) -> str:
    normalized_header = header.lower()
    if normalized_header.startswith(("old ", "current ")):
        return _old_value_color(value)
    if normalized_header.startswith("new "):
        return _new_value_color(value)
    return value


def _print_dry_run_notice(settings: Settings) -> None:
    if settings.dry_run:
        print_notice(
            "DRY RUN",
            "No metadata will be written. Preview tables show planned values only.",
            icon=ICONS["warning"],
        )


def _metadata_confirmation_prompt(settings: Settings) -> str:
    if settings.dry_run:
        return "Type yes to preview dry-run metadata"
    return "Type yes to write metadata"


def _print_timezone_rules(fixes: list[TimezoneFix]) -> None:
    print_section_heading("Rules")
    print_key_values([("Timezone baseline", "Europe/Helsinki")])
    for year in sorted({fix.selected_datetime.year for fix in fixes}):
        label, separator, detail = helsinki_rule_line(year).partition(": ")
        print(f"{muted(label + separator)}{detail}")
    print_key_values([("Timestamp priority", " > ".join(TIMESTAMP_FIELDS))])


def _print_device_fix_metadata(fix: DeviceFix) -> None:
    _print_table(
        ["File", "Date", "Time", "Taken From", "Offset", "Current Device", "Fingerprint"],
        [
            [
                fix.path.name,
                format_display_date(fix.selected_datetime),
                fix.selected_datetime.strftime("%H:%M:%S"),
                fix.timestamp_field,
                fix.timezone_offset or "(none)",
                fix.device_name,
                file_fingerprint(fix.path, _metadata_from_device_fix(fix)),
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
        ["File", "Date", "Time", "Taken From", "Offset", "Device", "Fingerprint"],
        [
            [
                path.name,
                format_display_date(taken_at),
                taken_at.strftime("%H:%M:%S"),
                metadata.timestamp_field,
                metadata.timezone_offset or "(none)",
                metadata.device_name,
                file_fingerprint(path, metadata),
            ],
        ],
    )


def _run_manual_date_fix(path: Path, metadata: Metadata, settings: Settings) -> int:
    workflow_path = (*EDIT_ONE_PATH, "Change date")
    value = _step_input("iii.", "New date (DD-MM-YYYY or YYYY-MM-DD)", path=workflow_path, step_count="3 of 4")
    new_date = _parse_date(value)
    new_datetime = datetime.combine(new_date, metadata.selected_datetime.time())
    return _write_manual_datetime_change(path, metadata, new_datetime, settings, "iv.", workflow_path)


def _run_manual_time_fix(path: Path, metadata: Metadata, settings: Settings) -> int:
    workflow_path = (*EDIT_ONE_PATH, "Change time")
    value = _step_input("iii.", "New time (HH:MM:SS)", path=workflow_path, step_count="3 of 4")
    new_time = _parse_time(value)
    new_datetime = datetime.combine(metadata.selected_datetime.date(), new_time)
    return _write_manual_datetime_change(path, metadata, new_datetime, settings, "iv.", workflow_path)


def _run_manual_offset_fix(path: Path, metadata: Metadata, settings: Settings) -> int:
    workflow_path = (*EDIT_ONE_PATH, "Change timezone offset")
    offset = _step_input("iii.", "New offset (+HH:MM or -HH:MM)", path=workflow_path, step_count="3 of 4")
    if parse_timezone_offset_minutes(offset) is None:
        raise ValueError("offset must use +HH:MM or -HH:MM")

    print(f"Will change offset for {path.name} to {offset}")
    if not _confirm_step("iv.", "Type yes to write metadata", path=workflow_path, step_count="4 of 4"):
        logger.warning("Manual offset fix was not confirmed; no files were changed")
        return 0

    if not settings.dry_run:
        write_timezone_offset(path, offset, settings)
        verify_timezone_offset(path, offset, settings)
    _print_manual_metadata_result(path, replace(metadata, timezone_offset=offset), "Offset", settings)
    return 0


def _run_manual_device_fix(path: Path, metadata: Metadata, settings: Settings) -> int:
    workflow_path = (*EDIT_ONE_PATH, "Change device name")
    device_choice = _choose_manual_device_name(workflow_path)
    if not device_choice:
        print(f"Skipped {path.name}")
        return 0

    print(f"Will set Model for {path.name} to {device_choice.name}")
    confirmation_step = "v." if device_choice.used_custom_name else "iv."
    confirmation_count = "5 of 5" if device_choice.used_custom_name else "4 of 4"
    if not _confirm_step(confirmation_step, "Type yes to write metadata", path=workflow_path, step_count=confirmation_count):
        logger.warning("Manual device fix was not confirmed; no files were changed")
        return 0

    if not settings.dry_run:
        write_device_model(path, device_choice.name, settings)
        verify_device_model(path, device_choice.name, settings)
    _print_manual_metadata_result(path, replace(metadata, device_name=device_choice.name), "Device", settings)
    return 0


def _write_manual_datetime_change(
    path: Path,
    metadata: Metadata,
    new_datetime: datetime,
    settings: Settings,
    confirmation_step: str,
    workflow_path: tuple[str, ...],
) -> int:
    print(
        f"Will change {path.name}: "
        f"{format_display_datetime(metadata.selected_datetime)} -> {format_display_datetime(new_datetime)}"
    )
    if not _confirm_step(confirmation_step, "Type yes to write metadata", path=workflow_path, step_count="4 of 4"):
        logger.warning("Manual date/time fix was not confirmed; no files were changed")
        return 0

    if not settings.dry_run:
        write_datetime(path, new_datetime, metadata.timezone_offset, settings)
        verify_datetime(path, new_datetime, metadata.timezone_offset, settings)
    _print_manual_metadata_result(path, replace(metadata, selected_datetime=new_datetime), "Date/Time", settings)
    return 0


def _print_manual_metadata_result(
    path: Path,
    metadata: Metadata,
    changed_field: str,
    settings: Settings,
) -> None:
    if settings.dry_run:
        print_section_heading("Dry Run Metadata Preview")
        print("DRY RUN: no metadata was written.")
    else:
        print_section_heading("Updated Metadata")
    _print_file_table(
        ["Filename", "Date", "Time", "Taken From", "Offset", "Device", "Fingerprint"],
        [_metadata_readback_row(path, metadata, changed_field)],
        [format_display_date(metadata.selected_datetime)],
    )


def _parse_date(value: str) -> date:
    for date_format in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            pass
    raise ValueError("date must use DD-MM-YYYY")


def _parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M:%S").time()
    except ValueError as exc:
        raise ValueError("time must use HH:MM:SS") from exc


def _choose_batch_device_name(
    path: tuple[str, ...] | None = None,
    *,
    step_marker: str = "ii.",
    step_count: str | None = None,
    custom_step_count: str = "3 of 3",
) -> DeviceChoice | None:
    _print_step(step_marker, "Choose device value", path=path, step_count=step_count)
    print("a. WhatsApp")
    print("b. Type the device name")
    print()
    choice = input("Choose device value, or leave blank to skip: ").strip().lower()
    if not choice:
        return None
    if choice == "a":
        return DeviceChoice("WhatsApp", used_custom_name=False)
    if choice == "b":
        device_name = _step_input("iii.", "Device name", path=path, step_count=custom_step_count)
        if not device_name:
            return None
        return DeviceChoice(device_name, used_custom_name=True)

    print("Skipped: unknown choice")
    return None


def _choose_bulk_device_name(path: tuple[str, ...]) -> DeviceChoice | None:
    return _choose_batch_device_name(path, step_marker="ii.", step_count="2 of 3", custom_step_count="3 of 4")


def _choose_manual_device_name(path: tuple[str, ...]) -> DeviceChoice | None:
    _print_step("iii.", "Choose device value", path=path, step_count="3 of 4")
    print("a. WhatsApp")
    print("b. Type the device name")
    print()
    choice = input("Choose device value, or leave blank to skip: ").strip().lower()
    if not choice:
        return None
    if choice == "a":
        return DeviceChoice("WhatsApp", used_custom_name=False)
    if choice == "b":
        device_name = _step_input("iv.", "Device name", path=path, step_count="4 of 5")
        if not device_name:
            return None
        return DeviceChoice(device_name, used_custom_name=True)

    print("Skipped: unknown choice")
    return None


def _confirm_step(
    marker: str,
    prompt: str,
    *,
    path: tuple[str, ...] | None = None,
    step_count: str | None = None,
) -> bool:
    return _step_input(marker, prompt, path=path, step_count=step_count).lower() == "yes"


def _step_input(
    marker: str,
    prompt: str,
    *,
    path: tuple[str, ...] | None = None,
    step_count: str | None = None,
) -> str:
    _print_step(marker, prompt, path=path, step_count=step_count)
    return input("> ").strip()


def _print_step(
    marker: str,
    text: str,
    *,
    path: tuple[str, ...] | None = None,
    step_count: str | None = None,
) -> None:
    if path:
        _print_workflow_header(path, step_count=step_count)
    print()
    print(f"{_step_color(marker)} {text}:")
    print()


def _print_workflow_header(path: tuple[str, ...], *, step_count: str | None = None) -> None:
    print()
    print(cyan(" > ".join(path), bold=True))
    if step_count:
        print(muted(f"Step {step_count}"))


def _files_label(count: int) -> str:
    if count == 0:
        return "no issues found"
    if count == 1:
        return "1 file"
    return f"{count} files"


def _step_color(value: str) -> str:
    return cyan(value)


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
    print_table(headers, rows)


def _print_file_table(headers: list[str], rows: list[list[str]], group_values: list[str]) -> None:
    print_grouped_table(headers, rows, group_values)


def _group_values(paths: list[Path], metadata_by_path: dict[Path, Metadata]) -> list[str]:
    return [format_display_date(metadata_by_path[path].selected_datetime) for path in paths]


def _metadata_from_timezone_fix(fix: TimezoneFix) -> Metadata:
    return Metadata(
        selected_datetime=fix.selected_datetime,
        timestamp_field="DateTimeOriginal",
        device_name=fix.device_name,
        quality="metadata",
        timezone_offset=fix.current_offset if fix.current_offset != "(none)" else None,
        image_width=fix.image_width,
        image_height=fix.image_height,
    )


def _metadata_from_device_fix(fix: DeviceFix) -> Metadata:
    return Metadata(
        selected_datetime=fix.selected_datetime,
        timestamp_field=fix.timestamp_field,
        device_name=fix.device_name,
        quality="metadata",
        timezone_offset=fix.timezone_offset,
        image_width=fix.image_width,
        image_height=fix.image_height,
    )
