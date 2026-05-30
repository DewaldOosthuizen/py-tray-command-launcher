# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for app_discovery module — build_launch_args fallback behaviour."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

# Stub PyQt6 before importing any src modules
_pyqt6_stub = MagicMock()
sys.modules.setdefault("PyQt6", _pyqt6_stub)
sys.modules.setdefault("PyQt6.QtCore", _pyqt6_stub.QtCore)
sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6_stub.QtWidgets)
sys.modules.setdefault("PyQt6.QtGui", _pyqt6_stub.QtGui)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.app_discovery import AppDiscovery, AppEntry  # noqa: E402


def _make_entry(exec_cmd: str, name: str = "TestApp", terminal: bool = False) -> AppEntry:
    entry = AppEntry.__new__(AppEntry)
    entry.name = name
    entry.exec_cmd = exec_cmd
    entry.icon_name = ""
    entry.categories = []
    entry.terminal = terminal
    return entry


class TestBuildLaunchArgsFallback(unittest.TestCase):
    """Tests for two-level fallback in build_launch_args (issue #49)."""

    def test_build_launch_args_unmatched_quote_falls_back_to_whitespace_split(self):
        """Exec= with unmatched quote must fall back to whitespace split, not single token."""
        entry = _make_entry("/usr/bin/app --flag 'bad")
        result = AppDiscovery.build_launch_args(entry)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 1, "Expected multiple tokens, got single-token fallback")
        self.assertEqual(result[0], "/usr/bin/app")

    def test_build_launch_args_empty_after_failed_shlex_returns_none(self):
        """Exec= that becomes empty/whitespace after field-code stripping returns None."""
        # Use an exec_cmd whose field codes strip to whitespace; shlex will also
        # fail on unmatched quote so we combine both — but the simplest case is
        # a purely whitespace exec_cmd after cleaning.
        entry = _make_entry("   ")
        result = AppDiscovery.build_launch_args(entry)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
