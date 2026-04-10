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
pip install flake8 black pylint
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

All contributions must pass both checks before committing.

### Syntax / import errors

```bash
find src -name "*.py" -exec python3 -m py_compile {} \;
```

No output means no errors.

### Style (flake8)

```bash
flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
```

This checks for syntax errors and undefined names. The exit code must be `0` (no issues found).

### Formatting

Code is formatted with `black` (line length 88):

```bash
black src/
```

Run this before committing to avoid formatting-only review comments.

---

## Project Conventions

- **Logging**: Use `logging.getLogger(__name__)` in every module. Do not use `print()` for diagnostic output.
- **Configuration access**: All file I/O for config and state must go through `config_manager` (the singleton from `core/config_manager.py`). Do not read or write JSON files directly.
- **Qt threading**: Long-running operations (encryption, external processes with large output) must run in a `QThread` to keep the UI responsive.
- **License header**: Every new `.py` file must include `# SPDX-License-Identifier: GPL-3.0-or-later` as the first line.

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

There are currently no automated unit tests. The primary validation method is:

1. Syntax check with `python3 -m py_compile` (see above).
2. Headless startup test with `QT_QPA_PLATFORM=offscreen`.
3. Manual GUI validation — requires a display server or VNC.

New tests should be placed in `tests/` and can be run with:

```bash
python3 -m pytest tests/
```

---

## Submitting Changes

1. Fork the repository and create a feature branch.
2. Make your changes, following the conventions above.
3. Run the syntax and style checks.
4. Update the relevant `docs/` file if applicable.
5. Open a pull request with a clear description of what changed and why.
