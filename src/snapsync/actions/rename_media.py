# Rename media in place using snapsync's normalized filename rules.
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config.settings import Settings
from snapsync.classifier import UNKNOWN, classify
from snapsync.cli import confirm_timezone_correction
from snapsync.duplicate import calculate_hash, collision_path
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.renamer import generate_filename
from snapsync.scanner import scan_source
from snapsync.summary import RunSummary
from snapsync.timezone_correction import apply_timezone_correction, build_timezone_correction_plan
from snapsync.util import logger


def run_media_rename(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run, action_label="rename")

    try:
        candidates = scan_source(source_folder, settings)
        summary.source_files_found = len(candidates)
        metadata_by_path = read_metadata_batch_or_fallback(candidates, settings)
        timezone_plan = build_timezone_correction_plan(metadata_by_path, settings)
        if timezone_plan and not confirm_timezone_correction(timezone_plan):
            logger.warning("Canon timezone correction was not confirmed; Canon timestamps are unchanged")
            timezone_plan = None
    except OSError as exc:
        logger.error(f"Startup failed: {exc}")
        return 1

    logger.info(f"Found {summary.source_files_found} source files")
    if settings.dry_run:
        logger.warning("DRY_RUN is enabled; no files will be renamed")

    for source_path in candidates:
        try:
            media_type = classify(source_path, settings)
            if media_type == UNKNOWN:
                summary.unknown_files += 1
                continue

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
            target_path = _rename_target(source_path, filename)
            if target_path == source_path:
                logger.info(f"Already renamed: {source_path.name}")
                continue

            if settings.dry_run:
                summary.planned_copies += 1
                logger.info(f"Will rename {source_path} -> {target_path}")
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.rename(target_path)
                summary.copied_files += 1
                logger.success(f"Renamed {source_path} -> {target_path}")
            if target_path.name != filename:
                summary.filename_collisions_handled += 1
                logger.warning(f"Collision handled for {source_path}: {target_path}")
        except Exception as exc:
            summary.errors += 1
            logger.error(f"Could not rename {source_path}: {exc}")

    summary.print()
    return 0 if summary.errors == 0 else 1


def _rename_target(source_path: Path, filename: str) -> Path:
    target_path = source_path.with_name(filename)
    if target_path == source_path:
        return source_path
    if not target_path.exists():
        return target_path
    return collision_path(target_path)
