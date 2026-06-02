#!/usr/bin/env bash
# lint.sh — local lint runner that mirrors the CI lint job exactly.
#
# Usage:
#   ./scripts/lint.sh           # check only (same as CI)
#   ./scripts/lint.sh --fix     # auto-fix then check (for local cleanup)
#
# Requirements: ruff must be installed.
#   pip install "ruff>=0.5.0"
#   or: pip install -e ".[dev]"  (if ruff is in optional-dependencies)

set -euo pipefail

FIX=0
for arg in "$@"; do
    [[ "$arg" == "--fix" ]] && FIX=1
done

echo "==> py-tray-command-launcher lint"

if [[ $FIX -eq 1 ]]; then
    echo "--- ruff format (fix) ---"
    ruff format src/ tests/
    echo "--- ruff check (fix) ---"
    ruff check src/ tests/ --fix
    echo "--- re-check after fixes ---"
fi

echo "--- ruff check src/ tests/ ---"
ruff check src/ tests/

echo "--- ruff format --check src/ tests/ ---"
ruff format --check src/ tests/

echo "==> All lint checks passed."
