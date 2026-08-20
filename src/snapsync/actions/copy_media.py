# Copy media into the configured snapsync destination folder.
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config.settings import Settings
from snapsync.classifier import UNKNOWN, classify
from snapsync.cli import confirm_timezone_correction
from snapsync.copier import copy_file
from snapsync.duplicate import build_hash_index, calculate_hash, decide_destination
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.reports import DuplicateGroup, write_duplicate_groups_report
from snapsync.renamer import generate_filename
from snapsync.scanner import scan_source
from snapsync.summary import RunSummary
from snapsync.timezone_correction import apply_timezone_correction, build_timezone_correction_plan
from snapsync.util import logger
from snapsync.util.paths import build_destination_path


def run_media_copy(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run)
    run_started_at = datetime.now()

    try:
        candidates = scan_source(source_folder, settings)
        summary.source_files_found = len(candidates)
        metadata_by_path = read_metadata_batch_or_fallback(candidates, settings)
        timezone_plan = build_timezone_correction_plan(metadata_by_path, settings)
        if timezone_plan and not confirm_timezone_correction(timezone_plan):
            logger.warning("Canon timezone correction was not confirmed; Canon timestamps are unchanged")
            timezone_plan = None
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

            metadata = metadata_by_path[source_path]
            selected_datetime = apply_timezone_correction(metadata, timezone_plan)
            file_hash = calculate_hash(source_path)
            filename = generate_filename(
                selected_datetime,
                metadata.device_name,
                file_hash,
                source_path,
                settings.filename_prefix,
                settings.hash_length,
            )
            target_path = build_destination_path(settings, selected_datetime, media_type, filename)

            decision = decide_destination(file_hash, target_path, hash_index, run_hash_index)
            if decision.action == "skip":
                _record_skipped_duplicate(
                    decision.duplicate_kind,
                    file_hash,
                    source_path,
                    run_hash_index,
                    run_destination_index,
                    duplicate_groups,
                    summary,
                )
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
                logger.info(f"Will copy {source_path} -> {decision.destination}")
            else:
                summary.copied_files += 1
                logger.success(f"Copied {source_path} -> {decision.destination}")
            if decision.collision:
                summary.filename_collisions_handled += 1
                logger.warning(f"Collision handled for {source_path}: {decision.destination}")
        except Exception as exc:
            summary.errors += 1
            logger.error(f"Could not process {source_path}: {exc}")

    _write_duplicate_report(settings, duplicate_groups, run_started_at, summary)
    summary.print()
    return 0 if summary.errors == 0 else 1


def _record_skipped_duplicate(
    duplicate_kind: str | None,
    file_hash: str,
    source_path: Path,
    run_hash_index: dict[str, Path],
    run_destination_index: dict[str, Path],
    duplicate_groups: dict[str, DuplicateGroup],
    summary: RunSummary,
) -> None:
    summary.duplicate_files_skipped += 1
    if duplicate_kind == "destination":
        summary.duplicates_already_in_destination += 1
        return
    if duplicate_kind != "source":
        return

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


def _write_duplicate_report(
    settings: Settings,
    duplicate_groups: dict[str, DuplicateGroup],
    run_started_at: datetime,
    summary: RunSummary,
) -> None:
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
