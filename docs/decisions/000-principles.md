# Decision 0000 - SyncSnap Principles

## Problem

SyncSnap needs clear rules before any code is written, because media storage decisions are hard to reverse once thousands of files are processed.

## Principles

- Originals are immutable.
- Source files are never modified.
- MVP copies files, never moves them.
- Metadata dates are preferred over filesystem dates.
- Filesystem dates are only fallback signals.
- Duplicate detection is based on file hash, not filename.
- Folder structure must remain human-readable.
- Filenames must be both human-readable and collision-safe.
- Every skipped file must have a reason in logs.
- Every copied file must be traceable to its source.
- Processing must be resumable.
- Unknown files must be preserved, not deleted.
- Automation must be boring, predictable, and reversible.

## Final Choice

SyncSnap will treat the destination folder as a long-term archive, not a temporary sync folder.

## Tradeoffs

- More upfront structure.
- Slightly slower MVP.
- Much lower risk of data loss, duplicate mess, or future migration pain.

## Future Risks

- Metadata inconsistencies across iPhone, Android, DSLR, WhatsApp, and exported files.
- Timezone confusion.
- Device naming inconsistencies.
- Duplicate files with different metadata.
- Edited files accidentally mixed with originals.
