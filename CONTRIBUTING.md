# Contributing to py-tray-command-launcher

## Dependency Convention

`pyproject.toml` is the single source of truth for all runtime dependencies.
The `requirements.txt` file is only a dev-install convenience shim:

    -e ".[dev]"

It must never declare standalone version pins. If you need to add, remove, or
tighten a dependency (e.g. `PyQt6>=6.11.0`), edit `[project].dependencies` in
`pyproject.toml` only.

## Development Setup

Install the project and its linting tools:

    pip install ruff
    pip install -e ".[dev]"

## Linting

Run the linter before opening a PR:

    ruff check src/

Check formatting (does not modify files):

    ruff format --check src/

Apply formatting:

    ruff format src/

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
