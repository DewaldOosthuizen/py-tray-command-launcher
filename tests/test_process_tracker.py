# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for core.process_tracker.ProcessTracker."""

from unittest.mock import MagicMock

from core.process_tracker import ProcessTracker


def test_add_stores_process_and_increments_count():
    tracker = ProcessTracker()
    proc = MagicMock()
    tracker.add("id-1", proc)
    assert tracker.count() == 1
    assert tracker.processes["id-1"] is proc


def test_add_emits_process_count_changed():
    tracker = ProcessTracker()
    received = []
    tracker.process_count_changed.connect(received.append)
    tracker.add("id-1", MagicMock())
    assert received == [1]


def test_remove_deletes_process_and_decrements_count():
    tracker = ProcessTracker()
    tracker.add("id-1", MagicMock())
    tracker.remove("id-1")
    assert tracker.count() == 0
    assert "id-1" not in tracker.processes


def test_remove_emits_process_count_changed():
    tracker = ProcessTracker()
    tracker.add("id-1", MagicMock())
    received = []
    tracker.process_count_changed.connect(received.append)
    tracker.remove("id-1")
    assert received == [0]


def test_remove_nonexistent_key_does_not_crash():
    tracker = ProcessTracker()
    # Must not raise.
    tracker.remove("does-not-exist")
    assert tracker.count() == 0


def test_remove_nonexistent_key_still_emits_signal():
    tracker = ProcessTracker()
    received = []
    tracker.process_count_changed.connect(received.append)
    tracker.remove("does-not-exist")
    assert received == [0]


def test_count_reflects_multiple_adds():
    tracker = ProcessTracker()
    tracker.add("a", MagicMock())
    tracker.add("b", MagicMock())
    assert tracker.count() == 2
