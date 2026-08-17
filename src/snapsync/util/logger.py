# Provide small colored console logging for SnapSync.
from __future__ import annotations

import sys


LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[34m",
    "SUCCESS": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
}

SYMBOLS = {
    "DEBUG": "🔎 ",
    "INFO": "ℹ️ ",
    "SUCCESS": "✅ ",
    "WARNING": "⚠️ ",
    "ERROR": "❌ ",
}

RESET = "\033[0m"

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
