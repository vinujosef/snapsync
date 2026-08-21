# Choose and run the snapsync command-line action.
from __future__ import annotations

import argparse
import sys
from time import perf_counter
from dataclasses import replace
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))

from config.settings import get_settings
from snapsync.actions.audit_folder import run_folder_audit
from snapsync.actions.copy_media import run_media_copy
from snapsync.actions.fix_audit_issues import run_audit_issue_fix
from snapsync.actions.repair_timezone import run_timezone_repair
from snapsync.cli import choose_interactive_action, print_action_context
from snapsync.constants import (
    ACTION_AUDIT_FOLDER,
    ACTION_COPY,
    ACTION_FIX_AUDIT_ISSUES,
    ACTION_QUIT,
    ACTION_REPAIR_TIMEZONE,
)
from snapsync.util import logger


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    try:
        settings = get_settings()
        if args.dry_run:
            settings = replace(settings, dry_run=True)
        logger.configure(settings.log_level)

        source_folder = Path(args.source_folder).expanduser() if args.source_folder else Path.cwd()
        if not source_folder.is_dir():
            raise ValueError(f"Source folder does not exist or is not a directory: {source_folder}")
    except ValueError as exc:
        logger.error(str(exc))
        return 2

    action = ACTION_COPY
    if not args.source_folder:
        action = choose_interactive_action()
        if action == ACTION_QUIT:
            logger.info("No action selected")
            return 0
        print_action_context(action, source_folder, settings)

    started_at = perf_counter()
    if action == ACTION_REPAIR_TIMEZONE:
        exit_code = run_timezone_repair(source_folder, settings)
    elif action == ACTION_AUDIT_FOLDER:
        exit_code = run_folder_audit(source_folder, settings)
    elif action == ACTION_FIX_AUDIT_ISSUES:
        exit_code = run_audit_issue_fix(source_folder, settings)
    else:
        exit_code = run_media_copy(source_folder, settings)
    print(f"Run time: {_format_duration(perf_counter() - started_at)}")
    return exit_code


def _parse_args(argv: list[str] | None):
    parser = argparse.ArgumentParser(description="Copy media into a snapsync destination folder.")
    parser.add_argument("--dry-run", action="store_true", help="Audit planned work without copying files")
    parser.add_argument("source_folder", nargs="?", help="Folder to scan recursively")
    return parser.parse_args(argv)


def _format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f}s"

    minutes, remaining_seconds = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {remaining_seconds:.2f}s"

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(remaining_minutes)}m {remaining_seconds:.2f}s"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
