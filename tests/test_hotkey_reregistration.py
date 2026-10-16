# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for global hotkey re-registration paths (issue #134)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.hotkey_helpers import safe_register, safe_unregister


class TestSafeUnregister:
    def test_none_handle_returns_none(self):
        assert safe_unregister(None) is None

    def test_stop_called_before_return(self):
        handle = MagicMock()
        result = safe_unregister(handle, timeout=0.1)
        handle.stop.assert_called_once()
        assert result is None

    def test_join_called_with_timeout(self):
        handle = MagicMock()
        safe_unregister(handle, timeout=0.5)
        handle.join.assert_called_once_with(timeout=0.5)


class TestSafeRegister:
    def test_stops_existing_then_factory(self):
        existing = MagicMock()
        new_handle = MagicMock()
        calls = []

        def factory():
            calls.append("factory")
            return new_handle

        # wrap stop to record ordering
        def stop_recording():
            calls.append("stop")

        existing.stop.side_effect = stop_recording
        result = safe_register(existing, factory, timeout=0.1)
        assert result is new_handle
        assert calls == ["stop", "factory"]

    def test_no_existing_handle(self):
        new_handle = MagicMock()
        result = safe_register(None, lambda: new_handle)
        assert result is new_handle


class TestPaletteReregistration:
    def test_unregister_nulls_handle(self):
        from ui.command_palette import CommandPalette

        cp = CommandPalette.__new__(CommandPalette)
        cp._hotkey_listener = MagicMock()
        cp._hotkey_listener.stop.return_value = None
        cp._services = MagicMock()
        # bypass init heavy
        cp._cmd_hotkey = ""
        cp._app_hotkey = ""

        listener = cp._hotkey_listener
        cp.unregister_hotkey()
        listener.stop.assert_called_once()
        assert cp._hotkey_listener is None
