# Coordinate the SyncSnap command-line ingestion flow.
from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))

from config.settings import Settings, get_settings
from syncsnap.classifier import UNKNOWN, classify
from syncsnap.copier import copy_file
from syncsnap.duplicate import build_hash_index, calculate_hash, decide_destination
from syncsnap.metadata import current_date_fallback, extract_metadata
from syncsnap.reports import DuplicateGroup, write_duplicate_groups_report
from syncsnap.renamer import generate_filename
from syncsnap.scanner import scan_source
from syncsnap.summary import RunSummary
from syncsnap.util import logger
from syncsnap.util.paths import build_destination_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy media into a SyncSnap destination folder.")
    parser.add_argument("--dry-run", action="store_true", help="Audit planned work without copying files")
    parser.add_argument("source_folder", nargs="?", help="Folder to scan recursively")
    args = parser.parse_args(argv)

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

    if not args.source_folder and not _confirm_interactive_run(source_folder, settings):
        logger.info("No action selected")
        return 0

    return run_media_copy(source_folder, settings)


def run_media_copy(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run)
    run_started_at = datetime.now()

    try:
        candidates = scan_source(source_folder, settings)
        summary.source_files_found = len(candidates)
        hash_index = build_hash_index(settings.destination_folder)
        run_hash_index: dict[str, Path] = {}
        run_destination_index: dict[str, Path] = {}
        duplicate_groups: dict[str, DuplicateGroup] = {}
    except OSError as exc:
        logger.error(f"Startup failed: {exc}")
        return 1

    logger.info(f"Found {summary.source_files_found} source files")
    if settings.dry_run:
        logger.warning("DRY_RUN is enabled; no files will be copied")

    for source_path in candidates:
        try:
            media_type = classify(source_path, settings)
            if media_type == UNKNOWN:
                summary.unknown_files += 1
            else:
                summary.media_files_processed += 1

            metadata = _safe_metadata(source_path, settings)
            file_hash = calculate_hash(source_path)
            filename = generate_filename(
                metadata.selected_datetime,
                metadata.device_name,
                file_hash,
                source_path,
                settings.filename_prefix,
                settings.hash_length,
            )
            target_path = build_destination_path(
                settings,
                metadata.selected_datetime,
                media_type,
                filename,
            )

            decision = decide_destination(file_hash, target_path, hash_index, run_hash_index)
            if decision.action == "skip":
                summary.duplicate_files_skipped += 1
                if decision.duplicate_kind == "destination":
                    summary.duplicates_already_in_destination += 1
                elif decision.duplicate_kind == "source":
                    summary.duplicates_repeated_in_source += 1
                    group = duplicate_groups.setdefault(
                        file_hash,
                        DuplicateGroup(
                            file_hash=file_hash,
                            kept_source=run_hash_index[file_hash],
                            duplicate_sources=[],
                            destination_path=run_destination_index.get(file_hash),
                        ),
                    )
                    group.duplicate_sources.append(source_path)
                logger.skipped(source_path, decision.reason)
                continue
            if decision.action == "error" or decision.destination is None:
                summary.errors += 1
                logger.error(f"Could not process {source_path}: {decision.reason}")
                continue

            copy_file(source_path, decision.destination, settings.dry_run)
            run_hash_index[file_hash] = source_path
            run_destination_index[file_hash] = decision.destination
            if settings.dry_run:
                summary.planned_copies += 1
            else:
                summary.copied_files += 1
            if decision.collision:
                summary.filename_collisions_handled += 1
                logger.warning(f"Collision handled for {source_path}: {decision.destination}")
            if settings.dry_run:
                logger.info(f"Will copy {source_path} -> {decision.destination}")
            else:
                logger.success(f"Copied {source_path} -> {decision.destination}")
        except Exception as exc:
            summary.errors += 1
            logger.error(f"Could not process {source_path}: {exc}")

    try:
        summary.duplicate_groups_report = write_duplicate_groups_report(
            settings,
            duplicate_groups,
            run_started_at,
        )
        if summary.duplicate_groups_report:
            logger.info(f"Duplicate groups report: {summary.duplicate_groups_report}")
    except OSError as exc:
        summary.errors += 1
        logger.error(f"Could not write duplicate groups report: {exc}")

    summary.print()
    return 0 if summary.errors == 0 else 1


def _safe_metadata(path: Path, settings: Settings):
    try:
        return extract_metadata(path, settings.exiftool_path)
    except Exception as exc:
        logger.warning(f"Metadata fallback for {path}: {exc}")
        try:
            return current_date_fallback()
        except Exception:
            raise exc


def _confirm_interactive_run(source_folder: Path, settings: Settings) -> bool:
    print("SyncSnap")
    print("--------")
    print(f"Source folder: {source_folder}")
    print(f"Destination folder: {settings.destination_folder}")
    print(f"Filename prefix: {settings.filename_prefix or '(none)'}")
    print(f"Filename hash length: {settings.hash_length}")
    print(f"Dry run: {'yes' if settings.dry_run else 'no'}")
    print("")
    print("Choose an action:")
    print("1. Media copy + filename fix")
    print("q. Quit")
    choice = input("> ").strip().lower()
    return choice == "1"


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
