# Rename Canon files in-place when their timestamps are still in the home timezone.
from __future__ import annotations

from collections import Counter
from pathlib import Path
import random
import sys

from config.settings import Settings
from snapsync.cli import (
    ProgressHeartbeat,
    confirm_timezone_correction,
    print_timezone_repair_noop,
)
from snapsync.duplicate import calculate_hash, collision_path
from snapsync.metadata import Metadata, current_date_fallback, extract_metadata
from snapsync.renamer import generate_filename
from snapsync.scanner import scan_source
from snapsync.summary import RunSummary
from snapsync.timezone_correction import (
    TimezoneCorrectionPlan,
    apply_timezone_correction,
    build_timezone_correction_plan,
)
from snapsync.util import logger


def run_timezone_repair(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run, action_label="rename")

    try:
        candidates = scan_source(source_folder, settings)
        summary.source_files_found = len(candidates)
        metadata_by_path = _metadata_for_timezone_repair(candidates, settings)
        should_continue, iphone_offset = _select_iphone_offset_for_run(metadata_by_path)
        if not should_continue:
            summary.print()
            return 0

        timezone_plan = build_timezone_correction_plan(
            metadata_by_path,
            settings,
            iphone_offset=iphone_offset,
            force_canon_home_timezone=True,
        )
        if not timezone_plan:
            print_timezone_repair_noop(metadata_by_path, settings)
            summary.print()
            return 0

        summary.canon_files_found = len(timezone_plan.canon_files)
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
            summary.planned_copies += 1
            logger.info(f"Will rename {_rename_display(source_path, target_path)}")
        else:
            source_path.rename(target_path)
            summary.copied_files += 1
            logger.success(f"Renamed {_rename_display(source_path, target_path)}")
        summary.media_files_processed += 1
    except Exception as exc:
        summary.errors += 1
        logger.error(f"Could not repair {source_path.name}: {exc}")


def _metadata_for_timezone_repair(candidates: list[Path], settings: Settings) -> dict[Path, Metadata]:
    likely_iphone_paths = [path for path in candidates if "iphone" in path.name.lower()]
    likely_canon_paths = [path for path in candidates if "canon" in path.name.lower()]
    metadata_by_path: dict[Path, Metadata] = {}
    progress = ProgressHeartbeat()

    for path in _stable_sample_paths(likely_iphone_paths, 5):
        progress.tick()
        metadata_by_path[path] = _safe_metadata(path, settings)

    for path in likely_canon_paths:
        if path not in metadata_by_path:
            progress.tick()
            metadata_by_path[path] = _safe_metadata(path, settings)

    fallback_paths = [path for path in candidates if path not in metadata_by_path]
    if likely_canon_paths:
        for path in _stable_shuffled_paths(fallback_paths):
            if _has_iphone_filename_hint(path) and len(_sampled_iphone_offsets(metadata_by_path)) >= 5:
                continue
            progress.tick()
            metadata_by_path[path] = _safe_metadata(path, settings)
            if len(_sampled_iphone_offsets(metadata_by_path)) >= 5:
                break
        return metadata_by_path

    for path in _stable_shuffled_paths(fallback_paths):
        if _has_iphone_filename_hint(path) and len(_sampled_iphone_offsets(metadata_by_path)) >= 5:
            continue
        progress.tick()
        metadata_by_path[path] = _safe_metadata(path, settings)

    return metadata_by_path


def _select_iphone_offset_for_run(metadata_by_path: dict[Path, Metadata]) -> tuple[bool, str | None]:
    offset_counts = Counter(_sampled_iphone_offsets(metadata_by_path))
    if len(offset_counts) <= 1:
        return True, next(iter(offset_counts), None)

    print()
    print("Multiple iPhone timezone offsets found in the sample:")
    for offset, count in sorted(offset_counts.items()):
        print(f"- {offset}: {count}")

    selected_offset = offset_counts.most_common(1)[0][0]
    print()
    print(f"Continue using {selected_offset} for Canon timezone repair?")
    if not sys.stdin.isatty():
        print("No interactive confirmation available; skipping Canon timezone repair.")
        return False, None
    choice = input("Type yes to continue: ").strip().lower()
    return choice == "yes", selected_offset


def _safe_metadata(path: Path, settings: Settings):
    try:
        return extract_metadata(path, settings.exiftool_path)
    except Exception as exc:
        logger.warning(f"Metadata fallback for {path}: {exc}")
        try:
            return current_date_fallback()
        except Exception:
            raise exc


def _sampled_iphone_offsets(metadata_by_path: dict[Path, Metadata]) -> list[str]:
    return [
        metadata.timezone_offset
        for metadata in metadata_by_path.values()
        if _is_iphone_metadata(metadata) and metadata.timezone_offset
    ][:5]


def _is_iphone_metadata(metadata: Metadata) -> bool:
    return "iphone" in metadata.device_name.lower()


def _has_iphone_filename_hint(path: Path) -> bool:
    return "iphone" in path.name.lower()


def _rename_display(source_path: Path, target_path: Path) -> str:
    return f"{source_path.name} -> {target_path.name}"


def _stable_sample_paths(paths: list[Path], sample_size: int) -> list[Path]:
    if len(paths) <= sample_size:
        return sorted(paths)
    ordered_paths = sorted(paths)
    seed = "|".join(str(path) for path in ordered_paths)
    rng = random.Random(seed)
    return rng.sample(ordered_paths, sample_size)


def _stable_shuffled_paths(paths: list[Path]) -> list[Path]:
    ordered_paths = sorted(paths)
    seed = "|".join(str(path) for path in ordered_paths)
    rng = random.Random(seed)
    rng.shuffle(ordered_paths)
    return ordered_paths
