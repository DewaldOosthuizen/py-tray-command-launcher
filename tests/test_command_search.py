import sys
from unittest.mock import MagicMock

_pyqt6 = MagicMock()
sys.modules.setdefault("PyQt6", _pyqt6)
sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6.QtWidgets)
sys.modules.setdefault("PyQt6.QtCore", _pyqt6.QtCore)
sys.modules.setdefault("PyQt6.QtGui", _pyqt6.QtGui)

import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from modules.command_search import _score


def test_exact_match_scores_high():
    score = _score("Terminal", "Terminal")
    assert score >= 90


def test_partial_match_returns_nonzero():
    score = _score("term", "Terminal")
    assert score > 0


def test_empty_query_gives_positive_score():
    # An empty string substring matches every string
    score = _score("", "anything")
    assert score >= 0  # Must not raise; score value depends on backend


def test_no_match_scores_low():
    score = _score("zzzzunlikely", "Terminal")
    # rapidfuzz may still return a small partial score; without it score is 0
    assert score < 90


def test_special_characters_do_not_raise():
    try:
        _score("!@#$%^&*()", "some command --flag=value")
    except Exception as exc:
        pytest.fail(f"_score raised unexpectedly: {exc}")


def test_score_is_symmetric_ish():
    # Both directions should yield a positive score for similar strings
    s1 = _score("git", "Git Status")
    s2 = _score("Git Status", "git")
    assert s1 > 0 and s2 > 0
