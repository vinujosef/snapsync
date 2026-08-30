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
- Apply timezone correction only after you type `yes`.
- Preserve file modified timestamps during audit metadata repairs.

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
1. Audit files in this folder
2. Fix audit issues in this folder
3. Rename files in this folder
4. Copy files to destination
q. Quit
```

- `1` Audit files:
  Scans the folder and shows metadata, warnings, and issue counts.
  Rows are ordered by taken date/time, then filename.

- `2` Fix audit issues:
  Repairs selected metadata issues after a preview and confirmation.
  Available fixes include timezone offset, unknown device, one-file manual
  edits, bulk repairs, and batch repairs.
  Preview tables show old/current values in red and new values in green.
  After confirmed fixes, snapsync prints a full metadata result table and
  highlights the changed final value in yellow.

- `3` Rename files:
  Renames media in place using the current metadata.
  It does not copy files or edit metadata.

- `4` Copy files:
  Copies media into `DESTINATION_FOLDER`, preserving current filenames.

Bulk vs batch repair:

- Bulk repair changes every media file in the folder.
- Batch repair changes only files that match your filter.
- Batch date repair: current date, new date, device filter.
- Batch time repair: current time, new time, device filter.
- Batch timezone repair: current offset, new offset, device filter.
- Bulk and batch timezone repair also move the clock time by the offset
  difference.
- Example: `+03:00` to `+05:30` with device filter `iPhone` changes
  `2026-08-26 09:41:37 +03:00` to `2026-08-26 12:11:37 +05:30`.
- Canon files already at `+05:30` are skipped.
- iPhone files already at `+05:30` are skipped.

Audit without copying:

```bash
snapsync --dry-run "/path/to/source-folder"
```

Run copy directly:

```bash
snapsync "/path/to/source-folder"
```

Every action prints the total run time when it finishes.

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
