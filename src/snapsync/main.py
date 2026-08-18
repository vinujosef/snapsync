# Choose and run the SnapSync command-line action.
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))

from config.settings import get_settings
from snapsync.actions.copy_media import run_media_copy
from snapsync.actions.repair_timezone import run_timezone_repair
from snapsync.cli import choose_interactive_action, print_action_context
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

    action = "copy"
    if not args.source_folder:
        action = choose_interactive_action()
        if action == "quit":
            logger.info("No action selected")
            return 0
        print_action_context(action, source_folder, settings)

    if action == "repair_timezone":
        return run_timezone_repair(source_folder, settings)
    return run_media_copy(source_folder, settings)


def _parse_args(argv: list[str] | None):
    parser = argparse.ArgumentParser(description="Copy media into a SnapSync destination folder.")
    parser.add_argument("--dry-run", action="store_true", help="Audit planned work without copying files")
    parser.add_argument("source_folder", nargs="?", help="Folder to scan recursively")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
