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

Composition root for the application. Creates the tray icon, shared services, and focused menu, module-wiring, and theme controllers; coordinates application-level startup and shutdown.

### `core/menu_controller.py` — `MenuController`

Owns the lazy first-build flag, tray-menu attachment/show lifecycle, command reload/rebuild decisions, and refresh of history and favorites submenus. It delegates rendering to `MenuBuilder`; menu construction remains deferred until the first tray-menu display.

### `core/menu_builder.py` — `MenuBuilder`

Renders the hierarchical tray menu using an immutable, typed `MenuBuilderDependencies` contract. The contract supplies command data, icon resolution, lazy feature accessors, action callbacks, and menu-state handoffs. The builder neither stores nor accepts a `TrayApp` instance.

### `core/module_controller.py` — `ModuleController`

Owns explicit cache-on-first-use factories for feature modules, `CommandPalette`, and `QuickLaunchBar`. It receives `AppServices`, the tray icon path, and a settings accessor; it does not receive `TrayApp` and does not use dynamic attribute proxies.

### `core/theme_controller.py` — `ThemeController`

Reads the persisted startup theme and delegates theme changes to `ThemeManager`. `ThemeManager` remains responsible for QSS lookup, fallback, and global stylesheet application. Its manager capability is passed to `SettingsDialog` for live preview and rollback.

### `core/config_manager.py` — `ConfigManager`

Singleton that owns all file I/O for configuration. Resolves the user config directory (XDG on Linux, `%APPDATA%` on Windows), copies bundled defaults on first run, migrates legacy paths, loads/saves `commands.json`, `settings.json`, `history.json`, and `favorites.json`. All other modules use `config_manager` (the module-level singleton instance) rather than reading files directly.

### `core/logging_config.py`

Configures the root logger once at startup. Resolves the effective log level by checking the `PY_TRAY_LOG_LEVEL` environment variable first, then the `log_level` field from `settings.json`. Sets a standard format: `timestamp | level | logger name | message`.

### `core/output_window.py` — `OutputWindow`

A `QDialog` subclass that displays captured stdout/stderr from commands where `showOutput` is `true`. Supports scrolling and copy-to-clipboard.

### `core/services.py` — `AppServices`

The `AppServices` dataclass is a thin service interface passed to every feature module. It decouples modules from the `TrayApp` god-object so each module depends only on the specific callables it actually needs. The canonical wiring site is `TrayApp._build_services()` (`src/core/tray_app.py` lines 112-132), which constructs the `AppServices` instance and connects each field to the corresponding `TrayApp` method or collaborator.

#### Field reference

Every field below is declared at `src/core/services.py` lines 25-35.

| Field | Type | Provides | Backed by |
|-------|------|----------|-----------|
| `config_manager` | `ConfigManager` | Central config I/O: load/save `commands.json`, `settings.json`, `history.json`, `favorites.json`, resolve paths, migrate legacy files | Module-level singleton `config_manager` from `core.config_manager` (imported at `tray_app.py` line 14) |
| `execute` | `Callable[[str, str, bool, bool, str \| None], None]` | Execute a command with optional confirmation, output capture, and prompt substitution | `TrayApp.execute()` (`tray_app.py` line 201) |
| `reload_commands` | `Callable[..., None]` | Reload the command menu from disk and optionally rebuild the tray menu | `TrayApp.reload_commands()` (`tray_app.py` line 339) |
| `show_output` | `Callable[[str, str], None]` | Execute a command and display its stdout/stderr in a `RichOutputWindow` | `TrayApp.show_command_output()` (`tray_app.py` line 245) |
| `get_all_commands` | `Callable[[], list]` | Return a flat list of all commands across all groups, suitable for search/dialogs | `TrayApp.get_all_commands()` (`tray_app.py` line 287) |
| `save_commands` | `Callable[[dict], None]` | Persist the command dictionary to disk (with backup) | `TrayApp.save_commands()` (`tray_app.py` line 280) |
| `reload_history_commands` | `Callable[[], None]` | Refresh the Recent Commands submenu from history | `TrayApp.reload_history_commands()` (`tray_app.py` line 359) |
| `reload_favorites_commands` | `Callable[[], None]` | Refresh the Favorites submenu | `TrayApp.reload_favorites_commands()` (`tray_app.py` line 363) |
| `resolve_icon_path` | `Callable[[str], str]` | Resolve a logical icon path to a concrete filesystem path using `IconResolver` | `TrayApp._resolve_icon_path()` (`tray_app.py` line 176) |
| `notify_user` | `Callable[[str, str], None]` | Show a tray notification (title + message) | `TrayApp.notify_user()` (`tray_app.py` line 241) |
| `process_tracker` | `ProcessTracker` | Track running subprocesses, emit `process_count_changed` signal, allow removal | `ProcessTracker(self.app)` constructed at `tray_app.py` line 109 |

#### Example module consumption

```python
# src/modules/my_new_module.py
from core.services import AppServices

class MyNewModule:
    def __init__(self, services: AppServices):
        self.services = services

    def do_something(self):
        # Read settings via the DI contract — NOT by importing config_manager directly
        settings = self.services.config_manager.get_settings()
        # Execute a command
        self.services.execute("My Action", "echo hello", confirm=False, show_output=True, prompt=None)
        # Show a notification
        self.services.notify_user("Done", "Action completed")
```

---

## Adding a new module

This guide walks through adding a new feature module to the application. Follow these steps in order.

### Step 1: Create the module file

Create a new file under `src/modules/`, e.g. `src/modules/my_new_module.py`. Every module is a plain Python class that accepts `AppServices` in its constructor and stores it as `self.services`.

```python
# src/modules/my_new_module.py
from core.services import AppServices

class MyNewModule:
    """Brief description of what this module does."""

    def __init__(self, services: AppServices):
        self.services = services
```

### Step 2: Use `self.services` — never import `config_manager` directly

**Do NOT do this:**

```python
# WRONG — creates hidden coupling to the singleton
from core.config_manager import config_manager

class MyNewModule:
    def __init__(self):
        self.settings = config_manager.get_settings()
```

**Do this instead:**

```python
# CORRECT — uses the DI contract
class MyNewModule:
    def __init__(self, services: AppServices):
        self.services = services

    def read_settings(self):
        return self.services.config_manager.get_settings()
```

**Why:** `ConfigManager` has a module-level singleton (`config_manager` at `src/core/config_manager.py` bottom) intended for application code. Importing it directly in a module bypasses the `AppServices` interface, creates an implicit dependency that is invisible to anyone reading the module's `__init__` signature, and makes testing harder because the module reaches outside its injected dependencies. The `ConfigManager` class docstring (`src/core/config_manager.py` lines 42-54) already documents the singleton-vs-test-instance distinction: in tests, instantiate `ConfigManager()` directly with a custom `config_dir`; importing the singleton name from application code would create a second independent instance with its own cache state, breaking the isolation that `AppServices` is designed to provide.

### Step 3: Wire the module into `TrayApp`

Add the module import and an explicit lazy factory to `ModuleController`. The factory must pass `AppServices`, store its instance in a controller-owned slot, and return the same instance on subsequent calls. Add an explicit `TrayApp.get_*()` delegate when an application access point is needed:

```python
# src/core/module_controller.py
def get_my_new_module(self):
    if self._my_new_module is None:
        self._my_new_module = MyNewModule(self.services)
    return self._my_new_module
```

### Step 4: Register tray-menu actions (if needed)

If your module adds tray-menu items, add its action through the typed rendering contract consumed by `MenuBuilder`; keep lifecycle and refresh decisions in `MenuController`. The existing pattern is:

- `TrayApp` composes `MenuBuilderDependencies` from command data, `IconResolver`, explicit module accessors, and application action callbacks; `MenuController` invokes the builder on first show or explicit rebuild.
- Modules that contribute submenus (e.g. `CommandHistory`, `Favorites`) expose methods like `populate_menu()` or `populate_favorites_menu()` that `MenuController` calls only when their submenu exists.

Follow whichever pattern matches your module's needs. If your module only reacts to menu-triggered signals connected elsewhere, no changes to `_build_menu()` are required.

### Step 5: Add tests

Add tests under `tests/` using a per-test `ConfigManager` instance. Do not rely on the module-level `config_manager` singleton in tests — it is shared state across tests. Instead, instantiate `ConfigManager()` directly with a temp `config_dir`, as documented in the `ConfigManager` class docstring (`src/core/config_manager.py` lines 51-53):

```python
# tests/test_my_new_module.py
import tempfile
from pathlib import Path
from core.config_manager import ConfigManager
from core.services import AppServices
from src.modules.my_new_module import MyNewModule

class TestMyNewModule:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager()  # per-test instance
        # Patch config_dir if needed for isolation
        self.services = AppServices(
            config_manager=self.config_manager,
            execute=lambda *a, **kw: None,
            reload_commands=lambda: None,
            show_output=lambda *a, **kw: None,
            get_all_commands=lambda: [],
            save_commands=lambda *a, **kw: None,
            reload_history_commands=lambda: None,
            reload_favorites_commands=lambda: None,
            resolve_icon_path=lambda p: p,
            notify_user=lambda *a, **kw: None,
            process_tracker=None,  # mock or pass a real ProcessTracker in integration tests
        )
        self.module = MyNewModule(self.services)

    def test_something(self):
        result = self.module.do_something()
        assert result is not None
```

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

Password-based file and folder encryption using PBKDF2 (SHA-256, 600,000 iterations for new files) for key derivation and Fernet (AES-128-CBC + HMAC) for encryption. Runs the cipher operation in a `QThread` (`EncryptionWorker`) to keep the UI responsive. Encrypted files are written as `<original>.enc`; salt is stored in `<original>.salt` using a versioned format: V0 (16 bytes, legacy, 100,000 iterations), V1 (20 bytes, 4-byte iteration prefix + 16-byte salt, read-only), V2 (57 bytes, authenticated: magic "PTCL" + version 0x02 + iterations + 16-byte salt + HMAC-SHA256). Iterations bounds-checked to 1..10,000,000; V2 HMAC verified fail-closed before key derivation. Encrypt/decrypt use atomic temp-file + os.replace writes with cleanup on failure.

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
       ├─ config_manager (singleton)     # load commands.json and settings
       ├─ ThemeController                # apply startup theme via ThemeManager
       ├─ ModuleController               # explicit lazy feature/UI factories
       ├─ MenuController                 # attach now; render on first display
       │    └─ MenuBuilder               # render via typed dependencies
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

## Lazy construction and controller ownership

`ModuleController` owns explicit factories and cached slots for each feature
module and UI module. `TrayApp` keeps explicit `get_*()` methods as composition
boundary delegates; there is no transparent `__getattr__` proxy, so Qt identity,
`isinstance`, and slot semantics are preserved. Feature modules receive only
`AppServices`, never the `TrayApp` instance.

### Delayed hotkey registration API

Hotkey registration remains settings-driven at first construction. Hotkey
re-registration (`_reregister_hotkey`, `_reregister_app_launcher_hotkey`,
`_reregister_bar_hotkey`) checks the controller's already-loaded slots and
never instantiates an unused module during settings changes.

### Factory registration sites

Module factories are explicit methods on `ModuleController`; their constructor
dependencies are composed in `TrayApp`. `AppServices` remains the feature-module
dependency contract and its fields are unchanged.

### Cleanup invariants

`ModuleController.cleanup()` only unregisters/closes already-loaded UI modules;
settings callbacks likewise inspect loaded slots without constructing them.
`MenuController` attaches the context menu and defers heavy rendering until the
first `aboutToShow` signal, so startup does not construct lazy feature modules.
