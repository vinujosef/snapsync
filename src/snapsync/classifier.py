# Classify files as photo, video, or unknown by extension.
from __future__ import annotations

from pathlib import Path

from config.settings import Settings


PHOTO = "photo"
VIDEO = "video"
UNKNOWN = "unknown"


def classify(path: Path, settings: Settings) -> str:
    extension = path.suffix.lower().lstrip(".")
    if extension in settings.allowed_photo_extensions:
        return PHOTO
    if extension in settings.allowed_video_extensions:
        return VIDEO
    return UNKNOWN
