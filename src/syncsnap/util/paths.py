# Build destination paths under DESTINATION_FOLDER.
from __future__ import annotations

import calendar
from datetime import datetime
from pathlib import Path

from config.settings import Settings


def build_destination_folder(settings: Settings, selected_datetime: datetime, media_type: str) -> Path:
    month_name = calendar.month_name[selected_datetime.month]
    month_folder = f"{selected_datetime.month:02d} - {month_name}"
    return (
        settings.destination_folder
        / f"{selected_datetime.year:04d}"
        / month_folder
        / media_type
    )


def build_destination_path(settings: Settings, selected_datetime: datetime, media_type: str, filename: str) -> Path:
    return build_destination_folder(settings, selected_datetime, media_type) / filename
