# Architecture

An overview of the codebase structure, module responsibilities, and key data flows.

---

## Directory Layout

```
py-tray-command-launcher/
├── src/                    # All application source code
│   ├── main.py             # Entry point
│   ├── core/               # Application lifecycle and shared services
│   ├── modules/            # Feature modules (self-contained capabilities)
│   └── utils/              # Low-level helpers with no Qt dependencies
├── config/                 # Bundled default configuration files
├── resources/              # Icons and other static assets
│   └── icons/
├── scripts/                # Build and packaging scripts
├── tests/                  # Automated tests
├── packaging/              # Desktop integration files (.desktop, etc.)
└── openspec/               # Change management and design specs
```

---

## Core Modules (`src/core/`)

### `main.py`

Entry point. Enforces single-instance check, initialises logging, creates the `QApplication`, instantiates `TrayApp`, and starts the Qt event loop.

### `core/tray_app.py` — `TrayApp`

Main application class. Builds and owns the system tray icon and entire menu hierarchy. Delegates all feature actions to the appropriate module. Manages application-level actions (restart, quit).

### `core/config_manager.py` — `ConfigManager`

Singleton that owns all file I/O for configuration. Resolves the user config directory (XDG on Linux, `%APPDATA%` on Windows), copies bundled defaults on first run, migrates legacy paths, loads/saves `commands.json`, `settings.json`, `history.json`, and `favorites.json`. All other modules use `config_manager` (the module-level singleton instance) rather than reading files directly.

### `core/logging_config.py`

Configures the root logger once at startup. Resolves the effective log level by checking the `PY_TRAY_LOG_LEVEL` environment variable first, then the `log_level` field from `settings.json`. Sets a standard format: `timestamp | level | logger name | message`.

### `core/output_window.py` — `OutputWindow`

A `QDialog` subclass that displays captured stdout/stderr from commands where `showOutput` is `true`. Supports scrolling and copy-to-clipboard.

---

## Feature Modules (`src/modules/`)

### `modules/command_executor.py`

Executes shell commands. Handles subprocess spawning, optional output capture, optional confirmation dialog, and `{promptInput}` substitution before execution.

### `modules/command_search.py`

Implements the command search dialog. Builds a flat list of all commands across categories, filters in real time as the user types, and executes the selected command on confirmation.

### `modules/command_creator.py`

Provides the GUI wizard for creating new commands without editing JSON. Writes the new entry via `config_manager` and triggers a menu refresh.

### `modules/command_history.py`

Records executed commands to `history.json` via `config_manager`. Supplies the Recent Commands submenu and enforces the history depth limit.

### `modules/favorites.py`

Manages the Favorites list stored in `favorites.json`. Provides add/remove operations and renders the Favorites submenu.

### `modules/backup_restore.py`

Creates timestamped backups of `commands.json` and restores from a user-selected backup file. Backups are written to the `backups/` subdirectory inside the user config directory.

### `modules/import_export.py`

Exports the current command set (or a specific category) to a user-chosen `.json` file. Imports from a `.json` file, merging or replacing categories.

### `modules/file_encryptor.py`

Password-based file and folder encryption using PBKDF2 (SHA-256, 100,000 iterations) for key derivation and Fernet (AES-128-CBC + HMAC) for encryption. Runs the cipher operation in a `QThread` (`EncryptionWorker`) to keep the UI responsive. Encrypted files are written as `<original>.enc`; salt is stored in `<original>.salt`.

### `modules/schedule_creator.py`

Shows a dialog to schedule a command via cron. Builds a cron expression from the selected time and days, then writes it using `crontab`.

### `modules/schedule_viewer.py`

Shows existing scheduled commands sourced from the user's crontab. Allows removal of individual scheduled entries.

---

## Utilities (`src/utils/`)

### `utils/utils.py`

General-purpose helpers: `get_base_dir()` (resolves the app root for both source and PyInstaller-frozen runs), `load_commands()` / `save_commands()` shims (delegate to `config_manager`), and `show_error_message()`.

### `utils/dialogs.py`

Reusable `QDialog` subclasses for confirmation prompts, text input, and generic message display used by multiple modules.

### `utils/single_instance.py` — `SingleInstanceChecker`

Uses `QSharedMemory` to guarantee only one process instance runs at a time. Optionally writes the current PID to a lock file. Handles stale locks gracefully (checks whether the recorded PID is still alive before refusing to start).

---

## Startup Data Flow

```
main.py
  │
  ├─ SingleInstanceChecker.check()       # abort if already running
  ├─ configure_logging()                 # load settings, set log level
  ├─ QApplication()
  └─ TrayApp()
       │
       ├─ config_manager (singleton)     # load commands.json
       ├─ QSystemTrayIcon + QMenu        # build menu from commands
       └─ Register modules               # executor, search, creator, history…
            │
            └─ Qt event loop (app.exec())
```

---

## Logging

All modules use the standard `logging` module with `logger = logging.getLogger(__name__)`. The root logger is configured once by `configure_logging()` in `core/logging_config.py`.

Log level resolution order (highest priority first):

1. `PY_TRAY_LOG_LEVEL` environment variable
2. `log_level` field in `settings.json`
3. Default: `INFO`

Log format: `2026-01-01 12:00:00,000 | INFO | core.config_manager | message`
