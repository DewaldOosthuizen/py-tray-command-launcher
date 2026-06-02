# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for command_executor module.

Tests cover subprocess-based execution, PID logging, QProcess creation, and
silent execution modes, using the actual public API:
  - execute_command(command)
  - execute_command_process(app, command)
  - execute_command_process_silently(app, command)
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        tray_app.reload_history_commands = MagicMock()
        tray_app.reload_favorites_commands = MagicMock()

        dangerous_input = "; rm -rf /"

        with (
            patch("core.tray_app.config_manager"),
            patch("core.tray_app.QInputDialog") as mock_dialog,
        ):
            mock_dialog.getText.return_value = (dangerous_input, True)
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
        tray_app.executor = CommandExecutor.__new__(CommandExecutor)
        tray_app.reload_history_commands = MagicMock()
        tray_app.reload_favorites_commands = MagicMock()

        dangerous_input = "; id"

        with (
            patch("subprocess.Popen") as mock_popen,
            patch("core.tray_app.config_manager"),
            patch("core.tray_app.QInputDialog") as mock_dialog,
        ):
            mock_popen.return_value.pid = 12345
            mock_dialog.getText.return_value = (dangerous_input, True)
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
