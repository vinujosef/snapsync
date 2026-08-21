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
1. Media copy + filename fix
2. Fix Canon timezone issue in this folder
3. Audit files in this folder
4. Fix audit issues in this folder
q. Quit
```

Option `1` copies media into `DESTINATION_FOLDER`.

Option `2` recursively scans the current folder and renames affected Canon
files in place. It does not copy files, move files to another root, or edit
embedded metadata.

Option `3` recursively scans the current folder and prints the number of files
found, the audit rules, a compact details table, and an issue summary at the
end.
Media rows are ordered by taken date/time, then filename, with divider lines
between date groups.
The rules include the Helsinki baseline timezone, Helsinki daylight saving
offset dates for years present in the audited files, and timestamp priority
order.
The audit info block is color-coded without using red or green.
In the metadata table, a timezone is shown in red when it does not match the
expected Helsinki offset for the file's taken date or when no timezone was
found.
The timestamp source is shown in yellow when it is not `DateTimeOriginal`.
`UnknownDevice` is also shown in red.
When a row has a red warning, that file's name is shown in red too. When the
only warning is the timestamp source, that file's name is shown in yellow.

Option `4` scans the current folder for audit issues, shows issue counts, and
lets you choose one issue type to fix. Timezone fixes set Helsinki's expected
offset for each file's date; the preview table shows each file's date, time,
device, current offset, new offset, and action before confirmation. The same
Helsinki timezone rules shown in the audit appear above the preview table.
Unknown-device fixes prompt for a device model per file, with a shortcut for
`WhatsApp`; each file is shown in a one-row metadata table before the device
choice. The selected subflow exits when finished.
Timezone and unknown-device fix lists are also ordered by taken date/time, then
filename.
For videos with no readable offset, timezone repair also writes a timezone-aware
`CreationDate` and verifies that snapsync can read the expected offset back.
Metadata repair writes preserve filesystem modified time so files that still
fall back to `FileModifyDate` do not jump to the repair run time.
Manual date/time edits also write the existing timezone offset fields when an
offset is known, so the local computer timezone is not introduced during repair.
When video metadata contains both a local-machine `DateTimeOriginal` offset and
a timezone-aware `CreationDate`, snapsync uses the `CreationDate` offset.
Option `4` also includes a manual one-file editor. Enter a filename, then choose
whether to edit its date, time, offset, or device metadata. The manual editor
uses step markers (`i.`, `ii.`, `iii.`) and shows the selected file's current
metadata in a one-row table before asking what to change. Option `4` repair
subflows use the same step-marker style.

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
