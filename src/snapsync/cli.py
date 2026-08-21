# Print snapsync's interactive command-line prompts and status messages.
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings
from snapsync.constants import (
    ACTION_AUDIT_FOLDER,
    ACTION_COPY,
    ACTION_QUIT,
    ACTION_REPAIR_TIMEZONE,
)
from snapsync.timezone_correction import (
    TimezoneCorrectionPlan,
    describe_shift,
    diagnose_timezone_correction,
)


RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[34m"
CYAN = "\033[36m"


def choose_interactive_action() -> str:
    print(blue("================"))
    print(blue(" 🎞️ snapsync 📤", bold=True))
    print(blue("================"))
    print()
    print(cyan("Choose an action:", bold=True))
    print(cyan("-----------------"))
    print("1️⃣  Media copy + filename fix")
    print("2️⃣  Fix Canon timezone issue in this folder")
    print("3️⃣  Audit files in this folder")
    print("q. Quit")

    choice = input("> ").strip().lower()
    if choice == "1":
        return ACTION_COPY
    if choice == "2":
        return ACTION_REPAIR_TIMEZONE
    if choice == "3":
        return ACTION_AUDIT_FOLDER
    return ACTION_QUIT


def print_action_context(action: str, source_folder: Path, settings: Settings) -> None:
    print()
    if action == ACTION_REPAIR_TIMEZONE:
        _print_action_heading("FIX CANON TIMEZONE ISSUE:")
        print(f"⬅️➡️ Repair folder: {source_folder}")
        print(f"⏱️ Scope hint: {_last_path_parts(source_folder, 5)}")
    elif action == ACTION_AUDIT_FOLDER:
        _print_action_heading("AUDIT FILES IN THIS FOLDER:")
        print(f"🔎 Source folder: {source_folder}")
    else:
        _print_action_heading("COPY MEDIA + FILENAME FIX:")
        print(f"➡️ Source folder: {source_folder}")
        print(f"⬅️ Copy destination folder: {settings.destination_folder}")
        print(f"🧾 Filename prefix: {settings.filename_prefix or '(none)'}")
        print(f"#️⃣ Filename hash length: {settings.hash_length}")
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


def print_timezone_repair_skip_message(metadata_by_path, settings: Settings) -> None:
    diagnostics = diagnose_timezone_correction(
        metadata_by_path,
        settings,
        force_canon_home_timezone=True,
    )
    summary = repair_skip_message(diagnostics.reason)
    symbol = "⚠️" if summary.kind == "warning" else "ℹ️"
    print()
    print(f"{symbol}  {summary.message}")


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


def blue(text: str, *, bold: bool = False) -> str:
    return _color(text, BLUE, bold)


def cyan(text: str, *, bold: bool = False) -> str:
    return _color(text, CYAN, bold)


def _color(text: str, color: str, bold: bool) -> str:
    prefix = f"{BOLD}{color}" if bold else color
    return f"{prefix}{text}{RESET}"


def _last_path_parts(path: Path, count: int) -> str:
    tail = path.parts[-count:]
    if path.is_absolute():
        return "/" + "/".join(part for part in tail if part != path.anchor)
    return str(Path(*tail))


@dataclass(frozen=True)
class RepairSkipMessage:
    kind: str
    message: str


def repair_skip_message(reason: str) -> RepairSkipMessage:
    # These messages are shown when option 2 has nothing to rename:
    # no Canon files means there are no repair targets; no iPhone timezone means
    # snapsync cannot know the local trip timezone; mixed iPhone timezones need
    # the earlier user confirmation; invalid Canon home timezone means the
    # configured fallback cannot be used; already-matching files need no change.
    if reason == "No iPhone timezone offsets were found":
        return RepairSkipMessage("warning", "No iPhone timezone sample found; no files renamed")
    if reason == "Multiple iPhone timezone offsets were found":
        return RepairSkipMessage("warning", "Multiple iPhone timezone samples found; no files renamed")
    if reason.startswith("Canon home timezone is invalid"):
        return RepairSkipMessage("warning", "Canon home timezone is invalid; no files renamed")
    if reason == "Canon timezone already matches the iPhone offset":
        return RepairSkipMessage(
            "info",
            "No Canon files available for timezone correction in this folder",
        )
    return RepairSkipMessage("warning", "No Canon timezone correction could be inferred")
