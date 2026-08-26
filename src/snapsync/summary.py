# Track counters and print the final run summary.
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from snapsync.util.console import BLUE, BOLD, CYAN, GREEN, RED, RESET, YELLOW


@dataclass
class RunSummary:
    source_files_found: int = 0
    media_files_processed: int = 0
    planned_copies: int = 0
    copied_files: int = 0
    duplicate_files_skipped: int = 0
    duplicates_already_in_destination: int = 0
    duplicates_repeated_in_source: int = 0
    filename_collisions_handled: int = 0
    unknown_files: int = 0
    errors: int = 0
    duplicate_groups_report: Path | None = None
    output_folders: dict[str, set[Path]] = field(default_factory=dict)
    audit_mode: bool = False
    action_label: str = "copy"

    def record_output_folder(self, media_type: str, destination: Path) -> None:
        self.output_folders.setdefault(media_type, set()).add(destination.parent)

    def print(self) -> None:
        sections = [
            (
                "Scanned",
                [
                    ("Files found", self.source_files_found, BLUE),
                    ("Media files", self.media_files_processed, CYAN),
                ],
            ),
            (
                "Results",
                self._result_rows(),
            ),
            (
                "Duplicate Details",
                [
                    ("Repeated in source folder", self.duplicates_repeated_in_source, YELLOW),
                    ("Already copied before", self.duplicates_already_in_destination, YELLOW),
                ],
            ),
        ]
        issue_rows = self._issue_rows()
        if issue_rows:
            sections.append(("Needs Attention", issue_rows))
        if self.duplicate_groups_report is not None:
            sections.append(
                (
                    "Reports",
                    [("Duplicate groups CSV", str(self.duplicate_groups_report), CYAN)],
                )
            )

        print("")
        print(f"{BOLD}{BLUE}snapsync Summary{RESET}")
        for index, (title, rows) in enumerate(sections, start=1):
            self._print_section(index, title, rows)
        self._print_output_folders()

    def _result_rows(self) -> list[tuple[str, int, str]]:
        rows = []
        action = "rename" if self.action_label == "rename" else "copy"
        if self.audit_mode:
            rows.append((f"Will {action}", self.planned_copies, GREEN))
        else:
            rows.append(("Renamed" if action == "rename" else "Copied", self.copied_files, GREEN))
        rows.append(("Skipped duplicates", self.duplicate_files_skipped, YELLOW))
        rows.append(("Skipped unknown", self.unknown_files, YELLOW))
        rows.append(("Errors", self.errors, RED if self.errors else GREEN))
        return rows

    def _issue_rows(self) -> list[tuple[str, int, str]]:
        rows = []
        if self.filename_collisions_handled:
            rows.append(("Filename conflicts fixed", self.filename_collisions_handled, YELLOW))
        return rows

    def _print_section(self, index: int, title: str, rows: list[tuple[str, object, str]]) -> None:
        label_width = max(len(label) for label, _, _ in rows)
        value_width = max(len(str(value)) for _, value, _ in rows)
        border = f"+-{'-' * label_width}-+-{'-' * value_width}-+"
        heading = f"{index}. {title}"

        print("")
        print(f"{BOLD}{CYAN}{heading}{RESET}")
        print(f"{CYAN}{'-' * len(heading)}{RESET}")
        print(border)
        for label, value, color in rows:
            print(
                f"| {label.ljust(label_width)} | "
                f"{color}{str(value).rjust(value_width)}{RESET} |"
            )
        print(border)

    def _print_output_folders(self) -> None:
        if not self.output_folders:
            return

        file_count = self.planned_copies if self.audit_mode else self.copied_files
        action = "would be written to" if self.audit_mode else "written to"
        noun = "file" if file_count == 1 else "files"
        print("")
        print(f"{file_count} {noun} {action}:")

        for media_type in ("photo", "video", "unknown"):
            folders = self.output_folders.get(media_type)
            if not folders:
                continue
            print("")
            print(f"({_media_type_label(media_type)})")
            for folder in sorted(folders):
                print(f"{folder}/")


def _media_type_label(media_type: str) -> str:
    labels = {
        "photo": "📸 photo",
        "video": "📹 video",
        "unknown": "unknown",
    }
    return labels.get(media_type, media_type)
