# Copy files safely without moving or overwriting originals.
from __future__ import annotations

import shutil
from pathlib import Path


def copy_file(source: Path, destination: Path, dry_run: bool = False) -> None:
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")

    if dry_run:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
