# Rename media in place using snapsync's normalized filename rules.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys

from config.settings import Settings
from snapsync.classifier import UNKNOWN, classify
from snapsync.duplicate import calculate_hash, collision_path
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.renamer import generate_filename
from snapsync.scanner import scan_source
from snapsync.summary import RunSummary
from snapsync.util import logger
from snapsync.util.console import format_display_date, format_table_row, table_widths


@dataclass(frozen=True)
class RenameChange:
    source_path: Path
    target_path: Path
    old_name: str
    new_name: str
    taken_date: str
    collision: bool


def run_media_rename(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run, action_label="rename")
    changes: list[RenameChange] = []

    if not _confirm_rename(settings):
        logger.warning("Rename was not confirmed; no files were renamed")
        summary.print()
        return 0

    try:
        candidates = scan_source(source_folder, settings)
        summary.source_files_found = len(candidates)
        metadata_by_path = read_metadata_batch_or_fallback(candidates, settings)
    except OSError as exc:
        logger.error(f"Startup failed: {exc}")
        return 1

    rename_candidates = sorted(
        candidates,
        key=lambda path: (metadata_by_path[path].selected_datetime, path.name.lower()),
    )

    print()
    logger.info(f"Found {summary.source_files_found} source files")
    print()
    if settings.dry_run:
        logger.warning("DRY_RUN is enabled; no files will be renamed")
        print()

    for source_path in rename_candidates:
        try:
            media_type = classify(source_path, settings)
            if media_type == UNKNOWN:
                summary.unknown_files += 1
                continue

            summary.media_files_processed += 1
            metadata = metadata_by_path[source_path]
            selected_datetime = metadata.selected_datetime
            file_hash = calculate_hash(source_path)
            filename = generate_filename(
                selected_datetime,
                metadata.device_name,
                file_hash,
                source_path,
                settings.filename_prefix,
                settings.hash_length,
            )
            target_path = _rename_target(source_path, filename)
            if target_path == source_path:
                logger.info(f"Already renamed: {source_path.name}")
                continue

            changes.append(
                RenameChange(
                    source_path=source_path,
                    target_path=target_path,
                    old_name=source_path.name,
                    new_name=target_path.name,
                    taken_date=format_display_date(selected_datetime),
                    collision=target_path.name != filename,
                )
            )
            if target_path.name != filename:
                summary.filename_collisions_handled += 1
                logger.warning(f"Collision handled for {source_path.name}: {target_path.name}")
        except Exception as exc:
            summary.errors += 1
            logger.error(f"Could not rename {source_path.name}: {exc}")

    if changes:
        _print_rename_table(changes)
        print()

    for change in changes:
        if settings.dry_run:
            summary.planned_copies += 1
            continue
        try:
            change.target_path.parent.mkdir(parents=True, exist_ok=True)
            change.source_path.rename(change.target_path)
            summary.copied_files += 1
        except Exception as exc:
            summary.errors += 1
            logger.error(f"Could not rename {change.old_name}: {exc}")

    summary.print()
    return 0 if summary.errors == 0 else 1


def _rename_target(source_path: Path, filename: str) -> Path:
    target_path = source_path.with_name(filename)
    if target_path == source_path:
        return source_path
    if not target_path.exists():
        return target_path
    return collision_path(target_path)


def _print_rename_table(changes: list[RenameChange]) -> None:
    headers = ["#", "Old name", "New name"]
    rows = [
        [str(index), change.old_name, change.new_name]
        for index, change in enumerate(changes, start=1)
    ]
    widths = table_widths(headers, rows)
    print(format_table_row(headers, widths))
    print(format_table_row(["-" * width for width in widths], widths))
    row_width = len(format_table_row(headers, widths))
    previous_date: str | None = None
    for row in rows:
        change_date = changes[int(row[0]) - 1].taken_date
        if previous_date is not None and change_date != previous_date:
            print("-" * row_width)
        print(format_table_row(row, widths))
        previous_date = change_date


def _confirm_rename(settings: Settings) -> bool:
    if not sys.stdin.isatty():
        print("No interactive confirmation available; skipping rename.")
        return False

    prompt = "Type yes to preview rename dry-run: " if settings.dry_run else "Type yes to rename files: "
    return input(prompt).strip().lower() == "yes"
