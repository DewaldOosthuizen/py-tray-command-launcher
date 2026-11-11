# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for command_executor module.

Tests cover subprocess-based execution, PID logging, QProcess creation, and
silent execution modes, using the actual public API:
  - execute_command(command)
  - execute_command_process(app, command)
  - execute_command_process_silently(app, command)
"""

import os
import shlex
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# [ORCHESTRATOR NOTE] Pre-existing failure — unrelated to issue #38
# Failure: ModuleNotFoundError: No module named 'PyQt6' — src/modules/command_executor.py imports PyQt6.QtCore but PyQt6 is not installed. Fix: add sys.modules stubs for PyQt6 before importing.
from modules.command_executor import CommandExecutor


class TestCommandExecutor(unittest.TestCase):
    """Test suite for CommandExecutor."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.executor = CommandExecutor(self.mock_services)

    # ------------------------------------------------------------------
    # execute_command (subprocess path)
    # ------------------------------------------------------------------

    def test_execute_command_calls_popen(self):
        """execute_command should invoke subprocess.Popen with the given command."""
        mock_proc = MagicMock()
        mock_proc.pid = 12345

        with patch(
            "modules.command_executor.subprocess.Popen", return_value=mock_proc
        ) as mock_popen:
            self.executor.execute_command("ls -la")

        mock_popen.assert_called_once_with("ls -la", shell=True)

    def test_execute_command_logs_pid(self):
        """execute_command should log the process PID at DEBUG level."""
        mock_proc = MagicMock()
        mock_proc.pid = 99

        with patch("modules.command_executor.subprocess.Popen", return_value=mock_proc):
            with patch("modules.command_executor.logger") as mock_logger:
                self.executor.execute_command("echo hello")

        # At least one debug call must reference the PID
        debug_messages = " ".join(str(c) for c in mock_logger.debug.call_args_list)
        self.assertIn("99", debug_messages)

    def test_execute_command_handles_oserror(self):
        """execute_command should catch OSError from Popen, log at ERROR, and not raise."""
        with patch(
            "modules.command_executor.subprocess.Popen",
            side_effect=OSError("Failed to start command"),
        ) as mock_popen:
            with patch("modules.command_executor.logger") as mock_logger:
                # Should not raise
                self.executor.execute_command("nonexistent-cmd")

        # Popen should have been called
        mock_popen.assert_called_once_with("nonexistent-cmd", shell=True)
        # logger.error should have been called with the command and exception details
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0]
        # call_args[0] = format string, call_args[1] = command, call_args[2] = exception
        self.assertEqual(call_args[1], "nonexistent-cmd")
        self.assertIn("Failed to start command", str(call_args[2]))

    def test_execute_command_handles_fileNotFoundError(self):
        """execute_command should catch FileNotFoundError (subclass of OSError)."""
        with patch(
            "modules.command_executor.subprocess.Popen",
            side_effect=FileNotFoundError("No such file or directory: 'bash'"),
        ) as mock_popen:
            with patch("modules.command_executor.logger") as mock_logger:
                # Should not raise
                self.executor.execute_command("some-command")

        mock_popen.assert_called_once_with("some-command", shell=True)
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0]
        self.assertEqual(call_args[1], "some-command")
        self.assertIn("No such file or directory", str(call_args[2]))

    def test_execute_command_immediate_failure_missing_executable(self):
        with patch(
            "modules.command_executor.subprocess.Popen",
            side_effect=FileNotFoundError("No such file"),
        ):
            with patch("modules.command_executor.logger"):
                self.executor.execute_command("missing-cmd")
        self.mock_services.notify_user.assert_called_once()

    def test_execute_command_immediate_failure_permission_denied(self):
        with patch(
            "modules.command_executor.subprocess.Popen",
            side_effect=PermissionError("Permission denied"),
        ):
            with patch("modules.command_executor.logger"):
                self.executor.execute_command("secret-cmd")
        self.mock_services.notify_user.assert_called_once()

    def test_execute_command_launch_failure_notifies_and_logs_context(self):
        error = OSError("resource temporarily unavailable")
        with (
            patch("modules.command_executor.subprocess.Popen", side_effect=error),
            patch("modules.command_executor.logger") as mock_logger,
        ):
            self.executor.execute_command("blocked-command")

        mock_logger.error.assert_called_once()
        self.assertIn("blocked-command", str(mock_logger.error.call_args))
        self.assertIn(str(error), str(mock_logger.error.call_args))
        self.assertEqual(
            mock_logger.error.call_args.kwargs["extra"],
            {"command": "blocked-command", "error": str(error)},
        )
        self.mock_services.notify_user.assert_called_once()
        self.assertIn("blocked-command", self.mock_services.notify_user.call_args.kwargs["message"])

    def test_execute_command_poll_immediate_failure(self):
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = 127
        mock_proc.returncode = 127
        with patch("modules.command_executor.subprocess.Popen", return_value=mock_proc):
            with patch("modules.command_executor.logger") as mock_logger:
                self.executor.execute_command("badcmd")
        mock_logger.error.assert_called()
        msg = " ".join(str(c) for c in mock_logger.error.call_args_list)
        self.assertIn("127", msg)
        self.mock_services.notify_user.assert_called_once()

    def test_execute_command_poll_still_running_not_flagged(self):
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.returncode = None
        mock_proc.wait.return_value = 0
        with patch("modules.command_executor.subprocess.Popen", return_value=mock_proc):
            with patch("modules.command_executor.logger") as mock_logger:
                self.executor.execute_command("longcmd")
        mock_logger.error.assert_not_called()
        self.mock_services.notify_user.assert_not_called()

    def test_execute_command_poll_fast_success_not_flagged(self):
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = 42
        mock_proc.returncode = 0
        with patch("modules.command_executor.subprocess.Popen", return_value=mock_proc):
            with patch("modules.command_executor.logger") as mock_logger:
                self.executor.execute_command("fastcmd")
        mock_logger.error.assert_not_called()
        self.mock_services.notify_user.assert_not_called()

    def test_execute_command_wait_oserror(self):
        """execute_command should catch OSError from process.wait() and notify user."""
        mock_proc = MagicMock()
        mock_proc.pid = 1
        mock_proc.poll.return_value = None
        mock_proc.returncode = None
        mock_proc.wait.side_effect = OSError("Unable to wait for command")

        class _SynchronousThread:
            """Run the completion target in start() so assertions are deterministic."""

            def __init__(self, target, args=(), **kwargs):
                self._target = target
                self._args = args

            def start(self):
                self._target(*self._args)

        with patch("modules.command_executor.subprocess.Popen", return_value=mock_proc):
            with patch("modules.command_executor.logger") as mock_logger:
                with patch("modules.command_executor.threading.Thread", _SynchronousThread):
                    self.executor.execute_command("longcmd")

        # OSError should be logged once, with the command and the failure reason.
        mock_logger.error.assert_called_once()
        logged = " ".join(str(part) for part in mock_logger.error.call_args[0])
        self.assertIn("Unable to wait", logged)
        self.assertIn("longcmd", logged)

        # The failure should be surfaced to the user exactly once.
        self.mock_services.notify_user.assert_called_once()
        self.assertIn("longcmd", self.mock_services.notify_user.call_args.kwargs["message"])

    # ------------------------------------------------------------------
    # execute_command_process (QProcess path)
    # ------------------------------------------------------------------

    def test_execute_command_process_returns_qprocess(self):
        """execute_command_process should configure and return a QProcess."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch(
            "modules.command_executor.QProcess", return_value=mock_process
        ) as mock_qprocess_cls:
            result = self.executor.execute_command_process(mock_app, "top")

        mock_qprocess_cls.assert_called_once_with(mock_app)
        mock_process.setProgram.assert_called_once_with("bash")
        mock_process.setArguments.assert_called_once_with(["-c", "top"])
        self.assertIs(result, mock_process)

    def test_execute_command_process_starts_process(self):
        """execute_command_process should call start() before returning."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            self.executor.execute_command_process(mock_app, "pwd")

        mock_process.start.assert_called_once()

    # ------------------------------------------------------------------
    # execute_command_process_silently
    # ------------------------------------------------------------------

    def test_execute_command_process_silently_starts_process_exactly_once(self):
        """QProcess.start() must be called exactly once via the silent path."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            # Spy on the inner helper to confirm it is called (and only it starts the process)
            with patch.object(
                self.executor,
                "execute_command_process",
                wraps=self.executor.execute_command_process,
            ) as mock_execute_command_process:
                self.executor.execute_command_process_silently(mock_app, "df -h")

        mock_execute_command_process.assert_called_once_with(mock_app, "df -h")
        # The process must have been started exactly once regardless of call path.
        self.assertEqual(
            mock_process.start.call_count,
            1,
            "QProcess.start() must be called exactly once on the silent path",
        )

    def test_execute_command_process_silently_logs_command(self):
        """execute_command_process_silently should log the command."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            with patch("modules.command_executor.logger") as mock_logger:
                self.executor.execute_command_process_silently(mock_app, "uptime")

        # Either info or debug logging should mention the command
        all_calls = mock_logger.info.call_args_list + mock_logger.debug.call_args_list
        messages = " ".join(str(c) for c in all_calls)
        self.assertIn("uptime", messages)

    # ------------------------------------------------------------------
    # Signal wiring tests (issue #60)
    # ------------------------------------------------------------------

    def test_execute_command_process_wires_error_signal(self):
        """execute_command_process should connect errorOccurred before start()."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            self.executor.execute_command_process(mock_app, "ls")

        mock_process.errorOccurred.connect.assert_called_once()
        # Verify ordering: errorOccurred.connect must appear before start()
        call_names = [str(c) for c in mock_process.mock_calls]
        connect_idx = next(i for i, c in enumerate(call_names) if "errorOccurred.connect" in c)
        start_idx = next(i for i, c in enumerate(call_names) if c == "call.start()")
        self.assertLess(
            connect_idx, start_idx, "errorOccurred.connect() must be called before start()"
        )

    def test_execute_command_process_wires_finished_signal(self):
        """execute_command_process should connect finished before start()."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            self.executor.execute_command_process(mock_app, "ls")

        mock_process.finished.connect.assert_called_once()
        # Verify ordering: finished.connect must appear before start()
        call_names = [str(c) for c in mock_process.mock_calls]
        connect_idx = next(i for i, c in enumerate(call_names) if "finished.connect" in c)
        start_idx = next(i for i, c in enumerate(call_names) if c == "call.start()")
        self.assertLess(connect_idx, start_idx, "finished.connect() must be called before start()")

    def test_execute_command_process_silently_wires_error_signal(self):
        """Silent path should also wire errorOccurred via execute_command_process."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            self.executor.execute_command_process_silently(mock_app, "uptime")

        mock_process.errorOccurred.connect.assert_called_once()

    def test_execute_command_process_finished_logs_warning_on_nonzero_exit(self):
        """finished lambda should call logger.warning when exit code != 0."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            with patch("modules.command_executor.logger") as mock_logger:
                self.executor.execute_command_process(mock_app, "false")
                # Extract and invoke the finished lambda
                finished_cb = mock_process.finished.connect.call_args[0][0]
                finished_cb(1, "NormalExit")

        mock_logger.warning.assert_called_once()

    def test_execute_command_process_finished_notifies_on_nonzero_exit(self):
        """A non-zero QProcess exit should surface the same failure notification."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            self.executor.execute_command_process(mock_app, "false")
            finished_cb = mock_process.finished.connect.call_args[0][0]
            finished_cb(1, "NormalExit")

        self.mock_services.notify_user.assert_called_once()
        self.assertIn("false", self.mock_services.notify_user.call_args.kwargs["message"])

    def test_execute_command_process_finished_logs_info_on_zero_exit(self):
        """finished lambda should call logger.info when exit code == 0."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch("modules.command_executor.QProcess", return_value=mock_process):
            with patch("modules.command_executor.logger") as mock_logger:
                self.executor.execute_command_process(mock_app, "true")
                info_count_before = mock_logger.info.call_count
                finished_cb = mock_process.finished.connect.call_args[0][0]
                finished_cb(0, "NormalExit")

        mock_logger.warning.assert_not_called()
        self.assertGreater(
            mock_logger.info.call_count,
            info_count_before,
            "finished callback should call logger.info for zero exit code",
        )


class TestPromptInputSanitisation(unittest.TestCase):
    """Tests verifying that shlex.quote() is applied to {promptInput} in tray_app.execute()."""

    def test_shlex_quote_escapes_semicolon(self):
        """shlex.quote should wrap input containing ; so it is not treated as a command separator."""
        import shlex

        result = shlex.quote("foo; rm -rf /")
        self.assertEqual(result, "'foo; rm -rf /'")

    def test_prompt_input_metacharacters_are_quoted(self):
        """shlex.quote wraps metachar input in single-quotes, neutralising injection."""
        import shlex

        dangerous = "; rm -rf /"
        quoted = shlex.quote(dangerous)
        # Must be wrapped in single quotes so shell treats it as a single literal token
        self.assertTrue(
            quoted.startswith("'") and quoted.endswith("'"),
            f"Expected single-quoted string, got: {quoted!r}",
        )
        # The quoted result must be a single shell word (no unquoted whitespace)
        self.assertEqual(
            quoted.count("'"), 2, f"Expected exactly one pair of single quotes, got: {quoted!r}"
        )

    def test_metacharacter_variants_are_quoted(self):
        """shlex.quote neutralises all common injection metacharacters."""
        import shlex

        metacharacters = [
            ";",
            "&&",
            "|",
            "$(echo x)",
            "`echo x`",
            ">",
            "<",
            "$VAR",
        ]
        for meta in metacharacters:
            with self.subTest(meta=meta):
                quoted = shlex.quote(meta)
                # shlex.quote either wraps in single-quotes or escapes
                # Either way the metachar must not appear unquoted
                self.assertTrue(
                    quoted.startswith("'") or quoted.startswith('"') or quoted.startswith("\\"),
                    f"shlex.quote({meta!r}) -> {quoted!r} — not properly quoted",
                )

    def test_benign_input_is_not_over_escaped(self):
        """shlex.quote should pass through simple safe filenames without extra escaping."""
        import shlex

        benign = "my_file.txt"
        result = shlex.quote(benign)
        # shlex.quote returns the bare word when no quoting is needed
        self.assertEqual(result, benign, f"Benign input over-escaped: {result!r}")

    def test_tray_app_execute_applies_shlex_quote(self):
        """TrayApp.execute() must pass shlex-quoted prompt input to execute_command."""
        import shlex

        from core.tray_app import TrayApp

        # Build a minimal TrayApp instance without running __init__
        tray_app = object.__new__(TrayApp)
        mock_executor = MagicMock()
        tray_app.executor = mock_executor
        tray_app.module_controller = MagicMock()
        tray_app.module_controller.get_executor.return_value = mock_executor
        tray_app.reload_history_commands = MagicMock()
        tray_app.reload_favorites_commands = MagicMock()

        dangerous_input = "; rm -rf /"

        with (
            patch("core.tray_app.config_manager"),
            patch("core.tray_app.prompt_text") as mock_prompt,
        ):
            mock_prompt.return_value = (dangerous_input, True)
            tray_app.execute(
                title="Test",
                command="echo {promptInput}",
                confirm=False,
                show_output=False,
                prompt="Enter value",
            )

        mock_executor.execute_command.assert_called_once()
        actual_command = mock_executor.execute_command.call_args[0][0]
        # The dangerous input must arrive as a quoted shell token
        self.assertIn(shlex.quote(dangerous_input), actual_command)

    def test_semicolon_injection_does_not_spawn_second_process(self):
        """Injecting '; id' must not cause Popen to be called more than once."""
        import shlex

        from core.tray_app import TrayApp

        tray_app = object.__new__(TrayApp)
        tray_app.executor = CommandExecutor(MagicMock())
        tray_app.module_controller = MagicMock()
        tray_app.module_controller.get_executor.return_value = tray_app.executor
        tray_app.reload_history_commands = MagicMock()
        tray_app.reload_favorites_commands = MagicMock()

        dangerous_input = "; id"

        with (
            patch("subprocess.Popen") as mock_popen,
            patch("core.tray_app.config_manager"),
            patch("core.tray_app.prompt_text") as mock_prompt,
        ):
            mock_popen.return_value.pid = 12345
            mock_prompt.return_value = (dangerous_input, True)
            tray_app.execute(
                title="Test",
                command="echo {promptInput}",
                confirm=False,
                show_output=False,
                prompt="Enter value",
            )

        # The shell must only have been invoked once — echo only, not echo + id
        mock_popen.assert_called_once()
        actual_command = mock_popen.call_args[0][0]
        # The quoted payload must appear verbatim in the command string
        self.assertIn(shlex.quote(dangerous_input), actual_command)
        # The raw injection metacharacter must NOT appear as a bare token
        self.assertNotIn("; id", actual_command.replace(shlex.quote(dangerous_input), ""))


if __name__ == "__main__":
    unittest.main()


@pytest.mark.skipif(os.name == "nt", reason="FIFO gate requires a POSIX OS")
def test_shell_failure_is_reported_once_on_gui_thread_without_blocking(tmp_path):
    """A shell blocked on a deterministic FIFO gate is observed asynchronously."""
    fifo = tmp_path / "release"
    os.mkfifo(fifo)
    missing_executable = tmp_path / "not-installed-command"
    command = f"read -r _ < {shlex.quote(str(fifo))}; {shlex.quote(str(missing_executable))}"
    script = """
import os
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QCoreApplication, QTimer

sys.path.insert(0, str(Path.cwd() / "src"))
from modules.command_executor import CommandExecutor

application = QCoreApplication([])
main_thread = threading.get_ident()
notifications = []
notification_threads = []
timer_ticks = []
ready_to_release = threading.Event()
release_gate = threading.Event()
timed_out = []

class Services:
    def notify_user(self, title, message):
        notifications.append((title, message))
        notification_threads.append(threading.get_ident())
        application.quit()

fifo = Path(__FIFO__)
command = __COMMAND__
created_processes = []
real_popen = subprocess.Popen

def capture_process(*args, **kwargs):
    process = real_popen(*args, **kwargs)
    created_processes.append(process)
    return process

def release_when_shell_is_waiting():
    with fifo.open("w", encoding="utf-8") as gate:
        ready_to_release.set()
        if release_gate.wait(5):
            gate.write("release\\n")

def keep_event_loop_responsive():
    timer_ticks.append(True)
    if ready_to_release.is_set() and len(timer_ticks) >= 2:
        release_gate.set()
    else:
        QTimer.singleShot(0, keep_event_loop_responsive)

with patch("modules.command_executor.subprocess.Popen", side_effect=capture_process):
    executor = CommandExecutor(Services())
    executor.execute_command(command)

assert len(created_processes) == 1
process = created_processes[0]
assert process.poll() is None
threading.Thread(target=release_when_shell_is_waiting, daemon=True).start()
QTimer.singleShot(0, keep_event_loop_responsive)
QTimer.singleShot(5000, lambda: (timed_out.append(True), application.quit()))
application.exec()
process.wait(timeout=1)
assert not timed_out, "completion notification did not arrive"
assert process.returncode not in (None, 0)
assert len(notifications) == 1
assert notification_threads == [main_thread]
assert len(timer_ticks) >= 2
""".replace("__FIFO__", repr(str(fifo))).replace("__COMMAND__", repr(command))
    environment = os.environ.copy()
    environment["PY_TRAY_NO_STUB"] = "1"
    environment["QT_QPA_PLATFORM"] = "offscreen"
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, f"{result.stdout}\n{result.stderr}"
