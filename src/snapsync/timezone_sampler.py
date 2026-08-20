# Collect just enough metadata to choose a folder timezone quickly.
from __future__ import annotations

from collections import Counter
from pathlib import Path
import random
import sys

from config.settings import Settings
from snapsync.cli import ProgressHeartbeat
from snapsync.metadata import Metadata
from snapsync.metadata_reader import read_metadata_or_fallback


IPHONE_SAMPLE_SIZE = 5


def collect_repair_metadata(candidates: list[Path], settings: Settings) -> dict[Path, Metadata]:
    likely_iphone_paths = [path for path in candidates if _looks_like_iphone(path)]
    likely_canon_paths = [path for path in candidates if _looks_like_canon(path)]
    metadata_by_path: dict[Path, Metadata] = {}
    progress = ProgressHeartbeat()

    for path in _stable_sample(likely_iphone_paths, IPHONE_SAMPLE_SIZE):
        _read_one(path, settings, metadata_by_path, progress)

    for path in likely_canon_paths:
        _read_one(path, settings, metadata_by_path, progress)

    remaining_paths = [path for path in candidates if path not in metadata_by_path]
    if likely_canon_paths:
        _read_paths(
            remaining_paths,
            settings,
            metadata_by_path,
            progress,
            stop_when_iphone_sample_is_full=True,
        )
    else:
        _read_paths(remaining_paths, settings, metadata_by_path, progress)

    return metadata_by_path


def choose_iphone_timezone(metadata_by_path: dict[Path, Metadata]) -> tuple[bool, str | None]:
    offset_counts = Counter(sampled_iphone_offsets(metadata_by_path))
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


def sampled_iphone_offsets(metadata_by_path: dict[Path, Metadata]) -> list[str]:
    return [
        metadata.timezone_offset
        for metadata in metadata_by_path.values()
        if _is_iphone_metadata(metadata) and metadata.timezone_offset
    ][:IPHONE_SAMPLE_SIZE]


def _read_paths(
    paths: list[Path],
    settings: Settings,
    metadata_by_path: dict[Path, Metadata],
    progress: ProgressHeartbeat,
    *,
    stop_when_iphone_sample_is_full: bool = False,
) -> None:
    for path in _stable_shuffle(paths):
        if _looks_like_iphone(path) and len(sampled_iphone_offsets(metadata_by_path)) >= IPHONE_SAMPLE_SIZE:
            continue
        _read_one(path, settings, metadata_by_path, progress)
        if stop_when_iphone_sample_is_full and len(sampled_iphone_offsets(metadata_by_path)) >= IPHONE_SAMPLE_SIZE:
            break


def _read_one(
    path: Path,
    settings: Settings,
    metadata_by_path: dict[Path, Metadata],
    progress: ProgressHeartbeat,
) -> None:
    if path in metadata_by_path:
        return
    progress.tick()
    metadata_by_path[path] = read_metadata_or_fallback(path, settings)


def _is_iphone_metadata(metadata: Metadata) -> bool:
    return "iphone" in metadata.device_name.lower()


def _looks_like_iphone(path: Path) -> bool:
    return "iphone" in path.name.lower()


def _looks_like_canon(path: Path) -> bool:
    return "canon" in path.name.lower()


def _stable_sample(paths: list[Path], sample_size: int) -> list[Path]:
    if len(paths) <= sample_size:
        return sorted(paths)
    return _rng_for_paths(paths).sample(sorted(paths), sample_size)


def _stable_shuffle(paths: list[Path]) -> list[Path]:
    shuffled_paths = sorted(paths)
    _rng_for_paths(paths).shuffle(shuffled_paths)
    return shuffled_paths


def _rng_for_paths(paths: list[Path]) -> random.Random:
    seed = "|".join(str(path) for path in sorted(paths))
    return random.Random(seed)
