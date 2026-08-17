# Coordinate the SyncSnap command-line ingestion flow.
from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
import random

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(project_root))
    sys.path.insert(0, str(project_root / "src"))

from config.settings import Settings, get_settings
from syncsnap.classifier import UNKNOWN, classify
from syncsnap.copier import copy_file
from syncsnap.duplicate import build_hash_index, calculate_hash, collision_path, decide_destination
from syncsnap.metadata import Metadata, current_date_fallback, extract_metadata
from syncsnap.reports import DuplicateGroup, write_duplicate_groups_report
from syncsnap.renamer import generate_filename
from syncsnap.scanner import scan_source
from syncsnap.summary import RunSummary
from syncsnap.timezone_correction import (
    TimezoneCorrectionPlan,
    apply_timezone_correction,
    build_timezone_correction_plan,
    diagnose_timezone_correction,
    describe_shift,
)
from syncsnap.util import logger
from syncsnap.util.paths import build_destination_path


RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[34m"
CYAN = "\033[36m"


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

    if not args.source_folder:
        action = _choose_interactive_action(source_folder, settings)
        if action == "repair_timezone":
            _print_action_context(action, source_folder, settings)
            return run_timezone_repair(source_folder, settings)
        if action != "copy":
            logger.info("No action selected")
            return 0
        _print_action_context(action, source_folder, settings)

    return run_media_copy(source_folder, settings)


def run_media_copy(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run)
    run_started_at = datetime.now()

    try:
        candidates = scan_source(source_folder, settings)
        summary.source_files_found = len(candidates)
        metadata_by_path = {path: _safe_metadata(path, settings) for path in candidates}
        timezone_plan = build_timezone_correction_plan(metadata_by_path, settings)
        if timezone_plan and not _confirm_timezone_correction(timezone_plan):
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
            target_path = build_destination_path(
                settings,
                selected_datetime,
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
            _log_timezone_repair_noop(metadata_by_path, settings)
            summary.print()
            return 0
        summary.canon_files_found = len(timezone_plan.canon_files)
        if not _confirm_timezone_correction(timezone_plan):
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
        try:
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
            target_path = source_path.with_name(filename)
            if target_path == source_path:
                summary.duplicate_files_skipped += 1
                logger.skipped(source_path, "filename already matches corrected timestamp")
                continue
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


def _metadata_for_timezone_repair(candidates: list[Path], settings: Settings) -> dict[Path, Metadata]:
    likely_iphone_paths = [path for path in candidates if "iphone" in path.name.lower()]
    likely_canon_paths = [path for path in candidates if "canon" in path.name.lower()]
    metadata_by_path: dict[Path, Metadata] = {}
    progress = _ProgressHeartbeat("⏳ Still working...", interval=50)

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
            metadata = _safe_metadata(path, settings)
            metadata_by_path[path] = metadata
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


def _sampled_iphone_offsets(metadata_by_path: dict[Path, Metadata]) -> list[str]:
    return [
        metadata.timezone_offset
        for metadata in metadata_by_path.values()
        if _is_iphone_metadata(metadata) and metadata.timezone_offset
    ][:5]


def _is_iphone_metadata(metadata: Metadata) -> bool:
    return "iphone" in metadata.device_name.lower()


def _is_canon_metadata(metadata: Metadata) -> bool:
    return "canon" in metadata.device_name.lower()


def _has_iphone_filename_hint(path: Path) -> bool:
    return "iphone" in path.name.lower()


def _rename_display(source_path: Path, target_path: Path) -> str:
    return f"{source_path.name} -> {target_path.name}"


class _ProgressHeartbeat:
    def __init__(self, label: str, interval: int) -> None:
        self.label = label
        self.interval = interval
        self.count = 0

    def tick(self) -> None:
        self.count += 1
        if self.count % self.interval == 0:
            print(self.label)


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


def _choose_interactive_action(source_folder: Path, settings: Settings) -> str:
    print(f"{BLUE}================{RESET}")
    print(f"{BOLD}{BLUE} 🎞️ SyncSnap 📤{RESET}")
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


def _print_action_context(action: str, source_folder: Path, settings: Settings) -> None:
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


def _print_action_heading(title: str) -> None:
    print(f"{BOLD}{CYAN}{title}{RESET}")
    print(f"{CYAN}{'-' * len(title)}{RESET}")


def _last_path_parts(path: Path, count: int) -> str:
    tail = path.parts[-count:]
    if path.is_absolute():
        return "/" + "/".join(part for part in tail if part != path.anchor)
    return str(Path(*tail))


def _confirm_timezone_correction(timezone_plan: TimezoneCorrectionPlan) -> bool:
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


def _log_timezone_diagnostics(
    metadata_by_path: dict[Path, Metadata],
    settings: Settings,
    *,
    force_canon_home_timezone: bool = False,
) -> None:
    diagnostics = diagnose_timezone_correction(
        metadata_by_path,
        settings,
        force_canon_home_timezone=force_canon_home_timezone,
    )
    logger.info("Timezone scan diagnostics:")
    logger.info(f"  iPhone files with timezone offset: {diagnostics.iphone_files_with_offset}")
    if diagnostics.iphone_offsets:
        offsets = ", ".join(
            f"{offset} ({count})" for offset, count in diagnostics.iphone_offsets
        )
        logger.info(f"  iPhone offsets found: {offsets}")
    else:
        logger.info("  iPhone offsets found: none")
    logger.info(f"  Canon files without timezone metadata: {diagnostics.canon_files_without_offset}")
    logger.info(f"  Canon files with timezone metadata: {diagnostics.canon_files_with_offset}")
    logger.info(f"  Canon files needing correction: {diagnostics.canon_files_needing_correction}")
    logger.info(f"  Reason: {diagnostics.reason}")


def _log_timezone_repair_noop(metadata_by_path: dict[Path, Metadata], settings: Settings) -> None:
    diagnostics = diagnose_timezone_correction(
        metadata_by_path,
        settings,
        force_canon_home_timezone=True,
    )
    summary = _timezone_repair_noop_summary(diagnostics.reason)
    symbol = "⚠️" if summary.kind == "warning" else "ℹ️"
    print()
    print(f"{symbol}  {summary.message}")


@dataclass(frozen=True)
class _TimezoneRepairNoopSummary:
    kind: str
    message: str


def _timezone_repair_noop_summary(reason: str) -> _TimezoneRepairNoopSummary:
    # These messages are shown when option 2 has nothing to rename:
    # no Canon files means there are no repair targets; no iPhone timezone means
    # SyncSnap cannot know the local trip timezone; mixed iPhone timezones need
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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
