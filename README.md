# SyncSnap

SyncSnap is a local photo/video ingestion tool.

It scans a source folder, reads metadata with ExifTool, copies media into a
structured destination folder, normalizes filenames, skips exact duplicates,
preserves filename conflicts, and prints a run summary.

## Safety

- Copy only, never move.
- Never modify source files.
- Detect duplicates with SHA-256 hashes.
- Skip exact duplicate content.
- Preserve filename conflicts with `_collision-01`.
- Continue after individual file errors.

## Setup

```bash
brew install exiftool
./scripts/install-syncsnap.sh --user
```

The installer creates `.venv`, installs `requirements.txt`, and creates the
`syncsnap` command. If using `--user`, make sure this is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Configuration

SyncSnap reads `.env`.

```env
DESTINATION_FOLDER=/path/to/destination
DRY_RUN=true
EXIFTOOL_PATH=/opt/homebrew/bin/exiftool
HASH_LENGTH=12
```

Optional:

```env
FILENAME_PREFIX=
LOG_LEVEL=INFO
INFER_TIMEZONE_FROM_IPHONE=true
CANON_HOME_TIMEZONE=Europe/Helsinki
IGNORED_FOLDERS=.git,.svn,.hg,__pycache__,@eaDir,System Volume Information,$RECYCLE.BIN
```

`VAULT_ROOT` is accepted as a legacy alias for `DESTINATION_FOLDER`.

## Timezone Correction

This handles trips where iPhones switch to the local timezone automatically, but
a Canon camera keeps using the home timezone.

Example:

- iPhone photos in Spain contain `OffsetTimeOriginal=+01:00`.
- Canon EOS M50 photos have capture times but no timezone offset.
- Canon clock is still set to Finland time.
- SyncSnap can shift Canon-derived filename and folder timestamps so Canon and
  iPhone photos sort together correctly.

SyncSnap is deliberately conservative:

- It checks iPhone files in the import batch for timezone metadata.
- It only infers a timezone when the iPhone offsets agree.
- It uses `CANON_HOME_TIMEZONE` as the timezone the Canon clock was set to.
- It prints the detected iPhone offset, Canon home timezone, Canon file count,
  and exact Canon timestamp shift.
- It applies the Canon correction only if you type `yes`.
- It never modifies source metadata or source files.
- If there is no interactive confirmation, Canon timestamps are left unchanged.

Configuration:

```env
INFER_TIMEZONE_FROM_IPHONE=true
CANON_HOME_TIMEZONE=Europe/Helsinki
```

To disable this behavior completely:

```env
INFER_TIMEZONE_FROM_IPHONE=false
```

Confirmation prompt example:

```text
Timezone correction
-------------------
Detected iPhone timezone offset: +01:00
Canon home timezone to assume: Europe/Helsinki
Canon files without timezone metadata: 42
Canon filename/folder timestamp shift: -1h

Apply this correction to Canon files for this run?
Type yes to apply:
```

## Usage

Interactive:

```bash
cd "/path/to/source-folder"
syncsnap
```

Audit without copying:

```bash
syncsnap --dry-run "/path/to/source-folder"
```

Real copy:

```env
DRY_RUN=false
```

```bash
syncsnap "/path/to/source-folder"
```

For large real runs, consider:

```env
LOG_LEVEL=WARNING
```

## Output

Destination structure:

```text
DESTINATION_FOLDER/
└── YYYY/
    └── MM - Month/
        ├── photo/
        ├── video/
        └── unknown/
```

Filename format:

```text
YYYY-MM-DD_HHMMSS_DeviceName_Hash12.ext
```

Example:

```text
2026-05-18_142211_iPhone15Pro_a8f31c9e71d4.jpg
```

If `FILENAME_PREFIX` is set, it is prepended to the filename.

## Reports

If repeated files are found inside the source folder, SyncSnap writes:

```text
DESTINATION_FOLDER/_syncsnap_reports/*_duplicate_groups.csv
```

The report shows which source file was kept and which repeated source files
were skipped for the same SHA-256 hash.

## Docs

See `docs/` for architecture notes and decision records.
