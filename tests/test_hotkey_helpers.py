# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for utils.hotkey_helpers — shared hotkey-to-pynput conversion."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.hotkey_helpers import _PYNPUT_WRAP, to_pynput_str


class TestToPynputStr:
    """Tests for the public to_pynput_str() helper."""

    def test_modifier_keys_get_brackets(self):
        result = to_pynput_str("ctrl+shift+space")
        assert "<ctrl>" in result
        assert "<shift>" in result
        assert "<space>" in result

    def test_single_alpha_no_brackets(self):
        assert to_pynput_str("a") == "a"

    def test_multi_char_combo(self):
        result = to_pynput_str("ctrl+alt+a")
        assert "<ctrl>" in result
        assert "<alt>" in result

    def test_ctrl_shift_b(self):
        result = to_pynput_str("ctrl+shift+b")
        assert result == "<ctrl>+<shift>+b"

    def test_empty_string(self):
        assert to_pynput_str("") == ""

    def test_trailing_whitespace_stripped(self):
        assert to_pynput_str("ctrl + shift") == "<ctrl>+<shift>"

    def test_case_insensitive(self):
        result = to_pynput_str("CTRL+SHIFT+SPACE")
        assert "<ctrl>" in result
        assert "<shift>" in result
        assert "<space>" in result


class TestPYNPUTWRAP:
    """Tests for the _PYNPUT_WRAP set contents."""

    def test_contains_modifier_keys(self):
        for key in ("ctrl", "shift", "alt", "altgr", "cmd", "win", "super", "meta"):
            assert key in _PYNPUT_WRAP

    def test_contains_special_keys(self):
        for key in ("space", "enter", "return", "tab", "esc", "escape",
                     "backspace", "delete", "insert"):
            assert key in _PYNPUT_WRAP

    def test_contains_navigation_keys(self):
        for key in ("home", "end", "page_up", "page_down",
                     "up", "down", "left", "right"):
            assert key in _PYNPUT_WRAP

    def test_contains_function_keys(self):
        for i in range(1, 13):
            assert f"f{i}" in _PYNPUT_WRAP

    def test_is_a_set(self):
        assert isinstance(_PYNPUT_WRAP, set)
