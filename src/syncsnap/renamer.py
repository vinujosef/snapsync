# Generate normalized destination filenames.
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


def generate_filename(
    selected_datetime: datetime,
    device_name: str | None,
    file_hash: str,
    original_path: Path,
    filename_prefix: str = "",
    hash_length: int = 12,
) -> str:
    timestamp = selected_datetime.strftime("%Y-%m-%d_%H%M%S")
    device = sanitize_device_name(device_name)
    prefix = sanitize_prefix(filename_prefix)
    extension = original_path.suffix.lower()
    stem = f"{timestamp}_{device}_{file_hash[:hash_length].lower()}"
    if prefix:
        stem = f"{prefix}_{stem}"
    return f"{stem}{extension}"


def sanitize_device_name(device_name: str | None) -> str:
    value = (device_name or "UnknownDevice").strip()
    value = re.sub(r"[^A-Za-z0-9]+", "", value)
    return value or "UnknownDevice"


def sanitize_prefix(filename_prefix: str | None) -> str:
    value = (filename_prefix or "").strip()
    value = re.sub(r"[^A-Za-z0-9_-]+", "", value)
    return value.strip("_-")
