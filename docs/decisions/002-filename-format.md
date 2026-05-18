# Decision 0003 - Filename Format

## Problem

Need globally unique, human-readable filenames for long-term archival.

## Options Considered

1. Keep original filename
2. Timestamp only
3. Timestamp + device
4. Timestamp + device + hash suffix

## Why Rejected

### Original filename
- IMG_1234 collisions
- meaningless names
- duplicate issues across devices

### Timestamp only
- burst-photo collisions possible
- multi-device conflicts possible

### Timestamp + device
- still vulnerable to same-second captures

## Final Choice

Filename format:

YYYY-MM-DD_HHMMSS_DeviceName_Hash12.ext

When `FILENAME_PREFIX` is configured, the prefix is prepended:

Prefix_YYYY-MM-DD_HHMMSS_DeviceName_Hash12.ext

Example:

2026-05-18_142211_iPhone15Pro_a8f31c9e71d4.jpg
zSyncSnapTestFolder2026May_2026-05-18_142211_iPhone15Pro_a8f31c9e71d4.jpg

`HASH_LENGTH` is configurable between 8 and 64. The default is 12 for a better
full-scale safety margin while keeping filenames readable.

## Tradeoffs

- longer filenames
- slight visual noise from hash

Benefits:
- collision-resistant
- searchable
- human-readable
- globally unique
- supports temporary test prefixes without losing uniqueness

## Future Risks

- inconsistent device naming
- timezone normalization problems
