# Decision 0006 - Configuration Strategy

## Problem

SnapSync requires configurable behavior across different machines, storage locations, and environments.

Hardcoded paths and constants would make the system difficult to maintain, migrate, or reuse.

## Options Considered

1. Hardcoded values in source code
2. JSON/YAML config file
3. Environment variables via `.env`
4. Database-driven configuration

## Why Rejected

### Hardcoded values
- difficult to migrate
- poor portability
- dangerous for backups
- creates environment coupling

### Database-driven configuration
- unnecessary complexity for MVP
- harder local debugging

## Final Choice

SnapSync uses environment-based configuration via `.env`.

Application behavior is controlled through centralized configuration loading.

## Example

DESTINATION_FOLDER=/Volumes/VINU_BKP1/1_Photo_Video_Vault

`VAULT_ROOT` remains supported as a legacy alias during the rename to
`DESTINATION_FOLDER`.

## Configuration Scope

The following settings should be externally configurable:

- destination folder path
- ExifTool executable path
- allowed media extensions
- ignored folders
- duplicate strategy
- dry-run mode
- logging verbosity
- device naming normalization
- filename prefix for local test runs
- filename hash length
- future database location

## Rules

- No machine-specific paths inside business logic.
- No duplicated constants across modules.
- All configuration access should happen through a centralized config layer.
- Missing required configuration should fail fast during startup.
- Missing ExifTool should fail fast during startup.

## Tradeoffs

- slightly more setup required
- environment management needed
- ExifTool must be installed outside pip

Benefits:
- portable
- easier migration
- easier testing
- future cloud/NAS support
- cleaner architecture

## Future Risks

- configuration drift across machines
- invalid environment values
- secret/config leakage if `.env` is committed accidentally
