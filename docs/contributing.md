# Contributing

Guidelines for setting up a development environment, coding standards, and submitting changes.

---

## Development Setup

### 1. Install system dependencies

```bash
sudo bash scripts/install_packages.sh
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate       # Linux / macOS
# venv\Scripts\activate        # Windows
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-build.txt
```

### 4. Install development tools

```bash
pip install "ruff>=0.5.0"
```

### 5. Validate the installation

```bash
python3 -c "import sys; sys.path.append('src'); from core.tray_app import TrayApp; print('OK')"
```

---

## Running the Application

**With a display server (normal use):**

```bash
source venv/bin/activate
python3 src/main.py
```

**Headless validation (no display required):**

```bash
QT_QPA_PLATFORM=offscreen timeout 5 python3 src/main.py
```

The headless run should start cleanly, print configuration loading messages, then exit (the timeout kills it — that is expected, not a failure).

---

## Code Quality

All contributions must pass both checks before committing. Use the local lint
script to replicate the CI lint job exactly:

```bash
bash scripts/lint.sh
```

To auto-fix violations before reviewing:

```bash
bash scripts/lint.sh --fix
```

### Syntax / import errors

```bash
find src -name "*.py" -exec python3 -m py_compile {} \;
```

No output means no errors.

### Linting and formatting (ruff)

```bash
bash scripts/lint.sh
```

The script runs `ruff check src/ tests/` and `ruff format --check src/ tests/`
in sequence — identical to what the CI lint job in `.github/workflows/lint.yml`
executes. Pass `--fix` to apply safe auto-fixes first.

---

## Project Conventions

- **Logging**: Use `logging.getLogger(__name__)` in every module. Do not use `print()` for diagnostic output.
- **Configuration access**: All file I/O for config and state must go through `config_manager` (the singleton from `core/config_manager.py`). Do not read or write JSON files directly.
- **Qt threading**: Long-running operations (encryption, external processes with large output) must run in a `QThread` to keep the UI responsive.
- **License header**: Every new Python module under `src/` must include `# SPDX-License-Identifier: GPL-3.0-or-later` as the first line. Files under `tests/` should follow the existing test-file conventions used in the repository.

---

## Documentation Policy

Any pull request that adds or changes a user-facing feature **must** update the relevant file in `docs/`:

| Change type | Update |
|---|---|
| New feature | `docs/features.md` |
| New config field | `docs/configuration.md` |
| New module or architectural change | `docs/architecture.md` |
| Build / packaging change | `docs/packaging.md` |

---

## Testing

The repository includes unit tests under `tests/`:

Run the unit tests with:

 ```bash
 python3 -m unittest discover -s tests -p "test_*.py"
 ```

 In addition to the unit tests, contributors should still run the following validation steps:

 1. Syntax check with `python3 -m py_compile` (see above).
 2. Headless startup test with `QT_QPA_PLATFORM=offscreen`.
 3. Manual GUI validation — requires a display server or VNC.
 New tests should be placed in `tests/` and follow the `test_*.py` naming pattern so they are picked up by `unittest` discovery.

---

## Submitting Changes

1. Fork the repository and create a feature branch.
2. Make your changes, following the conventions above.
3. Run the syntax and style checks.
4. Update the relevant `docs/` file if applicable.
5. Open a pull request with a clear description of what changed and why.
