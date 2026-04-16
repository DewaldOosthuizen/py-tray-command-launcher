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

    def test_execute_command_process_does_not_start_process(self):
        """execute_command_process should return the process without calling start()."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch('modules.command_executor.QProcess', return_value=mock_process):
            self.executor.execute_command_process(mock_app, "pwd")

        mock_process.start.assert_not_called()

    # ------------------------------------------------------------------
    # execute_command_process_silently
    # ------------------------------------------------------------------

    def test_execute_command_process_silently_starts_process(self):
        """execute_command_process_silently should call start() on the QProcess."""
        mock_process = MagicMock()
        mock_app = MagicMock()

        with patch('modules.command_executor.QProcess', return_value=mock_process):
            self.executor.execute_command_process_silently(mock_app, "df -h")

        mock_process.start.assert_called_once()

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


if __name__ == '__main__':
    unittest.main()
