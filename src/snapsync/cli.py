# Print snapsync's interactive command-line prompts and status messages.
from __future__ import annotations

import sys
from pathlib import Path

from config.settings import Settings
from snapsync.constants import (
    ACTION_AUDIT_FOLDER,
    ACTION_COPY,
    ACTION_FIX_AUDIT_ISSUES,
    ACTION_QUIT,
    ACTION_RENAME,
)
from snapsync.timezone_correction import (
    TimezoneCorrectionPlan,
    describe_shift,
)
from snapsync.util.console import ICONS, format_path, print_key_values, print_section_heading, print_title


def choose_interactive_action() -> str:
    print_title("snapsync", icon=ICONS["app"])
    print_section_heading("Choose An Action")
    print(f"1  {ICONS['audit']}  Audit files in this folder")
    print(f"2  {ICONS['fix']}  Fix audit issues in this folder")
    print(f"3  {ICONS['rename']}  Rename files in this folder")
    print(f"4  {ICONS['copy']}  Copy files to destination")
    print(f"q  {ICONS['back']}  Quit")

    choice = input("> ").strip().lower()
    if choice == "1":
        return ACTION_AUDIT_FOLDER
    if choice == "2":
        return ACTION_FIX_AUDIT_ISSUES
    if choice == "3":
        return ACTION_RENAME
    if choice == "4":
        return ACTION_COPY
    return ACTION_QUIT


def print_action_context(action: str, source_folder: Path, settings: Settings) -> None:
    print()
    if action == ACTION_AUDIT_FOLDER:
        _print_action_heading("Audit Files In This Folder", icon=ICONS["audit"])
        print_key_values([("Source folder", format_path(source_folder))])
    elif action == ACTION_FIX_AUDIT_ISSUES:
        _print_action_heading("Fix Audit Issues In This Folder", icon=ICONS["fix"])
        print_key_values([("Source folder", format_path(source_folder))])
    elif action == ACTION_RENAME:
        _print_action_heading("Rename Files In This Folder", icon=ICONS["rename"])
        print_key_values(
            [
                ("Source folder", format_path(source_folder)),
                ("Filename prefix", settings.filename_prefix or "(none)"),
                ("Filename hash length", settings.hash_length),
            ]
        )
    else:
        _print_action_heading("Copy Files To Destination", icon=ICONS["copy"])
        print_key_values(
            [
                ("Source folder", format_path(source_folder)),
                ("Destination folder", format_path(settings.destination_folder)),
            ]
        )
    print_key_values([("Dry run", "yes" if settings.dry_run else "no")])


def confirm_timezone_correction(timezone_plan: TimezoneCorrectionPlan) -> bool:
    print_section_heading("Timezone Correction", icon=ICONS["fix"])
    print_key_values(
        [
            ("Detected iPhone timezone offset", timezone_plan.iphone_offset),
            ("Canon home timezone fallback", timezone_plan.canon_home_timezone),
            ("Canon files needing correction", len(timezone_plan.canon_files)),
            ("Canon filename/folder timestamp shift", describe_shift(timezone_plan.canon_shift_minutes)),
        ]
    )
    print("")
    print("Apply this correction to Canon files for this run?")
    if not sys.stdin.isatty():
        print("No interactive confirmation available; skipping Canon timezone correction.")
        return False
    choice = input("Type yes to apply: ").strip().lower()
    return choice == "yes"


class ProgressHeartbeat:
    def __init__(self, label: str = f"{ICONS['progress']} Still working...", interval: int = 50) -> None:
        self.label = label
        self.interval = interval
        self.count = 0

    def tick(self) -> None:
        self.count += 1
        if self.count % self.interval == 0:
            print(self.label)


def _print_action_heading(title: str, *, icon: str) -> None:
    print_section_heading(title, icon=icon)
