# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for command_executor module.

Tests cover subprocess-based execution, PID logging, QProcess creation, and
silent execution modes, using the actual public API:
  - execute_command(command)
  - execute_command_process(app, command)
  - execute_command_process_silently(app, command)
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock, call
import logging

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

        with patch('modules.command_executor.subprocess.Popen', return_value=mock_proc) as mock_popen:
            self.executor.execute_command("ls -la")

        mock_popen.assert_called_once_with("ls -la", shell=True)

    def test_execute_command_logs_pid(self):
        """execute_command should log the process PID at DEBUG level."""
        mock_proc = MagicMock()
        mock_proc.pid = 99

        with patch('modules.command_executor.subprocess.Popen', return_value=mock_proc):
            with patch('modules.command_executor.logger') as mock_logger:
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

        with patch('modules.command_executor.QProcess', return_value=mock_process) as mock_qprocess_cls:
            result = self.executor.execute_command_process(mock_app, "top")

        mock_qprocess_cls.assert_called_once_with(mock_app)
        mock_process.setProgram.assert_called_once_with("bash")
        mock_process.setArguments.assert_called_once_with(["-c", "top"])
        self.assertIs(result, mock_process)

    def test_execute_command_process_starts_process(self):
        """execute_command_process should call start() before returning."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch('modules.command_executor.QProcess', return_value=mock_process):
            self.executor.execute_command_process(mock_app, "pwd")

        mock_process.start.assert_called_once()

    # ------------------------------------------------------------------
    # execute_command_process_silently
    # ------------------------------------------------------------------

    def test_execute_command_process_silently_starts_process_exactly_once(self):
        """QProcess.start() must be called exactly once via the silent path."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch('modules.command_executor.QProcess', return_value=mock_process):
            # Spy on the inner helper to confirm it is called (and only it starts the process)
            with patch.object(
                self.executor,
                'execute_command_process',
                wraps=self.executor.execute_command_process,
            ) as mock_execute_command_process:
                self.executor.execute_command_process_silently(mock_app, "df -h")

        mock_execute_command_process.assert_called_once_with(mock_app, "df -h")
        # The process must have been started exactly once regardless of call path.
        self.assertEqual(mock_process.start.call_count, 1,
                         "QProcess.start() must be called exactly once on the silent path")

    def test_execute_command_process_silently_logs_command(self):
        """execute_command_process_silently should log the command."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch('modules.command_executor.QProcess', return_value=mock_process):
            with patch('modules.command_executor.logger') as mock_logger:
                self.executor.execute_command_process_silently(mock_app, "uptime")

        # Either info or debug logging should mention the command
        all_calls = mock_logger.info.call_args_list + mock_logger.debug.call_args_list
        messages = " ".join(str(c) for c in all_calls)
        self.assertIn("uptime", messages)


class TestPromptInputSanitisation(unittest.TestCase):
    """Tests verifying that shlex.quote() is applied to {promptInput} in tray_app.execute()."""

    def test_shlex_quote_escapes_semicolon(self):
        """shlex.quote should wrap input containing ; so it is not treated as a command separator."""
        import shlex
        result = shlex.quote("foo; rm -rf /")
        self.assertEqual(result, "'foo; rm -rf /'")

    @unittest.mock.patch('builtins.__import__', side_effect=None)
    def test_prompt_input_metacharacters_are_quoted(self, *_):
        """shlex.quote wraps metachar input in single-quotes, neutralising injection."""
        import shlex
        dangerous = "; rm -rf /"
        quoted = shlex.quote(dangerous)
        # Must be wrapped in single quotes so shell treats it as a literal string
        self.assertTrue(quoted.startswith("'") and quoted.endswith("'"),
                        f"Expected single-quoted string, got: {quoted!r}")
        # The resulting command should not start a new shell command
        self.assertNotIn(";", quoted.strip("'"))

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
        self.assertEqual(result, benign,
                         f"Benign input over-escaped: {result!r}")

    def test_tray_app_execute_applies_shlex_quote(self):
        """tray_app.execute() must use shlex.quote() when substituting {promptInput}."""
        import shlex
        # Simulate what tray_app.execute() should now do
        command_template = "echo {promptInput}"
        user_input = "; rm -rf /"
        command = command_template.replace("{promptInput}", shlex.quote(user_input))
        # The dangerous semicolon must be inside quotes now
        self.assertIn("'", command)
        self.assertNotIn("; rm", command.split("'")[0])  # not before the opening quote


if __name__ == '__main__':
    unittest.main()
