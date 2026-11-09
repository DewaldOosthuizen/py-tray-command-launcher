# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for core.process_tracker.ProcessTracker."""

from unittest.mock import MagicMock

from core.process_output_relay import ProcessOutputRelay
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


def test_replacing_process_id_keeps_count_aligned_with_process_map():
    tracker = ProcessTracker()
    original = MagicMock()
    replacement = MagicMock()
    received = []
    tracker.process_count_changed.connect(received.append)

    tracker.add("shared", original)
    tracker.add("shared", replacement)

    assert tracker.processes == {"shared": replacement}
    assert tracker.count() == len(tracker.processes) == 1
    assert received == [1, 1]


def test_unknown_and_repeated_removals_keep_count_aligned():
    tracker = ProcessTracker()
    tracker.add("known", MagicMock())

    tracker.remove("unknown")
    tracker.remove("known")
    tracker.remove("known")

    assert tracker.count() == len(tracker.processes) == 0


def test_stale_process_completion_cannot_remove_replacement():
    tracker = ProcessTracker()
    old_process = MagicMock()
    replacement = MagicMock()
    old_output_window = MagicMock()
    new_output_window = MagicMock()
    tracker.add("shared", old_process)
    old_relay = ProcessOutputRelay(old_process, old_output_window, MagicMock(), "old")
    old_relay.wire(lambda *_args: tracker.remove("shared", expected_process=old_process))

    tracker.add("shared", replacement)
    old_process.finished.connect.call_args.args[0](0, 0)
    assert tracker.processes["shared"] is replacement
    assert tracker.count() == len(tracker.processes) == 1

    new_relay = ProcessOutputRelay(replacement, new_output_window, MagicMock(), "new")
    new_relay.wire(lambda *_args: tracker.remove("shared", expected_process=replacement))
    replacement.finished.connect.call_args.args[0](0, 0)
    assert tracker.count() == len(tracker.processes) == 0
