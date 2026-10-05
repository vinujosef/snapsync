# Rename media in place using snapsync's normalized filename rules.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import re
from collections import Counter

from config.settings import Settings
from snapsync.classifier import UNKNOWN, classify
from snapsync.duplicate import calculate_hash, collision_path
from snapsync.file_fingerprint import file_fingerprint
from snapsync.metadata_reader import read_metadata_batch_or_fallback
from snapsync.renamer import generate_filename
from snapsync.scanner import scan_source
from snapsync.summary import RunSummary
from snapsync.util import logger
from snapsync.util.console import changed_new, changed_old, format_display_date, print_grouped_table


@dataclass(frozen=True)
class RenameChange:
    source_path: Path
    target_path: Path
    old_name: str
    new_name: str
    taken_date: str
    fingerprint: str
    collision: bool
    duplicate: bool = False


def run_media_rename(source_folder: Path, settings: Settings) -> int:
    summary = RunSummary(audit_mode=settings.dry_run, action_label="rename")
    changes: list[RenameChange] = []

    if not _confirm_rename(settings):
        logger.warning("Rename was not confirmed; no files were renamed")
        summary.print()
        return 0

    try:
        candidates = scan_source(source_folder, settings)
        summary.source_files_found = sum(1 for path in source_folder.expanduser().rglob("*") if path.is_file())
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

    hashes: dict[Path, str] = {}
    for path in rename_candidates:
        if classify(path, settings) == UNKNOWN:
            continue
        try:
            hashes[path] = calculate_hash(path)
        except OSError as exc:
            summary.errors += 1
            summary.error_files.append(f"{path} — {exc}")
    counts = Counter(hashes.values())
    summary.identical_groups = sum(count > 1 for count in counts.values())
    normal_names = {
        path: generate_filename(
            metadata_by_path[path].selected_datetime, metadata_by_path[path].device_name,
            digest, path, settings.filename_prefix, settings.hash_length,
        ) for path, digest in hashes.items()
    }
    # Prefer existing normal names, then unlabelled files, then numbered copies.
    rename_candidates.sort(key=lambda path: (
        0 if path.name == normal_names.get(path) else (2 if re.search(r"_copy[0-9]+$", path.stem) else 1),
        int(re.search(r"_copy([0-9]+)$", path.stem).group(1)) if re.search(r"_copy([0-9]+)$", path.stem) else 0,
        metadata_by_path[path].selected_datetime, path.name.lower(), str(path),
    ))
    seen: Counter[str] = Counter()
    reserved: set[Path] = set()
    for source_path in rename_candidates:
        try:
            media_type = classify(source_path, settings)
            if media_type == UNKNOWN:
                summary.unknown_files += 1
                summary.skipped_files.append(f"{source_path} — unsupported file type")
                continue

            summary.media_files_processed += 1
            metadata = metadata_by_path[source_path]
            selected_datetime = metadata.selected_datetime
            if source_path not in hashes:
                continue
            file_hash = hashes[source_path]
            filename = generate_filename(
                selected_datetime,
                metadata.device_name,
                file_hash,
                source_path,
                settings.filename_prefix,
                settings.hash_length,
            )
            duplicate = seen[file_hash] > 0
            if duplicate:
                base = Path(filename)
                filename = f"{base.stem}_copy{seen[file_hash]}{base.suffix}"
            seen[file_hash] += 1
            target_path = _rename_target(source_path, filename)
            if target_path in reserved:
                target_path = _available_target(source_path.with_name(filename), reserved)
            reserved.add(target_path)
            if target_path == source_path:
                summary.already_named += 1
                if duplicate:
                    summary.already_labelled_files.append(str(source_path))
                logger.info(f"Already renamed: {source_path.name}")
                continue

            changes.append(
                RenameChange(
                    source_path=source_path,
                    target_path=target_path,
                    old_name=source_path.name,
                    new_name=target_path.name,
                    taken_date=format_display_date(selected_datetime),
                    fingerprint=file_fingerprint(source_path, metadata),
                    collision=target_path.name != filename,
                    duplicate=duplicate,
                )
            )
            if target_path.name != filename:
                logger.warning(f"Collision handled for {source_path.name}: {target_path.name}")
        except Exception as exc:
            summary.errors += 1
            summary.error_files.append(f"{source_path} — {exc}")
            logger.error(f"Could not rename {source_path.name}: {exc}")

    if changes:
        _print_rename_table(changes)
        print()

    for change in changes:
        if settings.dry_run:
            summary.planned_copies += 1
            if change.duplicate:
                summary.labelled_files.append(f"{change.old_name} → {change.new_name}")
            if change.collision:
                summary.filename_collisions_handled += 1
                summary.conflict_files.append(f"{change.source_path} → {change.target_path}")
            continue
        try:
            change.target_path.parent.mkdir(parents=True, exist_ok=True)
            if change.target_path.exists():
                raise FileExistsError(f"Target already exists: {change.target_path}")
            change.source_path.rename(change.target_path)
            summary.copied_files += 1
            if change.duplicate:
                summary.labelled_files.append(f"{change.old_name} → {change.new_name}")
            if change.collision:
                summary.filename_collisions_handled += 1
                summary.conflict_files.append(f"{change.source_path} → {change.target_path}")
        except Exception as exc:
            summary.errors += 1
            summary.error_files.append(f"{change.source_path} — {exc}")
            logger.error(f"Could not rename {change.old_name}: {exc}")

    summary.print()
    return 0 if summary.errors == 0 else 1


def _available_target(target_path: Path, reserved: set[Path]) -> Path:
    for number in range(1, 10_000):
        candidate = target_path.with_name(f"{target_path.stem}_collision-{number:02d}{target_path.suffix}")
        if not candidate.exists() and candidate not in reserved:
            return candidate
    raise RuntimeError(f"No available filename for {target_path}")


def _rename_target(source_path: Path, filename: str) -> Path:
    target_path = source_path.with_name(filename)
    if target_path == source_path:
        return source_path
    if not target_path.exists():
        return target_path
    return collision_path(target_path)


def _print_rename_table(changes: list[RenameChange]) -> None:
    headers = ["#", "Old name", "New name", "Date", "Fingerprint"]
    rows = [
        [str(index), changed_old(change.old_name), changed_new(change.new_name), change.taken_date, change.fingerprint]
        for index, change in enumerate(changes, start=1)
    ]
    print_grouped_table(headers, rows, [change.taken_date for change in changes])


def _confirm_rename(settings: Settings) -> bool:
    if not sys.stdin.isatty():
        print("No interactive confirmation available; skipping rename.")
        return False

    prompt = "Type yes to preview rename dry-run: " if settings.dry_run else "Type yes to rename files: "
    return input(prompt).strip().lower() == "yes"
