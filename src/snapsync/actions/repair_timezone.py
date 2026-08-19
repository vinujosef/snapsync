# Rename Canon files in-place when their timestamps are still in the home timezone.
from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from snapsync.cli import (
    confirm_timezone_correction,
    print_timezone_repair_skip_message,
)
from snapsync.duplicate import calculate_hash, collision_path
from snapsync.metadata import Metadata
from snapsync.renamer import generate_filename
from snapsync.scanner import scan_source
from snapsync.summary import RunSummary
from snapsync.timezone_sampler import collect_repair_metadata, choose_iphone_timezone
from snapsync.timezone_correction import (
    TimezoneCorrectionPlan,
    apply_timezone_correction,
    build_timezone_correction_plan,
)
from snapsync.util import logger


def run_timezone_repair(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run, action_label="rename")

    try:
        files = scan_source(source_folder, settings)
        summary.source_files_found = len(files)

        metadata_by_path = collect_repair_metadata(files, settings)
        should_continue, iphone_offset = choose_iphone_timezone(metadata_by_path)
        if not should_continue:
            summary.print()
            return 0

        timezone_plan = _build_repair_plan(metadata_by_path, settings, iphone_offset)
        if not timezone_plan:
            print_timezone_repair_skip_message(metadata_by_path, settings)
            summary.print()
            return 0

        summary.files_to_rename = len(timezone_plan.canon_files)
        if not confirm_timezone_correction(timezone_plan):
            logger.warning("Canon timezone repair was not confirmed; no files were renamed")
            summary.print()
            return 0
    except OSError as exc:
        logger.error(f"Startup failed: {exc}")
        return 1

    logger.info(f"Found {summary.source_files_found} source files")
    if settings.dry_run:
        logger.warning("DRY_RUN is enabled; no files will be renamed")

    for source_path in timezone_plan.canon_files:
        _repair_one_file(source_path, metadata_by_path[source_path], timezone_plan, settings, summary)

    summary.print()
    return 0 if summary.errors == 0 else 1


def _build_repair_plan(
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
    iphone_offset: str | None,
) -> TimezoneCorrectionPlan | None:
    return build_timezone_correction_plan(
        metadata_by_path,
        settings,
        iphone_offset=iphone_offset,
        force_canon_home_timezone=True,
    )


def _repair_one_file(
    source_path: Path,
    metadata: Metadata,
    timezone_plan: TimezoneCorrectionPlan,
    settings: Settings,
    summary: RunSummary,
) -> None:
    try:
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
        target_path = source_path.with_name(filename)
        if target_path == source_path:
            summary.duplicate_files_skipped += 1
            logger.skipped(source_path, "filename already matches corrected timestamp")
            return
        if target_path.exists():
            target_path = collision_path(target_path)
            summary.filename_collisions_handled += 1

        if settings.dry_run:
            summary.files_renamed += 1
            logger.info(f"Will rename {_rename_display(source_path, target_path)}")
        else:
            source_path.rename(target_path)
            summary.files_renamed += 1
            logger.success(f"Renamed {_rename_display(source_path, target_path)}")
        summary.media_files_processed += 1
    except Exception as exc:
        summary.errors += 1
        logger.error(f"Could not repair {source_path.name}: {exc}")


def _rename_display(source_path: Path, target_path: Path) -> str:
    return f"{source_path.name} -> {target_path.name}"
