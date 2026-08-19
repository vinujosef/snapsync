# Read metadata, falling back when ExifTool cannot read a file.
from __future__ import annotations

from pathlib import Path

from config.settings import Settings
from snapsync.metadata import current_date_fallback, extract_metadata
from snapsync.util import logger


def read_metadata_or_fallback(path: Path, settings: Settings):
    try:
        return extract_metadata(path, settings.exiftool_path)
    except Exception as exc:
        logger.warning(f"Metadata fallback for {path}: {exc}")
        try:
            return current_date_fallback()
        except Exception:
            raise exc
