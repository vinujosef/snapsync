# Choose the safe metadata reading strategy.
# Current order: batch read, single-file fallback, current-date fallback.
# Keep this in sync with docs/decisions/003-metadata-priority.md.
from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from snapsync.metadata import Metadata, current_date_fallback, extract_metadata, extract_metadata_batch
from snapsync.util import logger


DEFAULT_BATCH_SIZE = 100


def read_metadata_or_fallback(path: Path, settings: Settings):
    try:
        return extract_metadata(path, settings.exiftool_path)
    except Exception as exc:
        logger.warning(f"Metadata fallback for {path}: {exc}")
        try:
            return current_date_fallback()
        except Exception:
            raise exc


def read_metadata_batch_or_fallback(
    paths: list[Path],
    settings: Settings,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[Path, Metadata]:
    metadata_by_path: dict[Path, Metadata] = {}

    for batch in _chunks(paths, batch_size):
        try:
            metadata_by_path.update(extract_metadata_batch(batch, settings.exiftool_path))
        except Exception as exc:
            logger.warning(f"Batch metadata fallback for {len(batch)} files: {exc}")

        for path in batch:
            if path not in metadata_by_path:
                metadata_by_path[path] = read_metadata_or_fallback(path, settings)

    return metadata_by_path


def _chunks(paths: list[Path], size: int) -> list[list[Path]]:
    return [paths[index:index + size] for index in range(0, len(paths), size)]
