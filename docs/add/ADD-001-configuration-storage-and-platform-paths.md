# ADD-001 — Configuration storage and platform paths

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | config, storage, cross-platform |

---

## Context

The application needs to persist several kinds of user data:

- `commands.json` — the command catalogue
- `settings.json` — UI preferences (theme, hotkey, log level, etc.)
- `history.json` — recent command invocations
- `favorites.json` — pinned favourite commands
- `backups/` — timestamped backups of commands.json

Each platform has a canonical location for user-specific application config that
should be respected so that the data does not pollute the repository, the user's
home directory root, or any system-managed path.

Additionally, the application ships with a `resources/` tree (icons, QSS
themes) that lives relative to the source tree in development but must be
resolved against `sys._MEIPASS` when running as a PyInstaller bundle, or
against the executable's directory when distributed as an AppImage.

---

## Decision

### User config directory

Config files are stored under a platform-specific directory resolved at startup
by `ConfigManager._get_user_config_dir()`:

| Platform | Path |
|----------|------|
| Linux / macOS | `$XDG_CONFIG_HOME/py-tray-launcher` or `~/.config/py-tray-launcher` |
| Windows | `%APPDATA%\py-tray-launcher` |

The directory is created with `mkdir(parents=True, exist_ok=True)` on first
run, so no installer or setup step is required.

### Resource / base directory

The source root (containing `resources/`, `config/`) is located by
`_get_base_dir()`, a module-level private function in `config_manager.py`:

1. `sys._MEIPASS` — set by PyInstaller; used when running as a frozen bundle.
2. Parent of `sys.executable` — used for AppImage / system installs where
   resources sit alongside the executable.
3. Parent-of-parent of `__file__` — the project root during normal source runs.

The resolved path is stored as `ConfigManager.base_dir` and propagated to
`IconResolver` and `ThemeManager` so they all agree on where to find bundled
assets.

### Windows dual-file strategy

Windows uses a separate `win-commands.json` for commands that contain
Windows-specific paths or executables.  `_get_commands_file_for_read()`
returns `win-commands.json` on Windows if it exists; all writes still target
the primary `commands.json` so the two files stay in sync.

---

## Alternatives considered

**Store config in the project directory** — rejected: pollutes the repository,
breaks read-only installs, and conflicts with multiple concurrent users.

**Use a third-party config library (e.g. `appdirs`)** — rejected: the logic is
small enough to own directly; avoids an extra dependency and keeps the platform
detection close to the code that uses it.

**Single config path regardless of platform** — rejected: breaks the principle
of least surprise for users on each OS and complicates packaging.

---

## Consequences

+ The app works correctly in source, PyInstaller, and AppImage packaging modes
  without any code changes between distributions.
+ Config data survives application updates because it lives outside the
  installation directory.
+ Windows users get a commands file that matches their environment without
  manual path translation.
- Two commands files (Linux and Windows) can drift out of sync if the user
  edits one manually; there is no automatic merge or diff tool provided.
- The `_get_base_dir()` fallback chain is implicit; a developer unfamiliar with
  the pattern may find icon/theme resolution confusing.
