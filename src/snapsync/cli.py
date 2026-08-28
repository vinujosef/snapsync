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
from snapsync.util.console import blue, cyan


def choose_interactive_action() -> str:
    print(blue("================"))
    print(blue(" 🎞️ snapsync 📤", bold=True))
    print(blue("================"))
    print()
    print(cyan("Choose an action:", bold=True))
    print(cyan("----------------"))
    print("1️⃣  Audit files in this folder")
    print("2️⃣  Fix audit issues in this folder")
    print("3️⃣  Rename files in this folder")
    print("4️⃣  Copy files to destination")
    print("q. Quit")

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
        _print_action_heading("AUDIT FILES IN THIS FOLDER:")
        print(f"🔎 Source folder: {source_folder}")
    elif action == ACTION_FIX_AUDIT_ISSUES:
        _print_action_heading("FIX AUDIT ISSUES IN THIS FOLDER:")
        print(f"🔎 Source folder: {source_folder}")
    elif action == ACTION_RENAME:
        _print_action_heading("RENAME FILES IN THIS FOLDER:")
        print(f"🔎 Source folder: {source_folder}")
        print(f"🧾 Filename prefix: {settings.filename_prefix or '(none)'}")
        print(f"#️⃣ Filename hash length: {settings.hash_length}")
    else:
        _print_action_heading("COPY FILES TO DESTINATION:")
        print(f"➡️ Source folder: {source_folder}")
        print(f"⬅️ Copy destination folder: {settings.destination_folder}")
    print(f"✳️ Dry Run : {'yes' if settings.dry_run else 'no'}")


def confirm_timezone_correction(timezone_plan: TimezoneCorrectionPlan) -> bool:
    print("")
    print("Timezone correction")
    print("-------------------")
    print(f"Detected iPhone timezone offset: {timezone_plan.iphone_offset}")
    print(f"Canon home timezone fallback: {timezone_plan.canon_home_timezone}")
    print(f"Canon files needing correction: {len(timezone_plan.canon_files)}")
    print(f"Canon filename/folder timestamp shift: {describe_shift(timezone_plan.canon_shift_minutes)}")
    print("")
    print("Apply this correction to Canon files for this run?")
    if not sys.stdin.isatty():
        print("No interactive confirmation available; skipping Canon timezone correction.")
        return False
    choice = input("Type yes to apply: ").strip().lower()
    return choice == "yes"


class ProgressHeartbeat:
    def __init__(self, label: str = "⏳ Still working...", interval: int = 50) -> None:
        self.label = label
        self.interval = interval
        self.count = 0

    def tick(self) -> None:
        self.count += 1
        if self.count % self.interval == 0:
            print(self.label)


def _print_action_heading(title: str) -> None:
    print(cyan(title, bold=True))
    print(cyan("-" * len(title)))
