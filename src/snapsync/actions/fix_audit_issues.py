# Repair selected audit issues in the current snapsync source folder.
from __future__ import annotations

import sys
from pathlib import Path

from config.settings import Settings
from snapsync.actions.fix_audit_issues_finder import timezone_fixes, unknown_device_files
from snapsync.actions.fix_audit_issues_prompts import (
    print_issue_menu,
    run_batch_metadata_repair,
    run_bulk_metadata_fix,
    run_manual_file_fix,
    run_timezone_offset_fix,
    run_unknown_device_fix,
)
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.scanner import scan_source
from snapsync.util import logger


def run_audit_issue_fix(source_folder: Path, settings: Settings) -> int:
    try:
        candidates = scan_source(source_folder, settings)
        metadata_by_path = read_metadata_batch_or_fallback(candidates, settings)
    except OSError as exc:
        logger.error(f"Audit issue fix failed: {exc}")
        return 1

    # Build the issue lists first. The menu only shows counts, so this step
    # does not change any files.
    timezone_fix_list = timezone_fixes(candidates, metadata_by_path)
    unknown_device_file_list = unknown_device_files(candidates, metadata_by_path)
    print_issue_menu(len(timezone_fix_list), len(unknown_device_file_list), len(candidates))

    if not sys.stdin.isatty():
        print("No interactive input available; no audit issues fixed.")
        return 0

    choice = input("> ").strip().lower()
    if choice == "1":
        return run_timezone_offset_fix(timezone_fix_list, settings)
    if choice == "2":
        return run_unknown_device_fix(unknown_device_file_list, settings)
    if choice == "3":
        return run_manual_file_fix(source_folder, candidates, metadata_by_path, settings)
    if choice == "4":
        return run_bulk_metadata_fix(candidates, metadata_by_path, settings)
    if choice == "5":
        return run_batch_metadata_repair(candidates, metadata_by_path, settings)

    logger.info("No audit issue fix selected")
    return 0
