# Decision 0002 - Destination Folder Structure

## Problem

Need a predictable and scalable folder structure for long-term photo and video storage.

## Options Considered

1. Single flat folder
2. Year/month only
3. Event-based folders
4. Year/month with media separation

## Why Rejected

### Single flat folder
- becomes unusable at scale
- poor browsing experience

### Event-based folders
- inconsistent naming
- requires manual organization
- difficult automation

### Year/month only
- photos and videos mixed together
- harder processing and exports

## Final Choice

Destination structure:

DESTINATION_FOLDER/
└── YYYY/
    └── MM - Month/
        ├── photo/
        ├── video/
        └── unknown/

## Tradeoffs

- deeper folder nesting
- more directories created

Benefits:
- scalable
- predictable
- automation-friendly
- easy browsing
- easy backup verification

## Future Risks

- future edited/export folders may need separate conventions
- timezone-based month boundary edge cases
