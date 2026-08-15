# Write audit-friendly run reports.
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from config.settings import Settings


@dataclass
class DuplicateGroup:
    file_hash: str
    kept_source: Path
    duplicate_sources: list[Path]
    destination_path: Path | None = None


def write_duplicate_groups_report(
    settings: Settings,
    duplicate_groups: dict[str, DuplicateGroup],
    run_started_at: datetime,
) -> Path | None:
    groups = [group for group in duplicate_groups.values() if group.duplicate_sources]
    if not groups:
        return None

    reports_folder = settings.destination_folder / "_syncsnap_reports"
    reports_folder.mkdir(parents=True, exist_ok=True)
    report_path = reports_folder / f"{run_started_at.strftime('%Y%m%d_%H%M%S')}_duplicate_groups.csv"

    with report_path.open("w", newline="", encoding="utf-8") as report_file:
        writer = csv.writer(report_file)
        writer.writerow(
            [
                "sha256",
                "kept_source",
                "duplicate_source",
                "duplicate_count",
                "destination_path",
            ]
        )
        for group in sorted(groups, key=lambda item: str(item.kept_source)):
            for duplicate_source in sorted(group.duplicate_sources):
                writer.writerow(
                    [
                        group.file_hash,
                        group.kept_source,
                        duplicate_source,
                        len(group.duplicate_sources),
                        group.destination_path or "",
                    ]
                )

    return report_path
