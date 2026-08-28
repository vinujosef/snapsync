# Shared helpers for terminal colors and simple text tables.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import re


DISPLAY_DATE_FORMAT = "%d-%m-%Y"
DISPLAY_DATETIME_FORMAT = "%d-%m-%Y %H:%M:%S"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MUTED = "\033[90m"
ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")
DEFAULT_TRAILING_PATH_PARTS = 9
TABLE_SEPARATOR = "─"


@dataclass(frozen=True)
class ConsoleTheme:
    primary: str = BLUE
    heading: str = CYAN
    muted: str = MUTED
    success: str = GREEN
    warning: str = YELLOW
    danger: str = RED
    changed_old: str = YELLOW
    changed_new: str = GREEN


THEME = ConsoleTheme()

ICONS = {
    "app": "📸",
    "video": "🎞️",
    "audit": "🔍",
    "fix": "🛠️",
    "rename": "📝",
    "copy": "📤",
    "warning": "⚠️",
    "error": "❌",
    "success": "✅",
    "info": "ℹ️",
    "progress": "⏳",
    "back": "↩️",
}


def blue(text: str, *, bold: bool = False) -> str:
    return color(text, BLUE, bold=bold)


def cyan(text: str, *, bold: bool = False) -> str:
    return color(text, CYAN, bold=bold)


def green(text: str, *, bold: bool = False) -> str:
    return color(text, GREEN, bold=bold)


def yellow(text: str, *, bold: bool = False) -> str:
    return color(text, YELLOW, bold=bold)


def red(text: str, *, bold: bool = False) -> str:
    return color(text, RED, bold=bold)


def muted(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.muted, bold=bold)


def primary(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.primary, bold=bold)


def heading(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.heading, bold=bold)


def success(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.success, bold=bold)


def warning(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.warning, bold=bold)


def danger(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.danger, bold=bold)


def changed_old(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.changed_old, bold=bold)


def changed_new(text: str, *, bold: bool = False) -> str:
    return color(text, THEME.changed_new, bold=bold)


def color(text: str, color_code: str, *, bold: bool = False, dim: bool = False) -> str:
    emphasis = f"{BOLD if bold else ''}{DIM if dim else ''}"
    prefix = f"{emphasis}{color_code}"
    return f"{prefix}{text}{RESET}"


def print_title(title: str, *, icon: str | None = None) -> None:
    print()
    label = f"{icon} {title}" if icon else title
    print(heading(label, bold=True))


def print_section_heading(title: str, *, icon: str | None = None) -> None:
    print()
    label = f"{icon} {title}" if icon else title
    print(heading(label, bold=True))


def print_notice(title: str, detail: str | None = None, *, icon: str = ICONS["info"]) -> None:
    print()
    print(warning(f"{icon} {title}", bold=True))
    if detail:
        print(muted(detail))


def print_key_values(rows: list[tuple[str, object]], *, value_color: str | None = None) -> None:
    label_width = max((visible_len(label) for label, _ in rows), default=0)
    for label, value in rows:
        formatted_value = str(value)
        if value_color is not None:
            formatted_value = color(formatted_value, value_color)
        print(f"{muted(label.ljust(label_width))}  {formatted_value}")


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = table_widths(headers, rows)
    print(format_table_row(headers, widths, header=True))
    print(format_table_separator(widths))
    for row in rows:
        print(format_table_row(row, widths))


def print_grouped_table(headers: list[str], rows: list[list[str]], group_values: list[str]) -> None:
    widths = table_widths(headers, rows)
    print(format_table_row(headers, widths, header=True))
    print(format_table_separator(widths))
    row_width = visible_len(format_table_row(headers, widths))
    previous_group: str | None = None
    for index, row in enumerate(rows):
        current_group = group_values[index]
        if previous_group is not None and current_group != previous_group:
            print(muted(TABLE_SEPARATOR * row_width))
        print(format_table_row(row, widths))
        previous_group = current_group


def table_widths(headers: list[str], rows: list[list[str]]) -> list[int]:
    return [
        max(visible_len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]


def format_table_row(values: list[str], widths: list[int], *, header: bool = False) -> str:
    cells = [pad_cell(value, widths[index]) for index, value in enumerate(values)]
    row = "  ".join(cells)
    return heading(row, bold=True) if header else row


def format_table_separator(widths: list[int]) -> str:
    cells = [TABLE_SEPARATOR * width for width in widths]
    return muted("  ".join(cells))


def pad_cell(value: str, width: int) -> str:
    return value + (" " * (width - visible_len(value)))


def visible_len(value: str) -> int:
    return len(ANSI_PATTERN.sub("", value))


def format_path(value: Path | str, *, trailing_parts: int = DEFAULT_TRAILING_PATH_PARTS) -> str:
    path = Path(value)
    parts = path.parts
    if len(parts) <= trailing_parts:
        return str(path)
    return str(Path("...", *parts[-trailing_parts:]))


def format_display_date(value: date | datetime) -> str:
    return value.strftime(DISPLAY_DATE_FORMAT)


def format_display_datetime(value: datetime) -> str:
    return value.strftime(DISPLAY_DATETIME_FORMAT)
