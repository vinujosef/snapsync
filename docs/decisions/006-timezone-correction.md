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
