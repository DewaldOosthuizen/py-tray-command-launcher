# AI Agent Guide

A guide for AI agents (Hermes, GitHub Copilot, Codex, etc.) working in this
repository. For human contributors, see [Contributing](contributing.md).

---

## Code Exploration

### codegraph

`.codegraph/` is present. Use it FIRST for any symbol lookup, call tracing, or
targeted context gathering before opening source files.

```bash
codegraph context "<task description>" -p .   # focused file+symbol context
codegraph query "<ClassName or function>" -p . # where is X defined / used
codegraph affected <changed-files> -p .        # which tests are affected
codegraph sync .                               # after any code change
```

Decision order for code tasks:
  1. codegraph context     — which symbols matter?
  2. graphify query        — which files are involved?
  3. understand-anything   — where in the architecture does this live?
  4. Read raw source       — only the 1-2 files that actually matter.

### understand-anything

`.understand-anything/knowledge-graph.json` is present.
Use it for layered architecture questions (layers, communities, entry points).

```bash
# Launch the interactive dashboard
cd ~/.understand-anything-plugin/packages/dashboard
GRAPH_DIR=$(pwd) npx vite --host 127.0.0.1
```

For prose questions load the skill:

```
skill: understand-chat
```

### graphify

`graphify-out/` not yet generated for this repo.

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
│   └── settings_dialog.py   # App preferences dialog
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

## Key Design Decisions

### 1. ConfigManager is a module-level singleton
```python
from core.config_manager import config_manager   # always import the instance
```
Never instantiate `ConfigManager()` directly. It reads from:
1. CLI `--config <path>` override (highest priority)
2. `~/.config/py-tray-command-launcher/commands.json` (user config)
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
/tmp/py-tray-command-launcher-icons/<md5-of-url>.<ext>
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

---

## Architecture Design Decisions

Read `docs/add/` before making architectural changes. Key decisions:

| ADD | Decision |
|-----|---------|
| ADD-001 | Config storage uses XDG base dirs (`~/.config/py-tray-command-launcher/`) |
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
- User config: `~/.config/py-tray-command-launcher/commands.json`
- Favorites: `~/.config/py-tray-command-launcher/favorites.json`
- Icon cache: `/tmp/py-tray-command-launcher-icons/`
- Logs: `~/.local/share/py-tray-command-launcher/app.log`

### Test count
50 tests across 5 files — all should pass on every commit.

---

## Notes for AI Agents

- PyQt6 >= 6.11.0 is the GUI framework. The system may have PyQt5 installed — do not confuse them.
- Test files must stub PyQt6 at module level via sys.modules injection before importing src modules
  when the host only has PyQt5 (e.g. `sys.modules["PyQt6"] = MagicMock()`).
- Dependabot manages dependency updates (weekly, Monday). A pip-audit step runs on every push/PR.
- openspec is used for spec-driven change workflow in this repo.
- All architectural decisions are recorded as ADDs in `docs/add/`.
