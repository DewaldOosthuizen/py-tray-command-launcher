# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the _build_command_path helper in favorites.py.

These tests cover the high-priority Issue 2 fix — ensuring group paths
containing the \" → \" display separator are correctly expanded into
dot-separated keys rather than treated as a single group name.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Stub out PyQt6 so this file can be imported without a display or Qt install.
# _build_command_path is a pure Python function; it has no Qt dependency.
import types
for _mod in [
    "PyQt6", "PyQt6.QtWidgets", "PyQt6.QtGui", "PyQt6.QtCore",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)
# Provide the specific symbols favorites.py imports at module level.
# Save existing values so we can restore them after the import, preventing
# pollution of the conftest stubs for later test modules.
_qw = sys.modules["PyQt6.QtWidgets"]
_qw_syms = ["QMenu", "QMessageBox", "QInputDialog"]
_saved_qw = {s: getattr(_qw, s, None) for s in _qw_syms}
for _sym in _qw_syms:
    setattr(_qw, _sym, MagicMock)
_qg = sys.modules["PyQt6.QtGui"]
_qg_syms = ["QIcon", "QCursor", "QAction"]
_saved_qg = {s: getattr(_qg, s, None) for s in _qg_syms}
for _sym in _qg_syms:
    setattr(_qg, _sym, MagicMock)
_qc = sys.modules["PyQt6.QtCore"]
_saved_qt = getattr(_qc, "Qt", None)
setattr(_qc, "Qt", MagicMock)

from modules.favorites import _build_command_path

# Restore originals so subsequent UI test modules get the conftest _QWidget stubs.
for _sym, _val in _saved_qw.items():
    if _val is not None:
        setattr(_qw, _sym, _val)
    else:
        try:
            delattr(_qw, _sym)
        except AttributeError:
            pass
for _sym, _val in _saved_qg.items():
    if _val is not None:
        setattr(_qg, _sym, _val)
    else:
        try:
            delattr(_qg, _sym)
        except AttributeError:
            pass
if _saved_qt is not None:
    setattr(_qc, "Qt", _saved_qt)
else:
    try:
        delattr(_qc, "Qt")
    except AttributeError:
        pass


class TestBuildCommandPath:
    # ------------------------------------------------------------------
    # Basic cases
    # ------------------------------------------------------------------

    def test_flat_group(self):
        """Simple group + label -> 'Group.Label'."""
        assert _build_command_path("System", "Terminal") == "System.Terminal"

    def test_nested_group_single_separator(self):
        """'Tools → Git' + 'Commit' -> 'Tools.Git.Commit'."""
        assert _build_command_path("Tools → Git", "Commit") == "Tools.Git.Commit"

    def test_nested_group_multiple_separators(self):
        """Three-level nesting is flattened correctly."""
        assert _build_command_path("A → B → C", "Cmd") == "A.B.C.Cmd"

    # ------------------------------------------------------------------
    # Edge cases that previously caused corruption
    # ------------------------------------------------------------------

    def test_group_with_leading_trailing_spaces(self):
        """Extra whitespace around parts is stripped."""
        assert _build_command_path("  Tools  →  Git  ", "Push") == "Tools.Git.Push"

    def test_label_with_arrow_in_value(self):
        """A label that contains ' → ' should not be split (only group is split)."""
        result = _build_command_path("System", "Send → Mail")
        # label is appended as-is; only group is split
        assert result == "System.Send → Mail"

    def test_empty_group_parts_skipped(self):
        """Degenerate ' → Label' (leading separator) should not create empty segments."""
        result = _build_command_path(" → Git", "Status")
        # leading empty string after strip is filtered
        assert result == "Git.Status"

    def test_single_word_group(self):
        """No separator in group -> group.label."""
        assert _build_command_path("Git", "Log") == "Git.Log"

    def test_empty_group_string(self):
        """Empty group -> just the label."""
        assert _build_command_path("", "Orphan") == "Orphan"

    # ------------------------------------------------------------------
    # Regression: old implementation compared to new
    # ------------------------------------------------------------------

    def test_regression_old_impl_would_differ_for_nested(self):
        """The old code: group + '.' + label (with raw ' → ' join) produced wrong path.

        Old: 'Tools → Git.Commit'
        New: 'Tools.Git.Commit'
        """
        old_result = "Tools → Git" + "." + "Commit"  # simulates old logic
        new_result = _build_command_path("Tools → Git", "Commit")
        assert old_result != new_result
        assert new_result == "Tools.Git.Commit"
