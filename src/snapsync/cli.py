# Print SnapSync's interactive command-line prompts and status messages.
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from config.settings import Settings
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
    print(f"{BLUE}================{RESET}")
    print(f"{BOLD}{BLUE} 🎞️ SnapSync 📤{RESET}")
    print(f"{BLUE}================{RESET}")
    print()
    print(f"{BOLD}{CYAN}Choose an action:{RESET}")
    print(f"{CYAN}-----------------{RESET}")
    print("1️⃣  Media copy + filename fix")
    print("2️⃣  Fix Canon timezone issue in this folder")
    print("q. Quit")

    choice = input("> ").strip().lower()
    if choice == "1":
        return "copy"
    if choice == "2":
        return "repair_timezone"
    return "quit"


def print_action_context(action: str, source_folder: Path, settings: Settings) -> None:
    print()
    if action == "repair_timezone":
        _print_action_heading("FIX CANON TIMEZONE ISSUE:")
        print(f"⬅️➡️ Repair folder: {source_folder}")
        print(f"⏱️ Scope hint: {_last_path_parts(source_folder, 5)}")
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


def print_timezone_repair_noop(metadata_by_path, settings: Settings) -> None:
    diagnostics = diagnose_timezone_correction(
        metadata_by_path,
        settings,
        force_canon_home_timezone=True,
    )
    summary = _timezone_repair_noop_summary(diagnostics.reason)
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
    print(f"{BOLD}{CYAN}{title}{RESET}")
    print(f"{CYAN}{'-' * len(title)}{RESET}")


def _last_path_parts(path: Path, count: int) -> str:
    tail = path.parts[-count:]
    if path.is_absolute():
        return "/" + "/".join(part for part in tail if part != path.anchor)
    return str(Path(*tail))


@dataclass(frozen=True)
class _TimezoneRepairNoopSummary:
    kind: str
    message: str


def _timezone_repair_noop_summary(reason: str) -> _TimezoneRepairNoopSummary:
    # These messages are shown when option 2 has nothing to rename:
    # no Canon files means there are no repair targets; no iPhone timezone means
    # SnapSync cannot know the local trip timezone; mixed iPhone timezones need
    # the earlier user confirmation; invalid Canon home timezone means the
    # configured fallback cannot be used; already-matching files need no change.
    if reason == "No iPhone timezone offsets were found":
        return _TimezoneRepairNoopSummary("warning", "No iPhone timezone sample found; no files renamed")
    if reason == "Multiple iPhone timezone offsets were found":
        return _TimezoneRepairNoopSummary("warning", "Multiple iPhone timezone samples found; no files renamed")
    if reason.startswith("Canon home timezone is invalid"):
        return _TimezoneRepairNoopSummary("warning", "Canon home timezone is invalid; no files renamed")
    if reason == "Canon timezone already matches the iPhone offset":
        return _TimezoneRepairNoopSummary(
            "info",
            "No Canon files available for timezone correction in this folder",
        )
    return _TimezoneRepairNoopSummary("warning", "No Canon timezone correction could be inferred")
