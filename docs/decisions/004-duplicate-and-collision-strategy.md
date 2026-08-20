# Decision 0005 - Duplicate and Collision Strategy

## Problem

Need reliable duplicate handling without deleting legitimate files.

## Definitions

Duplicate:
- identical file hash

Collision:
- same target filename but different file hash

## Final Choice

Duplicates:
- detected using SHA-256 hash
- skipped during copy
- logged in summary
- split into files already in the destination and files repeated in the source folder

Filename collisions:
- preserved with a collision suffix
- never skipped, because a filename collision means same target filename but different file content
- never overwritten silently

Example:

2026-05-18_142211_iPhone15Pro_a8f31c9e71d4.jpg
2026-05-18_142211_iPhone15Pro_a8f31c9e71d4_collision-01.jpg

## Why

Filename alone is not reliable.

Different files can share:
- timestamps
- filenames
- device names

Skipping a filename collision would lose data. A duplicate is safe to skip
because the SHA-256 hash proves the content is identical. A collision is not
safe to skip because the hash is different, so snapsync keeps both files.

## Tradeoffs

- hashing increases processing time
- requires index tracking

## Future Risks

- large destination hash lookup performance
- edited exports with near-identical content
- live-photo related duplicates
