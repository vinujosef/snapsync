# Track counters and print the final run summary.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


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
    audit_mode: bool = False

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
        print(f"{BOLD}{BLUE}SyncSnap Summary{RESET}")
        for index, (title, rows) in enumerate(sections, start=1):
            self._print_section(index, title, rows)

    def _result_rows(self) -> list[tuple[str, int, str]]:
        rows = []
        if self.audit_mode:
            rows.append(("Will copy", self.planned_copies, GREEN))
        else:
            rows.append(("Copied", self.copied_files, GREEN))
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
