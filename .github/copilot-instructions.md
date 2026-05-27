# py-tray-command-launcher — Copilot Instructions

py-tray-command-launcher is a Python/PyQt6 system tray application for launching
custom shell commands from a hierarchical context menu. Features include favorites,
quick-launch bar, fuzzy command palette, command history, file encryption, cron
scheduling, app discovery via .desktop files, dark/light theming, import/export,
and backup/restore.

Always reference these instructions first and fall back to search or bash only when
you encounter something that does not match the info here.

---

## Code Exploration and Token Efficiency

- If `.codegraph/` exists, use CodeGraph tools FIRST for symbol lookup, context
  gathering, and call tracing before opening any source files.
  ```bash
  codegraph context "<task description>" -p .
  codegraph query "<ClassName or function>" -p .
  codegraph affected <changed-files> -p .   # find affected tests
  codegraph sync .                          # after any code changes
  ```
- If `.understand-anything/knowledge-graph.json` exists, use it for architecture
  questions (layers, relationships, guided tour) — launch the dashboard with:
  ```bash
  cd ~/.understand-anything-plugin/packages/dashboard
  GRAPH_DIR=/path/to/project npx vite --host 127.0.0.1
  ```
- Fall back to grep/file reading only when both tools return insufficient results.

---

## Architecture Overview

```
src/
├── main.py                  # Entry point — argparse, single-instance lock, QApplication
├── core/
│   ├── config_manager.py    # SINGLETON — all config reads go through config_manager
│   ├── services.py          # AppServices dataclass — dependency injection container
│   ├── tray_app.py          # TrayApp(QSystemTrayIcon) — orchestrates everything
│   ├── menu_builder.py      # Builds QMenu tree from config; context menus for items
│   ├── icon_resolver.py     # Resolves icons: bundled → XDG → URL download + TTL cache
│   ├── theme_manager.py     # Loads dark.qss / light.qss; applies to QApplication
│   └── logging_config.py    # Structured logging setup
├── modules/                 # Self-contained feature modules
│   ├── command_executor.py  # subprocess.Popen (with output) OR QProcess (silent)
│   ├── command_search.py    # Fuzzy search via rapidfuzz over full command tree
│   ├── command_creator.py   # GUI dialog to create/edit commands
│   ├── command_history.py   # Tracks recently executed commands
│   ├── favorites.py         # Pin/unpin commands; dot-path key encoding
│   ├── backup_restore.py    # JSON backup and restore of config + favorites
│   ├── import_export.py     # Import/export commands to/from external JSON
│   ├── file_encryptor.py    # Fernet + PBKDF2 encryption of config files
│   ├── schedule_creator.py  # Create cron jobs (Linux) or Task Scheduler (Windows)
│   ├── schedule_viewer.py   # List and delete existing schedules
│   └── app_discovery.py     # Scan /usr/share/applications for .desktop files
├── ui/                      # PyQt6 dialogs and widgets
│   ├── command_palette.py   # Floating fuzzy search palette (global hotkey trigger)
│   ├── output_window.py     # Rich output display for command stdout/stderr
│   ├── quick_launch_bar.py  # Floating toolbar of pinned favourite commands
│   ├── command_manager.py   # Full command tree browser/editor dialog
│   └── settings_dialog.py  # App preferences dialog
└── utils/
    └── single_instance.py   # QSharedMemory + PID file lock; Wayland-aware
config/
├── commands.json            # User command config (runtime, written by the app)
├── commands.schema.json     # JSON Schema draft-07 for validation
└── win-commands.json        # Windows command examples
resources/
├── icons/                   # Bundled icons (icon.png = main tray icon)
└── themes/                  # dark.qss and light.qss QSS stylesheets
tests/                       # pytest test suite (50 tests, all passing)
docs/add/                    # Architecture Design Decision records (ADD-001..015)
openspec/                    # Change proposals and spec-driven tasks
```

---

## Key Design Decisions (read before making changes)

### 1. ConfigManager is a module-level singleton
```python
from core.config_manager import config_manager   # always import the instance
```
Never instantiate `ConfigManager()` directly. It reads from:
1. CLI `--config <path>` override (highest priority)
2. `~/.config/py-tray-launcher/commands.json` (user config)
3. `config/commands.json` (bundled default)

Config writes use atomic temp-file rename to prevent corruption.

### 2. AppServices is the dependency injection container
```python
@dataclass
class AppServices:
    config_manager: ConfigManager
    command_executor: CommandExecutor
    favorites_manager: FavoritesManager
    # ... etc
```
All major modules receive an `AppServices` instance — never import modules directly
from each other if AppServices already wires them. See `src/core/services.py`.

### 3. Command execution has two modes
- `execute_command(cmd)` — subprocess.Popen, captures stdout/stderr, shows OutputWindow
- `execute_command_silently(cmd)` — QProcess.start(), fire-and-forget, no output window

Choose based on whether the user needs to see output. Always call `QProcess.start()`
before returning from the silent path.

### 4. Favorites use dot-path encoding
Favorite keys are `"group.label"` (dot-separated), NOT `"group → label"`.
Always build keys via `_build_command_path(group, label)` in `favorites.py`.
Never construct favorite keys by string concatenation with ` → `.

### 5. Schema validation is soft (warn, don't crash)
`config_manager._validate_commands()` logs warnings for unknown fields but never
raises. Items missing a `command` key are silently skipped — this is intentional
to support group-only entries. Only non-dict items raise ValueError.

### 6. Icon cache lives in /tmp
```
/tmp/py-tray-launcher-icons/<md5-of-url>.<ext>
```
TTL is configurable. When `_cache_ttl_seconds == 0`, TTL check is skipped entirely
(treat as permanent cache).

### 7. Single-instance uses QSharedMemory + PID file
`--force-unlock` CLI flag clears a stale lock. On Wayland, falls back to PID file
only (QSharedMemory is unreliable on Wayland).

### 8. Qt argument separation
Qt args are passed as `QApplication([sys.argv[0]] + qt_args)` so argparse and
Qt don't interfere with each other.

---

## Bootstrap, Build, and Test

**NEVER CANCEL these commands — all complete within expected timeframes.**

```bash
# 1. System dependencies (20-30s — NEVER CANCEL)
sudo bash scripts/install_packages.sh

# 2. Virtual environment (3-5s)
python3 -m venv venv
source venv/bin/activate

# 3. Python dependencies (4-6s — NEVER CANCEL)
pip install -r requirements.txt

# 4. Validate installation
python3 -c "import sys; sys.path.append('src'); from core.tray_app import TrayApp; print('OK')"
```

---

## Running the Application

```bash
# Normal GUI mode
source venv/bin/activate && python3 src/main.py

# With custom config
source venv/bin/activate && python3 src/main.py --config /path/to/commands.json

# Force release stale single-instance lock
source venv/bin/activate && python3 src/main.py --force-unlock

# Headless validation (CI / no display)
QT_QPA_PLATFORM=offscreen timeout 5 python3 src/main.py

# Background
nohup python3 src/main.py &
```

---

## Running Tests

```bash
source venv/bin/activate
pytest tests/ -v                  # all 50 tests
pytest tests/test_config_manager.py -v
pytest tests/test_favorites_path.py -v
pytest tests/test_icon_resolver.py -v
pytest tests/test_single_instance.py -v
pytest tests/test_command_executor.py -v
```

**Expected: 50/50 passing.**

### PyQt6 stub pattern in tests
The system may have PyQt5 installed, not PyQt6. Test files stub PyQt6 at module
level BEFORE importing any src modules:
```python
from unittest.mock import MagicMock
import sys
sys.modules["PyQt6"] = MagicMock()
sys.modules["PyQt6.QtWidgets"] = MagicMock()
sys.modules["PyQt6.QtCore"] = MagicMock()
sys.modules["PyQt6.QtGui"] = MagicMock()
# ...then import src modules
```
Always follow this pattern when writing new test files.

### resource_roots() patching
`IconResolver.resource_roots()` is a regular instance method — patch it on the
CLASS, not the instance:
```python
with patch.object(IconResolver, "resource_roots", return_value=[tmp_path]):
```
The test must create the icon at `tmp_path/resources/icons/<name>.png`.

---

## Code Quality

```bash
source venv/bin/activate

# Lint (ALWAYS before committing)
flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Format
black src/

# Syntax check all files
find src -name "*.py" -exec python3 -m py_compile {} \;

# Type hints (optional but encouraged)
mypy src/ --ignore-missing-imports
```

---

## Python Dependencies

| Package | Purpose |
|---------|---------|
| `PyQt6` | GUI framework — tray, menus, dialogs, QProcess |
| `pynput` | Global hotkey listener for command palette |
| `cryptography` | Fernet encryption + PBKDF2 key derivation |
| `jsonschema>=4.0` | Soft schema validation of commands.json |
| `rapidfuzz` | Fuzzy matching for command palette search |
| `pytest>=8.0` | Test runner |
| `pytest-qt>=4.4` | Qt widget testing support |

Full list in `requirements.txt`. Build/packaging deps in `requirements-build.txt`.

System packages installed by `scripts/install_packages.sh`:
`libxcb-xinerama0`, `libxcb-cursor0`, `policykit-1`, `libegl1`

---

## Adding a New Feature Module

1. Create `src/modules/<feature>.py` with a class that accepts `AppServices` in `__init__`
2. Add the instance to `AppServices` dataclass in `src/core/services.py`
3. Wire it into `TrayApp.__init__()` or `MenuBuilder` as needed
4. Add a menu entry in `menu_builder.py` if it needs a tray menu item
5. Write tests in `tests/test_<feature>.py` using the PyQt6 stub pattern
6. Run `codegraph sync .` to update the symbol index

---

## Adding a New UI Dialog

1. Create `src/ui/<dialog>.py` subclassing `QDialog`
2. Use `QSS` from `theme_manager` for consistent styling — call
   `self.setStyleSheet(services.theme_manager.current_stylesheet())`
3. Emit a signal or return value on accept/reject — don't call services directly
4. Wire the trigger in `tray_app.py` or `menu_builder.py`

---

## Working with commands.json

Structure:
```json
{
  "GroupName": {
    "CommandLabel": {
      "command": "shell command here",
      "showOutput": true,
      "confirm": false,
      "icon": "optional-icon-name-or-url"
    }
  }
}
```

- `showOutput: true` → runs via subprocess, shows OutputWindow
- `showOutput: false` → runs via QProcess, silent
- `confirm: true` → shows confirmation dialog before executing
- `icon` → icon name (XDG), relative path, or URL (cached to /tmp)
- `{promptInput}` → placeholder replaced with user input at runtime

Validate after manual edits:
```bash
python3 -c "import json; json.load(open('config/commands.json')); print('valid')"
```

---

## Theming

QSS files at `resources/themes/dark.qss` and `resources/themes/light.qss`.
`ThemeManager` in `src/core/theme_manager.py` applies them to `QApplication`.

To add a new theme:
1. Create `resources/themes/<name>.qss`
2. Add the name to the themes list in `settings_dialog.py`
3. `ThemeManager` picks it up automatically by filename

Widget-level overrides via `setStyleSheet()` are fine but avoid inline styles —
keep all QSS in the theme files for consistency.

---

## Change Management (OpenSpec)

This project uses openspec for spec-driven change management:

```bash
# Propose a new change
openspec new change "<kebab-name>"

# List active changes
openspec list

# Check status of a change
openspec status --change "<name>"

# Get implementation instructions
openspec instructions apply --change "<name>"

# Archive completed change
openspec archive --change "<name>"
```

Change artifacts live in `openspec/changes/<name>/`:
- `proposal.md` — what and why
- `design.md` — how
- `tasks.md` — implementation checklist

Completed changes are moved to `openspec/changes/archive/`.
Use the skills in `.github/skills/openspec-*/` for full workflows.

---

## Architecture Design Decisions

Read `docs/add/` before making architectural changes. Key decisions:

| ADD | Decision |
|-----|---------|
| ADD-001 | Config storage uses XDG base dirs (`~/.config/py-tray-launcher/`) |
| ADD-002 | ConfigManager is a module-level singleton — never re-instantiate |
| ADD-003 | AppServices dataclass wires all dependencies — no direct cross-module imports |
| ADD-004 | commands.json schema validation is soft (warn, don't crash) |
| ADD-005 | All JSON writes use atomic temp-file rename |
| ADD-006 | MenuBuilder is extracted from TrayApp — keep menu logic out of tray_app.py |
| ADD-007 | Icons cached in /tmp with MD5-keyed filenames; TTL=0 means no expiry |
| ADD-008 | Single-instance via QSharedMemory + PID file; Wayland falls back to PID only |
| ADD-009 | Two execution modes: subprocess (output) and QProcess (silent) |
| ADD-010 | Theming via QSS files — no inline styles |
| ADD-011 | Global hotkey via pynput thread; palette shown on main Qt thread via signal |
| ADD-012 | Favorites keys are dot-separated "group.label" — never use " → " separator |
| ADD-013 | Encryption uses Fernet + PBKDF2 with user-supplied passphrase |
| ADD-014 | Scheduling delegates to OS: crontab on Linux, Task Scheduler on Windows |
| ADD-015 | App discovery scans /usr/share/applications for .desktop files |

---

## Known Limitations

- Full GUI requires a display server; use `QT_QPA_PLATFORM=offscreen` for CI
- System tray needs a compatible desktop environment (GNOME, KDE, XFCE, etc.)
- Windows support is secondary — `win-commands.json` provides examples but
  platform-specific code paths are minimal
- Global hotkeys via pynput may require accessibility permissions on some DEs
- Wayland: tray icon positioning and QSharedMemory have known Qt limitations

---

## Timing Reference

| Operation | Expected Time |
|-----------|--------------|
| System package install | 20-30s |
| venv creation | 3-5s |
| pip install | 4-6s |
| Import validation | <1s |
| pytest (50 tests) | 2-5s |
| Linting | <1s |
| codegraph sync | <2s |

Set timeouts generously (60s+ for installs, 30s for tests). NEVER CANCEL.

---

## Frequent Reference

### Config categories (commands.json)
System, Media, Studies, Utilities, Development, Networking, Favorites

### Runtime data paths
- User config: `~/.config/py-tray-launcher/commands.json`
- Favorites: `~/.config/py-tray-launcher/favorites.json`
- Icon cache: `/tmp/py-tray-launcher-icons/`
- Logs: `~/.local/share/py-tray-launcher/app.log`

### Test count
50 tests across 5 files — all should pass on every commit.
