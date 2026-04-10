"""Tests for command_history module.

Tests call the real public methods (add_to_history, populate_menu,
clear_history) while patching modules.command_history.config_manager so
that no filesystem I/O is performed.
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock, call
import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.command_history import CommandHistory


class TestCommandHistory(unittest.TestCase):
    """Test suite for CommandHistory module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_config_manager.get_history.return_value = []

        with patch('modules.command_history.config_manager', self.mock_config_manager):
            self.history = CommandHistory(self.mock_services)

    # ------------------------------------------------------------------
    # add_to_history
    # ------------------------------------------------------------------

    def test_add_command_to_history(self):
        """add_to_history should persist the command via config_manager."""
        with patch('modules.command_history.config_manager', self.mock_config_manager):
            self.history.add_to_history(
                title="List Files", command="ls -la",
                confirm=False, show_output=False, prompt=None
            )

        self.mock_config_manager.add_to_history.assert_called_once()
        entry = self.mock_config_manager.add_to_history.call_args[0][0]
        self.assertEqual(entry["command"], "ls -la")
        self.assertEqual(entry["title"], "List Files")
        self.assertIn("timestamp", entry)

    def test_add_command_logs_debug_message(self):
        """add_to_history should emit a debug or info log message."""
        with patch('modules.command_history.logger') as mock_logger:
            with patch('modules.command_history.config_manager', self.mock_config_manager):
                self.history.add_to_history(
                    title="Test", command="test",
                    confirm=False, show_output=False, prompt=None
                )

        self.assertTrue(
            mock_logger.debug.called or mock_logger.info.called,
            "Expected at least one debug/info log call after add_to_history",
        )

    # ------------------------------------------------------------------
    # clear_history
    # ------------------------------------------------------------------

    def test_clear_history(self):
        """clear_history should call config_manager.clear_history."""
        with patch('modules.command_history.config_manager', self.mock_config_manager):
            self.history.clear_history()

        self.mock_config_manager.clear_history.assert_called_once()

    def test_clear_history_reloads_commands(self):
        """clear_history should trigger a history reload via services."""
        with patch('modules.command_history.config_manager', self.mock_config_manager):
            self.history.clear_history()

        self.mock_services.reload_history_commands.assert_called_once()

    # ------------------------------------------------------------------
    # populate_menu
    # ------------------------------------------------------------------

    def test_populate_history_menu(self):
        """populate_menu should add one action per history entry."""
        mock_menu = MagicMock()
        self.mock_config_manager.get_history.return_value = [
            {"command": "ls", "title": "List Files",
             "confirm": False, "showOutput": False, "prompt": None},
            {"command": "pwd", "title": "Current Dir",
             "confirm": False, "showOutput": False, "prompt": None},
        ]

        with patch('modules.command_history.QAction', return_value=MagicMock()):
            with patch('modules.command_history.config_manager', self.mock_config_manager):
                self.history.populate_menu(mock_menu)

        # At least 2 addAction calls for the history entries (plus "Clear History")
        self.assertGreaterEqual(mock_menu.addAction.call_count, 2)

    def test_history_empty_state(self):
        """populate_menu with empty history should still call get_history."""
        mock_menu = MagicMock()
        self.mock_config_manager.get_history.return_value = []

        with patch('modules.command_history.config_manager', self.mock_config_manager):
            self.history.populate_menu(mock_menu)

        self.mock_config_manager.get_history.assert_called()

    def test_history_entries_order(self):
        """populate_menu should add history entries in the order returned by config_manager."""
        time1 = datetime.datetime(2026, 4, 1, 10, 0, 0).isoformat()
        time2 = datetime.datetime(2026, 4, 1, 11, 0, 0).isoformat()
        mock_menu = MagicMock()
        # Most recent first (as stored by add_to_history in config_manager)
        self.mock_config_manager.get_history.return_value = [
            {"command": "cmd2", "title": "Second", "timestamp": time2,
             "confirm": False, "showOutput": False, "prompt": None},
            {"command": "cmd1", "title": "First", "timestamp": time1,
             "confirm": False, "showOutput": False, "prompt": None},
        ]

        created_titles = []

        def capture_qaction(title, *args, **kwargs):
            created_titles.append(title)
            return MagicMock()

        with patch('modules.command_history.QAction', side_effect=capture_qaction):
            with patch('modules.command_history.config_manager', self.mock_config_manager):
                self.history.populate_menu(mock_menu)

        self.assertIn("Second", created_titles)
        self.assertIn("First", created_titles)
        self.assertLess(
            created_titles.index("Second"),
            created_titles.index("First"),
            "Expected 'Second' (newer) to appear before 'First' (older)",
        )


if __name__ == '__main__':
    unittest.main()
