# Decision 0004 - Metadata Priority

## Problem

Media files may contain multiple conflicting timestamps or missing metadata.

Need a deterministic priority order.

## Tooling

SnapSync uses ExifTool as the authoritative metadata reader for the MVP.

ExifTool is required at startup because media timestamp behavior should be
predictable across iPhone, Android, DSLR, video, and exported files. Filesystem
timestamps remain fallbacks only when ExifTool reports no usable embedded
timestamp for an individual file.

## Final Choice

Timestamp priority:

1. DateTimeOriginal
2. CreateDate
3. MediaCreateDate
4. TrackCreateDate
5. FileModifyDate
6. FileCreateDate
7. Current date fallback

## Why

DateTimeOriginal best represents actual capture time.

Filesystem timestamps are unreliable because:
- copying changes timestamps
- exports rewrite metadata
- messaging apps modify dates

## Tradeoffs

- requires ExifTool as a system dependency
- slower processing than filesystem-only methods

## Future Risks

- timezone offsets
- malformed metadata
- edited files losing original EXIF
- WhatsApp/social media stripped metadata
