# Detect duplicates by hash and preserve filename collisions.
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DestinationDecision:
    action: str
    destination: Path | None
    reason: str = ""
    collision: bool = False
    duplicate_kind: str = ""


def calculate_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_hash_index(destination_index_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not destination_index_root.exists():
        return index

    for path in destination_index_root.rglob("*"):
        if not path.is_file() or _is_system_file(path):
            continue
        try:
            file_hash = calculate_hash(path)
        except OSError:
            continue
        index.setdefault(file_hash, path)
    return index


def decide_destination(
    file_hash: str,
    target_path: Path,
    destination_hash_index: dict[str, Path],
    run_hash_index: dict[str, Path] | None = None,
) -> DestinationDecision:
    existing_duplicate = destination_hash_index.get(file_hash)
    if existing_duplicate:
        return DestinationDecision(
            action="skip",
            destination=None,
            reason=f"duplicate hash already exists at {existing_duplicate}",
            duplicate_kind="destination",
        )

    repeated_source = run_hash_index.get(file_hash) if run_hash_index else None
    if repeated_source:
        return DestinationDecision(
            action="skip",
            destination=None,
            reason=f"repeated source file; first seen at {repeated_source}",
            duplicate_kind="source",
        )

    if not target_path.exists():
        return DestinationDecision(action="copy", destination=target_path)

    try:
        existing_hash = calculate_hash(target_path)
    except OSError as exc:
        return DestinationDecision(
            action="error",
            destination=None,
            reason=f"unable to hash existing target {target_path}: {exc}",
        )

    if existing_hash == file_hash:
        destination_hash_index[file_hash] = target_path
        return DestinationDecision(
            action="skip",
            destination=None,
            reason=f"duplicate hash already exists at {target_path}",
            duplicate_kind="destination",
        )

    return DestinationDecision(
        action="copy",
        destination=collision_path(target_path),
        reason=f"target filename exists with a different hash: {target_path}",
        collision=True,
    )


def collision_path(target_path: Path) -> Path:
    for number in range(1, 10_000):
        candidate = target_path.with_name(
            f"{target_path.stem}_collision-{number:02d}{target_path.suffix}"
        )
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Unable to find available collision filename for {target_path}")


def _is_system_file(path: Path) -> bool:
    if "_syncsnap_reports" in path.parts:
        return True
    if path.name.startswith("."):
        return True
    return path.name.lower() in {"thumbs.db", "desktop.ini"}
