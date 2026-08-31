# Build compact file fingerprints for manual duplicate spotting.
from __future__ import annotations

from pathlib import Path

from snapsync.metadata import Metadata
from snapsync.util.console import muted


def file_fingerprint(path: Path, metadata: Metadata) -> str:
    return muted(
        " ".join(
            [
                _format_size(path),
                _format_resolution(metadata),
                metadata.selected_datetime.strftime("%H:%M:%S"),
            ]
        )
    )


def _format_size(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "size?"

    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _format_resolution(metadata: Metadata) -> str:
    if metadata.image_width is None or metadata.image_height is None:
        return "res?"
    return f"{metadata.image_width}x{metadata.image_height}"
