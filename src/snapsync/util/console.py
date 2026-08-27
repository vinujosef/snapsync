# Shared helpers for terminal colors and simple text tables.
from __future__ import annotations

from datetime import date, datetime
import re


DISPLAY_DATE_FORMAT = "%d-%m-%Y"
DISPLAY_DATETIME_FORMAT = "%d-%m-%Y %H:%M:%S"
RESET = "\033[0m"
BOLD = "\033[1m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
ANSI_PATTERN = re.compile(r"\033\[[0-9;]*m")


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


def color(text: str, color_code: str, *, bold: bool = False) -> str:
    prefix = f"{BOLD}{color_code}" if bold else color_code
    return f"{prefix}{text}{RESET}"


def print_section_heading(title: str) -> None:
    print()
    print(cyan(f"{title}:"))
    print(cyan("-" * (len(title) + 1)))


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = table_widths(headers, rows)
    print(format_table_row(headers, widths))
    print(format_table_separator(widths))
    for row in rows:
        print(format_table_row(row, widths))


def print_grouped_table(headers: list[str], rows: list[list[str]], group_values: list[str]) -> None:
    widths = table_widths(headers, rows)
    print(format_table_row(headers, widths))
    print(format_table_separator(widths))
    row_width = visible_len(format_table_row(headers, widths))
    previous_group: str | None = None
    for index, row in enumerate(rows):
        current_group = group_values[index]
        if previous_group is not None and current_group != previous_group:
            print("-" * row_width)
        print(format_table_row(row, widths))
        previous_group = current_group


def table_widths(headers: list[str], rows: list[list[str]]) -> list[int]:
    return [
        max(visible_len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]


def format_table_row(values: list[str], widths: list[int]) -> str:
    cells = [pad_cell(value, widths[index]) for index, value in enumerate(values)]
    return f"| {' | '.join(cells)} |"


def format_table_separator(widths: list[int]) -> str:
    cells = ["-" * width for width in widths]
    return f"| {' | '.join(cells)} |"


def pad_cell(value: str, width: int) -> str:
    return value + (" " * (width - visible_len(value)))


def visible_len(value: str) -> int:
    return len(ANSI_PATTERN.sub("", value))


def format_display_date(value: date | datetime) -> str:
    return value.strftime(DISPLAY_DATE_FORMAT)


def format_display_datetime(value: datetime) -> str:
    return value.strftime(DISPLAY_DATETIME_FORMAT)
