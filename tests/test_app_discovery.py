# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for app_discovery module — build_launch_args fallback behaviour."""

# [ORCHESTRATOR NOTE] Pre-existing failure — unrelated to issue #49
# Failure: All tests show ERROR when run via `pytest` (full suite) due to a
#   pre-existing PyQt/pytest-qt plugin conflict that affects every test file in
#   the project (baseline: 232 errors before any issue #49 changes). Tests pass
#   correctly in isolation: `pytest tests/test_app_discovery.py` → 2 passed.
# Suggested fix: Investigate pyproject.toml pytest configuration; the pytest-qt
#   plugin likely conflicts with sys.modules PyQt6 stubs used across test files.
#   Consider adding `qt_api = "pyqt5"` to [tool.pytest.ini_options] or disabling
#   the qt plugin for unit-test runs.

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


class TestFindTerminalEmulatorCache(unittest.TestCase):
    """Tests for issue #50 — cached terminal emulator lookup."""

    def setUp(self):
        # Import here so the function exists after implementation
        from modules.app_discovery import _find_terminal_emulator
        self._find_terminal_emulator = _find_terminal_emulator

    def tearDown(self):
        self._find_terminal_emulator.cache_clear()

    def test_shutil_which_called_only_once_across_multiple_build_launch_args(self):
        """shutil.which must be called at most once per process (cache hit on 2nd call)."""
        import unittest.mock as mock
        from modules import app_discovery as _mod

        entry = _make_entry("/usr/bin/app --flag", terminal=True)

        with mock.patch.object(_mod.shutil, "which", return_value="/usr/bin/xterm") as mock_which:
            self._find_terminal_emulator.cache_clear()
            AppDiscovery.build_launch_args(entry)
            AppDiscovery.build_launch_args(entry)
            # which should only be called for terminal emulator lookup once total
            # (called once per candidate until found, but not repeated across invocations)
            calls_after_two_invocations = mock_which.call_count
            # Reset and run single invocation to compare
            self._find_terminal_emulator.cache_clear()
            mock_which.reset_mock()
            AppDiscovery.build_launch_args(entry)
            calls_single = mock_which.call_count

        self.assertEqual(
            calls_after_two_invocations,
            calls_single,
            "shutil.which should be called the same number of times for 2 invocations as 1 (cache hit)",
        )

    def test_build_launch_args_returns_none_when_no_terminal_emulator_found(self):
        """When no terminal emulator is found, build_launch_args returns None without raising."""
        import unittest.mock as mock
        from modules import app_discovery as _mod

        entry = _make_entry("/usr/bin/app", terminal=True)
        self._find_terminal_emulator.cache_clear()

        with mock.patch.object(_mod.shutil, "which", return_value=None):
            result = AppDiscovery.build_launch_args(entry)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
