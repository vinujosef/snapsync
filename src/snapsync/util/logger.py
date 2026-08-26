# Provide small colored console logging for snapsync.
from __future__ import annotations

import sys

from snapsync.util.console import BLUE, CYAN, GREEN, RED, RESET, YELLOW


LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

COLORS = {
    "DEBUG": CYAN,
    "INFO": BLUE,
    "SUCCESS": GREEN,
    "WARNING": YELLOW,
    "ERROR": RED,
}

SYMBOLS = {
    "DEBUG": "🔎 ",
    "INFO": "ℹ️ ",
    "SUCCESS": "✅ ",
    "WARNING": "⚠️ ",
    "ERROR": "❌ ",
}

_level = LEVELS["INFO"]


def configure(log_level: str) -> None:
    global _level
    _level = LEVELS.get(log_level.upper(), LEVELS["INFO"])


def debug(message: str) -> None:
    _log("DEBUG", message)


def info(message: str) -> None:
    _log("INFO", message)


def success(message: str) -> None:
    _log("SUCCESS", message)


def warning(message: str) -> None:
    _log("WARNING", message)


def error(message: str) -> None:
    _log("ERROR", message, stream=sys.stderr)


def skipped(path: object, reason: str) -> None:
    warning(f"Skipped {path}: {reason}")


def _log(level: str, message: str, stream=sys.stdout) -> None:
    threshold = LEVELS.get(level, LEVELS["INFO"])
    if level == "SUCCESS":
        threshold = LEVELS["INFO"]
    if threshold < _level:
        return
    color = COLORS.get(level, "")
    symbol = SYMBOLS.get(level, "•")
    print(f"{color}{symbol} {message}{RESET}", file=stream)
