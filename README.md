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
IGNORED_FOLDERS=.git,.svn,.hg,__pycache__,@eaDir,System Volume Information,$RECYCLE.BIN
```

`VAULT_ROOT` is accepted as a legacy alias for `DESTINATION_FOLDER`.

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