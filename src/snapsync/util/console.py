# Shared helpers for terminal colors and simple text tables.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
import builtins
import re
import shutil
import sys

try:
    from rich import box
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text
except ImportError:  # pragma: no cover - exercised when dependencies are absent.
    box = None
    Console = None
    Table = None
    Text = None


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
RICH_STYLES = {
    BLUE: "blue",
    CYAN: "cyan",
    GREEN: "green",
    YELLOW: "yellow",
    RED: "red",
    MUTED: "bright_black",
}


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


def _rich_enabled() -> bool:
    return Console is not None and Text is not None and Table is not None and box is not None


def _console() -> Console:
    terminal_width = shutil.get_terminal_size(fallback=(160, 24)).columns
    return Console(
        file=sys.stdout,
        force_terminal=True,
        color_system="standard",
        highlight=False,
        soft_wrap=True,
        width=max(terminal_width, 160),
        _environ={"COLUMNS": str(max(terminal_width, 160)), "LINES": "24"},
    )


def _emit(value: str = "") -> None:
    if _rich_enabled():
        _console().print(Text.from_ansi(value))
        return
    builtins.print(value)


def print_title(title: str, *, icon: str | None = None) -> None:
    _emit()
    label = f"{icon} {title}" if icon else title
    _emit(heading(label, bold=True))


def print_section_heading(title: str, *, icon: str | None = None) -> None:
    _emit()
    label = f"{icon} {title}" if icon else title
    _emit(heading(label, bold=True))


def print_notice(title: str, detail: str | None = None, *, icon: str = ICONS["info"]) -> None:
    _emit()
    _emit(warning(f"{icon} {title}", bold=True))
    if detail:
        _emit(muted(detail))


def print_key_values(rows: list[tuple[str, object]], *, value_color: str | None = None) -> None:
    label_width = max((visible_len(label) for label, _ in rows), default=0)
    for label, value in rows:
        formatted_value = str(value)
        if value_color is not None:
            formatted_value = color(formatted_value, value_color)
        _emit(f"{muted(label.ljust(label_width))}  {formatted_value}")


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if _rich_enabled():
        _print_rich_table(headers, rows)
        return
    widths = table_widths(headers, rows)
    _emit(format_table_row(headers, widths, header=True))
    _emit(format_table_separator(widths))
    for row in rows:
        _emit(format_table_row(row, widths))


def print_grouped_table(headers: list[str], rows: list[list[str]], group_values: list[str]) -> None:
    if _rich_enabled():
        _print_rich_table(headers, rows, group_values=group_values)
        return
    widths = table_widths(headers, rows)
    _emit(format_table_row(headers, widths, header=True))
    _emit(format_table_separator(widths))
    row_width = visible_len(format_table_row(headers, widths))
    previous_group: str | None = None
    for index, row in enumerate(rows):
        current_group = group_values[index]
        if previous_group is not None and current_group != previous_group:
            _emit(muted(TABLE_SEPARATOR * row_width))
        _emit(format_table_row(row, widths))
        previous_group = current_group


def _print_rich_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    group_values: list[str] | None = None,
) -> None:
    table = Table(
        box=box.SIMPLE_HEAD,
        header_style="bold cyan",
        show_edge=False,
        show_lines=False,
        pad_edge=False,
    )
    for header in headers:
        table.add_column(header, overflow="fold")

    previous_group: str | None = None
    for index, row in enumerate(rows):
        if group_values is not None:
            current_group = group_values[index]
            if previous_group is not None and current_group != previous_group:
                table.add_section()
            previous_group = current_group
        table.add_row(*[Text.from_ansi(value) for value in row])

    _console().print(table)


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
