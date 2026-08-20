# snapsync

snapsync is a local photo/video ingestion tool.

It scans a source folder, reads metadata with ExifTool, copies media into a
structured destination folder, normalizes filenames, skips exact duplicates,
preserves filename conflicts, and prints a run summary.

- [Safety](#safety)
- [Install](#install)
- [Basic Usage](#basic-usage)
- [Config](#config)
- [Where To Read More](#where-to-read-more)

## Safety

- Copy only, never move.
- Never modify source files during copy.
- Skip exact duplicate content using SHA-256 hashes.
- Preserve filename conflicts with `_collision-01`.
- Continue after individual file errors.
- Read metadata with ExifTool in batches, with safe fallbacks for unreadable files.
- Apply Canon timezone correction only after you type `yes`.

## Install

```bash
brew install exiftool
./scripts/install-snapsync.sh --user
```

If using `--user`, make sure this is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Basic Usage

Run from the folder you want to process:

```bash
cd "/path/to/source-folder"
snapsync
```

Choose an action:

```text
1. Media copy + filename fix
2. Fix Canon timezone issue in this folder
q. Quit
```

Option `1` copies media into `DESTINATION_FOLDER`.

Option `2` recursively scans the current folder and renames affected Canon
files in place. It does not copy files, move files to another root, or edit
embedded metadata.

Audit without copying:

```bash
snapsync --dry-run "/path/to/source-folder"
```

Run copy directly:

```bash
snapsync "/path/to/source-folder"
```

## Config

snapsync reads `.env`.

```env
DESTINATION_FOLDER=/path/to/destination
DRY_RUN=true
EXIFTOOL_PATH=/opt/homebrew/bin/exiftool
HASH_LENGTH=12
```

Common optional settings:

```env
FILENAME_PREFIX=
LOG_LEVEL=INFO
INFER_TIMEZONE_FROM_IPHONE=true
CANON_HOME_TIMEZONE=Europe/Helsinki
IGNORED_FOLDERS=.git,.svn,.hg,__pycache__,@eaDir,System Volume Information,$RECYCLE.BIN
```

`VAULT_ROOT` is accepted as a legacy alias for `DESTINATION_FOLDER`.

For large real runs, consider:

```env
LOG_LEVEL=WARNING
```

## Where To Read More

- Destination folder structure: [docs/architecture/002-vault-structure.md](docs/architecture/002-vault-structure.md)
- Media ingestion flow: [docs/architecture/001-media-ingestion-flow.md](docs/architecture/001-media-ingestion-flow.md)
- Filename format: [docs/decisions/002-filename-format.md](docs/decisions/002-filename-format.md)
- Metadata priority and fallback strategy: [docs/decisions/003-metadata-priority.md](docs/decisions/003-metadata-priority.md)
- Timezone correction rules: [docs/decisions/006-timezone-correction.md](docs/decisions/006-timezone-correction.md)
- Duplicate reports and collision handling: [docs/decisions/004-duplicate-and-collision-strategy.md](docs/decisions/004-duplicate-and-collision-strategy.md)
