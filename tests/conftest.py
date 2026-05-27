# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared pytest fixtures for py-tray-command-launcher tests.

All fixtures avoid importing PyQt6 at module level so the test suite can run
headlessly without a display (QApplication is only created when a test
explicitly requests the ``qt_app`` fixture).
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make src/ importable without installing the package
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_config_dir(tmp_path: Path) -> Path:
    """Return a temporary directory suitable for use as a config dir."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    return cfg


@pytest.fixture()
def tmp_commands_file(tmp_config_dir: Path) -> Path:
    """Write a minimal valid commands.json and return its path."""
    data = {
        "System": {
            "Terminal": {"command": "gnome-terminal"},
            "Editor": {"command": "gedit", "showOutput": False},
        },
        "Git": {
            "Status": {"command": "git status", "showOutput": True},
        },
    }
    path = tmp_config_dir / "commands.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Mock AppServices
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_services() -> MagicMock:
    """Return a MagicMock that quacks like AppServices."""
    svc = MagicMock()
    svc.get_all_commands.return_value = [
        {"group": "System", "label": "Terminal", "command": "gnome-terminal"},
        {"group": "System", "label": "Editor", "command": "gedit"},
        {"group": "Git", "label": "Status", "command": "git status"},
    ]
    svc.resolve_icon_path.return_value = None
    svc.resolve_command_reference.side_effect = lambda group, label, item: item
    return svc
