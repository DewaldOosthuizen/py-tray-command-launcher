# Contributing to py-tray-command-launcher

## Architecture Overview

The source tree is organised into four top-level areas:

    src/
      core/          Orchestration and shared infrastructure
      modules/       Self-contained feature modules
      ui/            PyQt6 widgets and dialogs
      utils/         Thin cross-cutting helpers
      main.py        Entry point (argparse + QApplication bootstrap)

### core/ — Orchestration and DI

| File               | Responsibility                                              |
|--------------------|-------------------------------------------------------------|
| tray_app.py        | QSystemTrayIcon host; owns the Qt event loop                |
| services.py        | AppServices dataclass — the DI boundary                     |
| menu_builder.py    | Builds and rebuilds the tray context menu from commands     |
| config_manager.py  | Reads/writes commands.json and app config                   |
| theme_manager.py   | Loads and applies Qt stylesheets                            |
| icon_resolver.py   | Resolves icon paths (XDG, bundled, fallback)                |
| logging_config.py  | Configures the root logger                                  |

AppServices (core/services.py) is the single object passed to every feature
module. It exposes only the callables a module actually needs — execute,
reload_commands, save_commands, etc. — so modules never import TrayApp
directly.

### modules/ — Feature Logic

Each module is a self-contained unit that receives AppServices and operates
on the command data model. Modules must not import from ui/ or from each other.

| File                | Responsibility                                    |
|---------------------|---------------------------------------------------|
| command_executor.py | Launches commands via subprocess / QProcess       |
| command_search.py   | Fuzzy/keyword search over the command list        |
| command_creator.py  | Validates and creates new command entries         |
| command_history.py  | Tracks and replays recently executed commands     |
| favorites.py        | Pins/unpins commands to the quick-launch bar      |
| app_discovery.py    | Discovers installed applications from the OS     |
| schedule_creator.py | Creates cron / Task Scheduler entries             |
| schedule_viewer.py  | Lists and removes scheduled entries               |
| file_encryptor.py   | Encrypts/decrypts command data at rest            |
| backup_restore.py   | Exports and imports command archives              |
| import_export.py    | JSON import/export for individual command sets    |

### ui/ — PyQt6 Widgets

UI components present data and should prefer delegating logic via AppServices.
Widgets must not contain business logic.

| File               | Responsibility                                              |
|--------------------|-------------------------------------------------------------|
| command_palette.py | Full-screen command search and launch overlay               |
| quick_launch_bar.py| Persistent toolbar for pinned/favourite commands            |
| command_manager.py | CRUD dialog for editing the command list                    |
| settings_dialog.py | App-wide preferences dialog                                 |
| output_window.py   | Scrollable log window for command stdout/stderr             |

### utils/ — Cross-Cutting Helpers

| File               | Responsibility                                              |
|--------------------|-------------------------------------------------------------|
| single_instance.py | Prevents multiple app instances via `QSharedMemory` and a PID-file fallback |
| dialogs.py         | Shared QMessageBox/QInputDialog convenience wrappers        |

## Dependency Convention

`pyproject.toml` is the single source of truth for all runtime dependencies.
The `requirements.txt` file is only a dev-install convenience shim:

    -e ".[dev]"

It must never declare standalone version pins. If you need to add, remove, or
tighten a dependency (e.g. `PyQt6>=6.11.0`), edit `[project].dependencies` in
`pyproject.toml` only.

## Development Setup

    git clone https://github.com/DewaldOosthuizen/py-tray-command-launcher.git
    cd py-tray-command-launcher
    python3 -m venv .venv
    source .venv/bin/activate          # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    pip install ruff

Verify the setup:

    python3 -m pytest tests/           # all tests should pass
    bash scripts/lint.sh               # no lint errors (mirrors CI exactly)

## Adding a New Feature

Follow these steps to add a new capability to the launcher:

1. **Create a module** in `src/modules/my_feature.py`.
   - Accept `AppServices` in the constructor or as a function parameter.
   - Keep all business logic here; no PyQt6 imports unless you need QProcess.

2. **Expose it via AppServices** (`src/core/services.py`).
   - Add a typed callable field to the `AppServices` dataclass.
   - Wire it in `src/core/tray_app.py` where `AppServices` is instantiated.

3. **Add a menu entry** (`src/core/menu_builder.py`).
   - Call `services.<your_field>` from the action's triggered slot.

4. **Add a widget** (optional) in `src/ui/my_feature_dialog.py`.
   - Prefer receiving data via AppServices callables instead of importing from
     `modules/` directly.

5. **Write tests** in `tests/test_my_feature.py`.
   - Use the `mock_services` fixture from `conftest.py` to provide a fake AppServices.
   - If the module uses PyQt6, stub the import at the top of the test file (see
     "Test Conventions" below).

6. **Run lint and tests** before opening a PR:
      bash scripts/lint.sh
      python3 -m pytest tests/

## Linting

Run the linter before opening a PR using the local script that mirrors CI exactly:

    bash scripts/lint.sh

The script runs `ruff check src/ tests/` and `ruff format --check src/ tests/`
in sequence — identical to what the CI lint job executes. A non-zero exit means
lint would also fail in CI.

To auto-fix violations before reviewing manually:

    bash scripts/lint.sh --fix

The `--fix` flag runs `ruff format` and `ruff check --fix` first, then
re-runs the check. The output shows what remains after auto-fixing (if anything).

The CI workflow (`.github/workflows/lint.yml`) runs both commands on every push
and pull request. A PR cannot merge if either check fails.

## noqa Suppression Convention

All `noqa` suppressions must include a human-readable reason string after the
rule code. A bare suppression is not acceptable:

    # Bad
    subprocess.Popen(command, shell=True)  # noqa: S602

    # Good
    subprocess.Popen(command, shell=True)  # noqa: S602 — intentional: user-authored command, see method docstring

The reason must explain *why* the violation is safe or intentional so that
future reviewers can audit suppressions without having to reconstruct the
original context.

## Running Tests

    python3 -m pytest tests/

### Test Conventions

**PyQt6 headless stub** — Tests that import any `src/` module which transitively
imports PyQt6 must stub the entire PyQt6 namespace before the import. The canonical
pattern (already applied in all existing tests via `conftest.py`):

    import sys
    from unittest.mock import MagicMock

    # Must appear before any src/ import
    _pyqt6_stub = MagicMock()
    sys.modules.setdefault("PyQt6", _pyqt6_stub)
    sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6_stub.QtWidgets)
    sys.modules.setdefault("PyQt6.QtCore", _pyqt6_stub.QtCore)
    sys.modules.setdefault("PyQt6.QtGui", _pyqt6_stub.QtGui)

This is centralised in `tests/conftest.py`; individual test files do not need to
repeat it.

**Available fixtures** (defined in `tests/conftest.py`):

| Fixture            | What it provides                                       |
|--------------------|--------------------------------------------------------|
| `mock_services`    | A MagicMock-based AppServices with all fields stubbed  |
| `tmp_config_dir`   | A temporary directory wired as the app config path     |
| `tmp_commands_file`| A temporary commands.json with sample data             |

## Project-Level Ruff Ignores

The following rules are suppressed globally in `pyproject.toml` with documented
justifications:

- `E501`  — line length is managed by the formatter, not enforced manually.
- `S602`  — `subprocess` with `shell=True` is intentional in `CommandExecutor`
            (commands are user-authored, not external input).
- `S603`  — `subprocess` without shell is low-risk (fixed arg lists, no user
            string interpolation).
- `S606`  — `os.startfile` is intentional for launching user-configured paths
            on Windows.
- `S607`  — partial executable paths (`open`, `xdg-open`, `crontab`, `schtasks`)
            are platform-standard helpers, not user-controlled input.

## Commit and PR Guidelines

**Branch naming:**

    feature/<short-description>    e.g. feature/schedule-timezone-support
    fix/<short-description>        e.g. fix/icon-resolver-fallback
    docs/<short-description>       e.g. docs/contributing-architecture

**Commit messages:**
Use the imperative mood in the subject line (50 chars max):

    Add schedule timezone support
    Fix icon resolver fallback for missing XDG path
    Docs: expand CONTRIBUTING with architecture overview

Reference the issue in the body:

    Closes #51

**PR checklist before opening:**
- [ ] `bash scripts/lint.sh` — zero errors and zero formatting diffs
- [ ] `python3 -m pytest tests/` — all tests pass
- [ ] New feature includes at least one test
- [ ] Issue number referenced in the PR description

---

## Releasing a New Version

Releases are fully automated via `.github/workflows/release.yml`. There is no manual
build step — pushing a version tag is the entire release process.

### Steps

1. Merge all intended changes to `main` and push:

   ```bash
   git push origin main
   ```

2. Pick a version following [Semantic Versioning](https://semver.org):

   | Change type                  | Example bump        |
   |------------------------------|---------------------|
   | Bug fixes only               | v1.0.0 → v1.0.1     |
   | Backward-compatible feature  | v1.0.0 → v1.1.0     |
   | Breaking change              | v1.0.0 → v2.0.0     |

3. Create an annotated tag and push it:

   ```bash
   git tag v1.2.0 -m "Release v1.2.0"
   git push origin v1.2.0
   ```

4. The workflow runs automatically on GitHub Actions:
   - Builds the Linux executable with PyInstaller
   - Assembles the AppImage
   - Creates a GitHub Release with auto-generated release notes
   - Attaches `py-tray-command-launcher-v1.2.0-x86_64.AppImage` as a release asset

5. Verify the release on the repository's **Releases** page.

### Pre-releases

Tags with a hyphen suffix are marked as pre-releases automatically:

```bash
git tag v1.2.0-beta.1 -m "Beta release v1.2.0-beta.1"
git push origin v1.2.0-beta.1
```

### Re-building a release

If you need to redo a release (e.g. after a broken tag), delete the release on GitHub
first, then force-push the tag:

```bash
git tag -f v1.2.0 -m "Re-release v1.2.0"
git push origin v1.2.0 --force
```

See [docs/packaging.md](docs/packaging.md#automated-releases-cicd) for full CI/CD details.
