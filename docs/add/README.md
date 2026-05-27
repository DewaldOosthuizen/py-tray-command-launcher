# Architecture Design Decisions (ADD)

This folder contains Architecture Design Decision records for
`py-tray-command-launcher`.  Each record captures a specific decision made
during the design or evolution of the project: the context that made the
decision necessary, the options that were considered, the choice that was made,
and the consequences — both positive and negative.

Records are numbered sequentially and kept permanently, even when superseded.
A superseded record is marked as such and links to its replacement so the full
history of reasoning is preserved.

## Index

| # | Title | Status |
|---|-------|--------|
| [ADD-001](ADD-001-configuration-storage-and-platform-paths.md) | Configuration storage and platform paths | Accepted |
| [ADD-002](ADD-002-singleton-config-manager.md) | Singleton ConfigManager — module-level instance | Accepted |
| [ADD-003](ADD-003-dependency-injection-via-appservices.md) | Dependency injection via AppServices dataclass | Accepted |
| [ADD-004](ADD-004-command-schema-and-validation.md) | commands.json schema and soft validation | Accepted |
| [ADD-005](ADD-005-atomic-json-writes.md) | Atomic JSON writes via temp-file rename | Accepted |
| [ADD-006](ADD-006-menu-builder-decomposition.md) | MenuBuilder extraction from TrayApp | Accepted |
| [ADD-007](ADD-007-icon-resolver-and-cache.md) | IconResolver with TTL-aware local cache | Accepted |
| [ADD-008](ADD-008-single-instance-locking.md) | Single-instance locking — QSharedMemory + PID file | Accepted |
| [ADD-009](ADD-009-command-execution-strategies.md) | Command execution strategies — subprocess vs QProcess | Accepted |
| [ADD-010](ADD-010-theming-via-qss.md) | Theming via QSS stylesheets | Accepted |
| [ADD-011](ADD-011-command-palette-and-global-hotkeys.md) | Command palette and global hotkeys via pynput | Accepted |
| [ADD-012](ADD-012-favorites-path-encoding.md) | Favorites command path encoding | Accepted |
| [ADD-013](ADD-013-file-encryption.md) | File encryption with Fernet and PBKDF2 | Accepted |
| [ADD-014](ADD-014-scheduling-via-cron.md) | Command scheduling via cron / Task Scheduler | Accepted |
| [ADD-015](ADD-015-app-discovery-desktop-files.md) | App discovery via .desktop file scanning | Accepted |

## Status vocabulary

- **Accepted** — current and in effect
- **Superseded** — replaced by a later decision; kept for history
- **Deprecated** — no longer recommended; will be replaced
- **Proposed** — under discussion; not yet enacted
