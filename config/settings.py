# Load and validate snapsync settings from .env.
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


DEFAULT_PHOTO_EXTENSIONS = {
    "jpg",
    "jpeg",
    "heic",
    "png",
    "dng",
    "arw",
    "cr2",
    "nef",
}

DEFAULT_VIDEO_EXTENSIONS = {
    "mov",
    "mp4",
    "m4v",
    "avi",
    "mkv",
}

DEFAULT_IGNORED_FOLDERS = {
    ".git",
    ".svn",
    ".hg",
    "__pycache__",
    "@eaDir",
    "System Volume Information",
    "$RECYCLE.BIN",
}


@dataclass(frozen=True)
class Settings:
    destination_folder: Path
    dry_run: bool
    log_level: str
    exiftool_path: str
    filename_prefix: str
    hash_length: int
    allowed_photo_extensions: frozenset[str]
    allowed_video_extensions: frozenset[str]
    ignored_folders: frozenset[str]
    infer_timezone_from_iphone: bool = True
    canon_home_timezone: str = "Europe/Helsinki"


def get_settings() -> Settings:
    load_dotenv()

    destination_folder = os.getenv("DESTINATION_FOLDER", "").strip()
    if not destination_folder:
        destination_folder = os.getenv("VAULT_ROOT", "").strip()
    if not destination_folder:
        raise ValueError("Missing required config: DESTINATION_FOLDER")

    exiftool_path = os.getenv("EXIFTOOL_PATH", "exiftool").strip() or "exiftool"
    if not shutil.which(exiftool_path):
        raise ValueError(
            "ExifTool is required but was not found. Install it with "
            "`brew install exiftool` or set EXIFTOOL_PATH in .env."
        )

    return Settings(
        destination_folder=Path(destination_folder).expanduser(),
        dry_run=_parse_bool(os.getenv("DRY_RUN", "false")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        exiftool_path=exiftool_path,
        filename_prefix=os.getenv("FILENAME_PREFIX", "").strip(),
        hash_length=_parse_hash_length(os.getenv("HASH_LENGTH", "12")),
        allowed_photo_extensions=frozenset(
            _parse_csv(os.getenv("ALLOWED_PHOTO_EXTENSIONS"), DEFAULT_PHOTO_EXTENSIONS)
        ),
        allowed_video_extensions=frozenset(
            _parse_csv(os.getenv("ALLOWED_VIDEO_EXTENSIONS"), DEFAULT_VIDEO_EXTENSIONS)
        ),
        ignored_folders=frozenset(
            _parse_csv(os.getenv("IGNORED_FOLDERS"), DEFAULT_IGNORED_FOLDERS)
        ),
        infer_timezone_from_iphone=_parse_bool(os.getenv("INFER_TIMEZONE_FROM_IPHONE", "true")),
        canon_home_timezone=os.getenv("CANON_HOME_TIMEZONE", "Europe/Helsinki").strip()
        or "Europe/Helsinki",
    )


def load_dotenv(env_path: Path | None = None) -> None:
    path = env_path or _find_dotenv()
    if not path.exists():
        return

    try:
        from dotenv import load_dotenv as python_dotenv_load

        python_dotenv_load(path, override=False)
        return
    except ImportError:
        pass

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_csv(value: str | None, default: set[str]) -> set[str]:
    if not value:
        return set(default)
    return {item.strip().lstrip(".").lower() for item in value.split(",") if item.strip()}


def _parse_hash_length(value: str | None) -> int:
    try:
        hash_length = int((value or "12").strip())
    except ValueError as exc:
        raise ValueError("HASH_LENGTH must be an integer between 8 and 64") from exc

    if hash_length < 8 or hash_length > 64:
        raise ValueError("HASH_LENGTH must be between 8 and 64")
    return hash_length


def _find_dotenv() -> Path:
    cwd_path = Path.cwd() / ".env"
    if cwd_path.exists():
        return cwd_path

    project_path = Path(__file__).resolve().parents[1] / ".env"
    if project_path.exists():
        return project_path

    return cwd_path
