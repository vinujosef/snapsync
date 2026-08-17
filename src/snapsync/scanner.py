# Recursively scan source folders for candidate files.
from __future__ import annotations

from pathlib import Path

from config.settings import Settings


def scan_source(source_folder: Path, settings: Settings) -> list[Path]:
    source_folder = source_folder.expanduser()
    candidates: list[Path] = []

    for path in source_folder.rglob("*"):
        if _is_ignored(path, source_folder, settings.ignored_folders):
            continue
        if path.is_file():
            candidates.append(path)

    return sorted(candidates)


def _is_ignored(path: Path, source_folder: Path, ignored_folders: frozenset[str]) -> bool:
    try:
        relative_parts = path.relative_to(source_folder).parts
    except ValueError:
        relative_parts = path.parts

    if path.is_file() and path.name.startswith("."):
        return True
    if path.is_file() and path.name.lower() in {"thumbs.db", "desktop.ini"}:
        return True

    for part in relative_parts[:-1] if path.is_file() else relative_parts:
        if part.startswith(".") or part in ignored_folders:
            return True
    return False
