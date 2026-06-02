# SPDX-License-Identifier: GPL-3.0-or-later
"""Characterisation tests for :class:`core.tray_app.TrayApp`.

Covers the critical paths of the tray-application orchestrator that were
previously untested in a dedicated file:

* ``execute()`` — history recording, confirmation gate, prompt substitution
  routing (POSIX ``shlex.quote`` vs Windows ``list2cmdline``) and the
  show-output vs direct-execute branch.
* ``_update_tray_badge()`` — running-action label/visibility for the running
  process count.
* ``show_command_output()`` lifecycle — process registration plus the nested
  ``_on_finished`` callback that removes the process and refreshes the badge.
* ``_reregister_hotkey`` / ``_reregister_bar_hotkey`` — exception swallowing.

The shlex-quote and shell-injection grains of ``execute()`` are intentionally
NOT re-tested here; they are already covered by
``tests/test_command_executor.py::TestPromptInputSanitisation`` (reuse).

TrayApp is instantiated via ``object.__new__`` to bypass the Qt-heavy
``__init__`` wiring; only the attributes each method touches are set by hand.
PyQt6 is stubbed in ``conftest.py`` (sys.modules injection) — not repeated here.
"""

from unittest.mock import MagicMock, patch

from core.tray_app import TrayApp


def _make_app():
    """Build a bare TrayApp with the attributes ``execute()`` touches."""
    app = object.__new__(TrayApp)
    app.executor = MagicMock()
    app.reload_history_commands = MagicMock()
    app.reload_favorites_commands = MagicMock()
    return app


# --------------------------------------------------------------------------- #
# execute()                                                                     #
# --------------------------------------------------------------------------- #


def test_execute_adds_entry_to_history():
    """execute() records a history entry unconditionally before any gate."""
    app = _make_app()
    with patch("core.tray_app.config_manager") as cm:
        app.execute(
            title="Term",
            command="echo hi",
            confirm=False,
            show_output=False,
            prompt="",
        )
    cm.add_to_history.assert_called_once()
    entry = cm.add_to_history.call_args[0][0]
    assert entry["command"] == "echo hi"
    assert entry["title"] == "Term"
    assert entry["confirm"] is False
    assert entry["showOutput"] is False
    assert entry["prompt"] == ""
    assert "timestamp" in entry


def test_execute_without_confirm_runs_command():
    """With confirm=False, no prompt and show_output=False the command runs directly."""
    app = _make_app()
    with patch("core.tray_app.config_manager"):
        app.execute(
            title="Term",
            command="echo hi",
            confirm=False,
            show_output=False,
            prompt="",
        )
    app.executor.execute_command.assert_called_once_with("echo hi")


def test_execute_confirm_declined_aborts():
    """A declined confirmation aborts before the command is executed."""
    app = _make_app()
    with (
        patch("core.tray_app.config_manager"),
        patch("core.tray_app.confirm_execute", return_value=False),
    ):
        app.execute(
            title="Term",
            command="rm -rf /tmp/x",
            confirm=True,
            show_output=False,
            prompt="",
        )
    app.executor.execute_command.assert_not_called()


def test_execute_confirm_accepted_runs_command():
    """An accepted confirmation lets the command execute."""
    app = _make_app()
    with (
        patch("core.tray_app.config_manager"),
        patch("core.tray_app.confirm_execute", return_value=True),
    ):
        app.execute(
            title="Term",
            command="echo hi",
            confirm=True,
            show_output=False,
            prompt="",
        )
    app.executor.execute_command.assert_called_once_with("echo hi")


def test_execute_prompt_cancelled_aborts():
    """Cancelling the input dialog (ok=False) aborts execution."""
    app = _make_app()
    with (
        patch("core.tray_app.config_manager"),
        patch("core.tray_app.QInputDialog") as dialog,
    ):
        dialog.getText.return_value = ("whatever", False)
        app.execute(
            title="Term",
            command="echo {promptInput}",
            confirm=False,
            show_output=False,
            prompt="Enter value",
        )
    app.executor.execute_command.assert_not_called()


def test_execute_prompt_empty_input_aborts():
    """Empty input (ok=True but blank string) aborts execution."""
    app = _make_app()
    with (
        patch("core.tray_app.config_manager"),
        patch("core.tray_app.QInputDialog") as dialog,
    ):
        dialog.getText.return_value = ("", True)
        app.execute(
            title="Term",
            command="echo {promptInput}",
            confirm=False,
            show_output=False,
            prompt="Enter value",
        )
    app.executor.execute_command.assert_not_called()


def test_execute_show_output_routes_to_show_command_output():
    """show_output=True routes to show_command_output, not the direct executor."""
    app = _make_app()
    app.show_command_output = MagicMock()
    with patch("core.tray_app.config_manager"):
        app.execute(
            title="Status",
            command="git status",
            confirm=False,
            show_output=True,
            prompt="",
        )
    app.show_command_output.assert_called_once_with("Status", "git status")
    app.executor.execute_command.assert_not_called()


def test_execute_prompt_windows_uses_list2cmdline():
    """On Windows (os.name == 'nt') prompt input is quoted via list2cmdline."""
    app = _make_app()
    with (
        patch("core.tray_app.config_manager"),
        patch("core.tray_app.QInputDialog") as dialog,
        patch("core.tray_app.os") as mock_os,
        patch("core.tray_app.subprocess") as mock_sub,
    ):
        mock_os.name = "nt"
        dialog.getText.return_value = ("a b", True)
        mock_sub.list2cmdline.return_value = '"a b"'
        app.execute(
            title="Term",
            command="echo {promptInput}",
            confirm=False,
            show_output=False,
            prompt="Enter value",
        )
    mock_sub.list2cmdline.assert_called_once_with(["a b"])
    app.executor.execute_command.assert_called_once_with('echo "a b"')


def test_execute_prompt_posix_uses_shlex_quote():
    """On POSIX (os.name != 'nt') prompt input is quoted via shlex.quote."""
    app = _make_app()
    with (
        patch("core.tray_app.config_manager"),
        patch("core.tray_app.QInputDialog") as dialog,
        patch("core.tray_app.os") as mock_os,
        patch("core.tray_app.shlex") as mock_shlex,
    ):
        mock_os.name = "posix"
        dialog.getText.return_value = ("a b; rm -rf x", True)
        mock_shlex.quote.return_value = "'a b; rm -rf x'"
        app.execute(
            title="Term",
            command="echo {promptInput}",
            confirm=False,
            show_output=False,
            prompt="Enter value",
        )
    mock_shlex.quote.assert_called_once_with("a b; rm -rf x")
    app.executor.execute_command.assert_called_once_with("echo 'a b; rm -rf x'")


# --------------------------------------------------------------------------- #
# _update_tray_badge()                                                          #
# --------------------------------------------------------------------------- #


def test_update_badge_hides_running_action_when_zero():
    """With no running processes the running-action entry is hidden."""
    app = object.__new__(TrayApp)
    app._running_processes = {}
    app._running_action = MagicMock()
    app.icon_file = "icon.png"
    app.tray_icon = MagicMock()
    with patch("core.tray_app.QPixmap") as qpix:
        qpix.return_value.isNull.return_value = True
        app._update_tray_badge()
    app._running_action.setVisible.assert_any_call(False)
    app._running_action.setText.assert_not_called()


def test_update_badge_shows_count_when_running():
    """With running processes the running-action shows 'Running: N' and is visible."""
    app = object.__new__(TrayApp)
    app._running_processes = {"a": MagicMock(), "b": MagicMock()}
    app._running_action = MagicMock()
    app.icon_file = "icon.png"
    app.tray_icon = MagicMock()
    with patch("core.tray_app.QPixmap") as qpix:
        qpix.return_value.isNull.return_value = True
        app._update_tray_badge()
    app._running_action.setText.assert_any_call("Running: 2")
    app._running_action.setVisible.assert_any_call(True)


# --------------------------------------------------------------------------- #
# show_command_output() lifecycle / _on_finished                                #
# --------------------------------------------------------------------------- #


def test_on_finished_removes_process_and_updates_badge():
    """When a process finishes it is removed from _running_processes and the badge refreshes."""
    app = object.__new__(TrayApp)
    app.app = MagicMock()
    app.executor = MagicMock()
    app.output_windows = []
    app._running_processes = {}
    app._update_tray_badge = MagicMock()

    process = app.executor.execute_command_process.return_value

    with patch("core.tray_app.RichOutputWindow"):
        app.show_command_output("Status", "git status")

    # Registration side effects.
    assert len(app._running_processes) == 1
    assert app._update_tray_badge.called

    # Capture and invoke the finished callback wired by show_command_output.
    on_finished = process.finished.connect.call_args[0][0]
    badge_calls_before = app._update_tray_badge.call_count
    on_finished()

    assert len(app._running_processes) == 0
    assert app._update_tray_badge.call_count > badge_calls_before


# --------------------------------------------------------------------------- #
# Hotkey re-registration — exception swallowing                                 #
# --------------------------------------------------------------------------- #


def test_reregister_hotkey_swallows_exception():
    """_reregister_hotkey logs and swallows a failure instead of propagating it."""
    app = object.__new__(TrayApp)
    app.palette = MagicMock()
    app.palette.register_hotkey.side_effect = RuntimeError("boom")
    # Must not raise.
    app._reregister_hotkey("ctrl+x")
    app.palette.register_hotkey.assert_called_once_with("ctrl+x")


def test_reregister_bar_hotkey_swallows_exception():
    """_reregister_bar_hotkey logs and swallows a failure instead of propagating it."""
    app = object.__new__(TrayApp)
    app.quick_launch_bar = MagicMock()
    app.quick_launch_bar.unregister_hotkey.side_effect = RuntimeError("boom")
    # Must not raise.
    app._reregister_bar_hotkey("ctrl+y")
