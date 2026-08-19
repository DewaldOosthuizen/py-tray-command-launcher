# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for :class:`core.process_output_relay.ProcessOutputRelay`.

Exercises the stdout/stderr/finished/errorOccurred wiring extracted from
``TrayApp.show_command_output`` in isolation, without constructing a full
TrayApp or RichOutputWindow.
"""

from unittest.mock import MagicMock

from core.process_output_relay import ProcessOutputRelay


def _make_relay():
    process = MagicMock()
    output_win = MagicMock()
    tab = MagicMock()
    relay = ProcessOutputRelay(process, output_win, tab, "echo hi")
    return relay, process, output_win, tab


def test_wire_connects_all_signals():
    """wire() connects stdout, stderr, finished and errorOccurred."""
    relay, process, _output_win, _tab = _make_relay()
    on_finished = MagicMock()

    relay.wire(on_finished)

    process.readyReadStandardOutput.connect.assert_called_once_with(relay._on_stdout)
    process.readyReadStandardError.connect.assert_called_once_with(relay._on_stderr)
    process.finished.connect.assert_called_once_with(on_finished)
    process.errorOccurred.connect.assert_called_once()


def test_on_stdout_appends_decoded_output():
    """_on_stdout decodes stdout bytes and appends them to the tab."""
    relay, process, output_win, tab = _make_relay()
    process.readAllStandardOutput.return_value.data.return_value = b"hello"

    relay._on_stdout()

    output_win.append_output.assert_called_once_with(tab, "hello")


def test_on_stdout_skips_empty_output():
    """_on_stdout is a no-op when there is no new stdout data."""
    relay, process, output_win, _tab = _make_relay()
    process.readAllStandardOutput.return_value.data.return_value = b""

    relay._on_stdout()

    output_win.append_output.assert_not_called()


def test_on_stderr_appends_decoded_output():
    """_on_stderr decodes stderr bytes and appends them to the tab."""
    relay, process, output_win, tab = _make_relay()
    process.readAllStandardError.return_value.data.return_value = b"oops"

    relay._on_stderr()

    output_win.append_output.assert_called_once_with(tab, "oops")


def test_append_swallows_destroyed_window_after_error():
    """After an error, a RuntimeError from a destroyed window is swallowed."""
    relay, _process, output_win, _tab = _make_relay()
    output_win.append_output.side_effect = RuntimeError("wrapped C/C++ object deleted")
    on_finished = MagicMock()

    relay._on_error("Crashed", on_finished)

    on_finished.assert_called_once()


def test_append_is_noop_when_window_garbage_collected():
    """If the output window has been garbage collected, appends are skipped."""
    relay, _process, _output_win, _tab = _make_relay()
    relay._output_win_ref = lambda: None

    # Must not raise for any of the append paths.
    relay._on_stdout()
    relay._append("text", "stdout")
