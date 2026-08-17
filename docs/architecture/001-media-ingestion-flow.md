# Media Ingestion Flow

## Flow

1. User enters a source folder and runs SnapSync
2. If no source path is passed, SnapSync asks which action to run
3. User presses `1` for media copy plus filename fix
4. Recursive scan begins
5. Media files identified
6. Metadata extracted using ExifTool
7. Best timestamp selected
8. Media classified:
   - photo
   - video
   - unknown
9. Filename generated
10. Duplicate hash check performed
11. Destination folder created if missing
12. File copied
13. Summary generated

## Rules

- Originals are never modified
- Originals are never renamed in source
- Destination copy is authoritative
- Every failure must be logged
- Processing should continue even after individual file failures

## Configuration

SnapSync uses environment-based configuration.

The destination folder is configured externally via `.env`.

Example:

DESTINATION_FOLDER=/path/to/destination
EXIFTOOL_PATH=exiftool
FILENAME_PREFIX=zSnapSyncTestFolder2026May
HASH_LENGTH=12

All ingestion paths are derived from this destination folder.

`VAULT_ROOT` is still accepted as a legacy alias for `DESTINATION_FOLDER`.

ExifTool is required for metadata extraction. If the executable cannot be found,
startup fails with a clear configuration error.

`--dry-run` can be passed at the command line to audit planned copies without
editing `.env`.
