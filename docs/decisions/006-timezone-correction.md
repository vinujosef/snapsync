# Decision 0006 - Timezone Correction

## Problem

When travelling, phones often update to the local timezone automatically.
Dedicated cameras may keep using the home timezone and may not write timezone
metadata.

That means two photos taken at the same local moment can produce filenames and
folders that sort one hour apart.

## Final Choice

During copy, snapsync may infer the destination timezone from iPhone photo
metadata, then apply a Canon timestamp correction only after explicit
confirmation.

The correction affects generated filenames and destination folders for the copy
run.

The correction does not edit embedded metadata.

## Rules

- Read iPhone timezone offsets such as `OffsetTimeOriginal`.
- Infer a timezone only when the iPhone offsets in the batch agree.
- Treat Canon files as candidates when their effective timezone differs from the
  inferred iPhone timezone.
- Use Canon timezone metadata when Canon provides it.
- Use `CANON_HOME_TIMEZONE` only as a fallback when Canon timezone metadata is
  missing.
- Print the detected iPhone offset, Canon home timezone, Canon file count, and
  exact timestamp shift before applying anything.
- Require the user to type `yes`.
- If confirmation is unavailable or not given, leave Canon timestamps unchanged.
- Standalone Canon timezone repair is not offered as a separate interactive
  action; audit-based metadata repair is handled by the audit fix workflow.

## Audit Metadata Repair

The audit fix workflow offers both bulk and batch metadata repair. This is
separate from copy-time Canon correction because it edits embedded metadata.

Bulk repair changes every media file in the folder. Batch repair changes only
files that match the user's filter. Bulk and batch timezone repair both move
the clock time by the offset difference.

For batch timezone repair, the user enters:

- Current offset to match.
- New offset to write.
- Device-name filter.

Only files whose current metadata offset exactly matches the current offset are
changed. The file's device name must contain the device filter text too.

Example: moving `+03:00` to `+05:30` with device filter `iPhone` changes an
iPhone file from `2026-08-26 09:41:37 +03:00` to
`2026-08-26 12:11:37 +05:30`. Canon files already at `+05:30` are skipped, and
iPhone files already at `+05:30` are skipped.

## Configuration

```env
INFER_TIMEZONE_FROM_IPHONE=true
CANON_HOME_TIMEZONE=Europe/Helsinki
```

## Why

Hardcoding `-1 hour` is fragile because daylight saving rules change the actual
offset between places depending on the capture date.

Using an IANA timezone such as `Europe/Helsinki` lets Python calculate the
camera's home offset for the photo date, while the iPhone metadata tells
snapsync the destination offset.

## Tradeoffs

- Requires at least one iPhone photo with timezone metadata.
- Mixed iPhone offsets are skipped for now rather than guessed.
- Canon correction is not automatic in non-interactive runs.
