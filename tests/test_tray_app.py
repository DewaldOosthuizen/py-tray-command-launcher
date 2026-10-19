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

from core.process_tracker import ProcessTracker
from core.tray_app import TrayApp


def _make_app():
    """Build a bare TrayApp with the attributes ``execute()`` touches."""
    app = object.__new__(TrayApp)
    app.executor = MagicMock()
    app.module_controller = MagicMock()
    app.module_controller.get_executor.return_value = app.executor
    app.module_controller.loaded_palette = None
    app.module_controller.loaded_quick_launch_bar = None
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
        patch("core.tray_app.prompt_text") as dialog,
    ):
        dialog.return_value = ("whatever", False)
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
        patch("core.tray_app.prompt_text") as dialog,
    ):
        dialog.return_value = ("", True)
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
        patch("core.tray_app.prompt_text") as dialog,
        patch("core.tray_app.os") as mock_os,
        patch("core.tray_app.subprocess") as mock_sub,
    ):
        mock_os.name = "nt"
        dialog.return_value = ("a b", True)
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
        patch("core.tray_app.prompt_text") as dialog,
        patch("core.tray_app.os") as mock_os,
        patch("core.tray_app.shlex") as mock_shlex,
    ):
        mock_os.name = "posix"
        dialog.return_value = ("a b; rm -rf x", True)
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
# Extracted helper methods (_record_history, _get_prompt_input,             #
# _substitute_prompt, _route_execution)                                    #
# --------------------------------------------------------------------------- #


def test_record_history_adds_entry():
    """_record_history delegates to config_manager.add_to_history with correct fields."""
    app = _make_app()
    with patch("core.tray_app.config_manager") as cm:
        app._record_history("echo hi", "Term", False, False, "")
    cm.add_to_history.assert_called_once()
    entry = cm.add_to_history.call_args[0][0]
    assert entry["command"] == "echo hi"
    assert entry["title"] == "Term"
    assert entry["confirm"] is False
    assert entry["showOutput"] is False
    assert entry["prompt"] == ""
    assert "timestamp" in entry


def test_get_prompt_input_ok():
    """_get_prompt_input returns (value, True) when the dialog is accepted with text."""
    app = _make_app()
    with patch("core.tray_app.prompt_text") as dialog:
        dialog.return_value = ("hello", True)
        value, ok = app._get_prompt_input("Enter value")
        dialog.assert_called_once_with(None, "Input Required", "Enter value")
    assert value == "hello"
    assert ok is True


def test_get_prompt_input_cancelled():
    """_get_prompt_input returns (None, False) when the dialog is cancelled."""
    app = _make_app()
    with patch("core.tray_app.prompt_text") as dialog:
        dialog.return_value = ("", False)
        value, ok = app._get_prompt_input("Enter value")
        dialog.assert_called_once_with(None, "Input Required", "Enter value")
    assert value is None
    assert ok is False


def test_get_prompt_input_empty():
    """_get_prompt_input returns (None, False) when input is empty (ok=True)."""
    app = _make_app()
    with patch("core.tray_app.prompt_text") as dialog:
        dialog.return_value = ("", True)
        value, ok = app._get_prompt_input("Enter value")
        dialog.assert_called_once_with(None, "Input Required", "Enter value")
    assert value is None
    assert ok is False


def test_substitute_prompt_posix():
    """_substitute_prompt uses shlex.quote on POSIX (os.name != 'nt')."""
    app = _make_app()
    app._get_prompt_input = MagicMock(return_value=("value", True))
    with (
        patch("core.tray_app.os") as mock_os,
        patch("core.tray_app.shlex") as mock_shlex,
    ):
        mock_os.name = "posix"
        mock_shlex.quote.return_value = "'value'"
        command, ok = app._substitute_prompt("echo {promptInput}", "Enter value")
    assert command == "echo 'value'"
    assert ok is True
    mock_shlex.quote.assert_called_once_with("value")


def test_substitute_prompt_windows():
    """_substitute_prompt uses subprocess.list2cmdline on Windows (os.name == 'nt')."""
    app = _make_app()
    app._get_prompt_input = MagicMock(return_value=("a b", True))
    with (
        patch("core.tray_app.os") as mock_os,
        patch("core.tray_app.subprocess") as mock_sub,
    ):
        mock_os.name = "nt"
        mock_sub.list2cmdline.return_value = '"a b"'
        command, ok = app._substitute_prompt("echo {promptInput}", "Enter value")
    assert command == 'echo "a b"'
    assert ok is True
    mock_sub.list2cmdline.assert_called_once_with(["a b"])


def test_substitute_prompt_cancelled():
    """_substitute_prompt returns original command with ok=False when input is cancelled."""
    app = _make_app()
    app._get_prompt_input = MagicMock(return_value=(None, False))
    command, ok = app._substitute_prompt("echo {promptInput}", "Enter value")
    assert command == "echo {promptInput}"
    assert ok is False


def test_route_execution_confirm_declined():
    """_route_execution aborts before execution when confirmation is declined."""
    app = _make_app()
    app.show_command_output = MagicMock()
    with patch("core.tray_app.confirm_execute", return_value=False):
        app._route_execution("Term", "echo hi", True, False, "")
    app.executor.execute_command.assert_not_called()
    app.show_command_output.assert_not_called()


def test_route_execution_show_output():
    """_route_execution routes to show_command_output when show_output is True."""
    app = _make_app()
    app.show_command_output = MagicMock()
    app._route_execution("Status", "git status", False, True, "")
    app.show_command_output.assert_called_once_with("Status", "git status")
    app.executor.execute_command.assert_not_called()


def test_route_execution_direct():
    """_route_execution routes to executor.execute_command when show_output is False."""
    app = _make_app()
    app._route_execution("Term", "echo hi", False, False, "")
    app.executor.execute_command.assert_called_once_with("echo hi")


def test_route_execution_prompt_cancelled():
    """_route_execution aborts when _substitute_prompt reports cancellation."""
    app = _make_app()
    app.show_command_output = MagicMock()
    app._substitute_prompt = MagicMock(return_value=("echo {promptInput}", False))
    app._route_execution("Term", "echo {promptInput}", False, False, "Enter value")
    app.executor.execute_command.assert_not_called()
    app.show_command_output.assert_not_called()


# --------------------------------------------------------------------------- #
# _on_process_count_changed()                                                   #
# --------------------------------------------------------------------------- #


def test_update_badge_hides_running_action_when_zero():
    """With no running processes the running-action entry is hidden."""
    app = object.__new__(TrayApp)
    app._running_action = MagicMock()
    app.badge_manager = MagicMock()
    app._on_process_count_changed(0)
    app._running_action.setVisible.assert_any_call(False)
    app._running_action.setText.assert_not_called()
    app.badge_manager.update_badge.assert_called_once_with(0)


def test_update_badge_shows_count_when_running():
    """With running processes the running-action shows 'Running: N' and is visible."""
    app = object.__new__(TrayApp)
    app._running_action = MagicMock()
    app.badge_manager = MagicMock()
    app._on_process_count_changed(2)
    app._running_action.setText.assert_any_call("Running: 2")
    app._running_action.setVisible.assert_any_call(True)
    app.badge_manager.update_badge.assert_called_once_with(2)


# --------------------------------------------------------------------------- #
# show_command_output() lifecycle / _on_finished                                #
# --------------------------------------------------------------------------- #


def test_on_finished_removes_process_and_updates_badge():
    """When a process finishes it is removed from process_tracker and the badge refreshes."""
    app = object.__new__(TrayApp)
    app.app = MagicMock()
    app.services = MagicMock()
    app.services.config_manager = MagicMock()
    app.executor = MagicMock()
    app.module_controller = MagicMock()
    app.module_controller.get_executor.return_value = app.executor
    app.output_windows = []
    app.process_tracker = ProcessTracker()
    app.process_tracker.process_count_changed = MagicMock()

    process = app.executor.execute_command_process.return_value

    with patch("core.tray_app.RichOutputWindow"):
        app.show_command_output("Status", "git status")

    # Registration side effects.
    assert app.process_tracker.count() == 1

    # Capture and invoke the finished callback wired by show_command_output.
    on_finished = process.finished.connect.call_args[0][0]
    on_finished()

    assert app.process_tracker.count() == 0


# --------------------------------------------------------------------------- #
# Hotkey re-registration — exception swallowing                                 #
# --------------------------------------------------------------------------- #


def test_reregister_hotkey_swallows_exception():
    """_reregister_hotkey logs and swallows a failure instead of propagating it."""
    app = object.__new__(TrayApp)
    app.palette = MagicMock()
    app.module_controller = MagicMock()
    app.module_controller.loaded_palette = app.palette
    app.palette.register_hotkey.side_effect = RuntimeError("boom")
    # Must not raise.
    app._reregister_hotkey("ctrl+x")
    app.palette.register_hotkey.assert_called_once_with("ctrl+x")


def test_reregister_bar_hotkey_swallows_exception():
    """_reregister_bar_hotkey logs and swallows a failure instead of propagating it."""
    app = object.__new__(TrayApp)
    app.quick_launch_bar = MagicMock()
    app.module_controller = MagicMock()
    app.module_controller.loaded_quick_launch_bar = app.quick_launch_bar
    app.quick_launch_bar.unregister_hotkey.side_effect = RuntimeError("boom")
    # Must not raise.
    app._reregister_bar_hotkey("ctrl+y")


# ---------------------------------------------------------------------------
# Branding wiring (Issue #135)
# ---------------------------------------------------------------------------


def test_setup_paths_selects_branded_icon(tmp_path):
    """_setup_paths prefers the branded icon when it exists under base_dir."""
    app = object.__new__(TrayApp)
    branded = tmp_path / "resources" / "icons" / "branding" / "icon.png"
    branded.parent.mkdir(parents=True)
    branded.write_bytes(b"x")
    with patch("core.tray_app.config_manager") as cm:
        cm.get_base_dir.return_value = str(tmp_path)
        cm.get_settings.return_value = {}
        app._setup_paths()
    assert app.icon_file == str(branded)


def test_setup_tray_icon_calls_set_window_icon():
    """_setup_tray_icon wires setWindowIcon on the QApplication."""
    app = object.__new__(TrayApp)
    app.app = MagicMock()
    app.icon_file = "icon.png"
    app.cleanup = MagicMock()
    app._setup_tray_icon()
    app.app.setWindowIcon.assert_called_once()


def test_reload_menus_are_noops_before_tray_menu_is_built():
    """Regression: executing a command (e.g. via hotkey/palette) before the lazy
    tray menu was first opened raised AttributeError in a Qt slot -> app abort."""
    app = object.__new__(TrayApp)  # real reload_* methods, not the mocks of _make_app
    app.favorites_menu = None
    app.history_menu = None
    app.get_favorites = MagicMock()
    app.get_history = MagicMock()

    app.reload_favorites_commands()
    app.reload_history_commands()

    app.get_favorites.assert_not_called()
    app.get_history.assert_not_called()


def test_open_command_manager_displays_the_command_manager_dialog():
    """The Manage Commands action opens the manager with current app services."""
    app = object.__new__(TrayApp)
    app.services = MagicMock()
    app.process_tracker = MagicMock()

    with patch("core.tray_app.CommandManagerDialog") as dialog_factory:
        app._open_command_manager()

    dialog_factory.assert_called_once_with(
        app.services,
        app.process_tracker.processes,
        parent=None,
    )
    dialog_factory.return_value.exec.assert_called_once_with()


def test_pin_to_quick_launch_persists_group_reference_without_opening_manager():
    """Pinning stores the command's group and does not open command management."""
    app = _make_app()
    app.module_controller.loaded_quick_launch_bar = None
    settings = {"quick_launch_bar": {"pinned": []}}

    with (
        patch("core.tray_app.config_manager") as config,
        patch("core.tray_app.CommandManagerDialog") as dialog_factory,
    ):
        config.get_settings.return_value = settings
        app._pin_to_quick_launch(
            {
                "group": "System",
                "label": "Terminal",
                "command": "xterm",
                "confirm": False,
                "showOutput": True,
            }
        )

    assert settings["quick_launch_bar"]["pinned"] == [
        {
            "group": "System",
            "label": "Terminal",
            "command": "xterm",
            "confirm": False,
            "showOutput": True,
        }
    ]
    config.save_settings.assert_called_once_with(settings)
    dialog_factory.assert_not_called()
