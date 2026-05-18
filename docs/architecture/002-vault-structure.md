# Destination Structure

## Purpose

The SyncSnap destination folder is the long-term storage location for copied photo and video originals.

The destination folder must stay predictable, human-readable, and safe to back up.

## Configuration

The destination folder is configured through `.env`.

Example:

```env
DESTINATION_FOLDER=/Volumes/...
```

Output is created directly under `DESTINATION_FOLDER`:

```text
DESTINATION_FOLDER/
└── YYYY/
    └── MM - Month/
        ├── photo/
        ├── video/
        └── unknown/
```
