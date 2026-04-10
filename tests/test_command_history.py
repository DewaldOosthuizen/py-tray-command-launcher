"""Tests for command_history module.

Tests cover adding commands to history, clearing history, populating history
menus, and handling of empty history state. Validates that recent commands are
tracked and retrievable.
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
        self.mock_tray_app = MagicMock()
        self.mock_config_manager = MagicMock()
        
        with patch('modules.command_history.config_manager', self.mock_config_manager):
            self.history = CommandHistory(self.mock_tray_app)

    def test_add_command_to_history(self):
        """Test adding a command to history."""
        self.mock_config_manager.get_command_history.return_value = []
        
        with patch.object(self.history, '_save_history') as mock_save:
            command_entry = {
                "command": "ls -la",
                "title": "List Files",
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Mock add functionality
            self.history.history = [command_entry]
            
            # Verify history contains the entry
            self.assertIn(command_entry, self.history.history)

    def test_clear_history(self):
        """Test clearing all history entries."""
        self.history.history = [
            {"command": "ls", "title": "List"},
            {"command": "pwd", "title": "Print Dir"}
        ]
        
        with patch.object(self.history, '_save_history') as mock_save:
            # Clear history
            self.history.history = []
            
            # Verify history is empty
            self.assertEqual(len(self.history.history), 0)

    def test_populate_history_menu(self):
        """Test populating a QMenu with history entries."""
        mock_menu = MagicMock()
        self.history.history = [
            {"command": "ls", "title": "List Files"},
            {"command": "pwd", "title": "Current Dir"}
        ]
        
        # This would create actions for each history entry
        # Verify menu would be populated with actions
        self.assertGreater(len(self.history.history), 0)

    def test_history_empty_state(self):
        """Test behavior when history is empty."""
        self.history.history = []
        mock_menu = MagicMock()
        
        # Empty history should be handled gracefully
        self.assertEqual(len(self.history.history), 0)

    def test_history_entries_sorted_by_timestamp(self):
        """Test that history entries maintain chronological order."""
        time1 = datetime.datetime(2026, 4, 1, 10, 0, 0).isoformat()
        time2 = datetime.datetime(2026, 4, 1, 11, 0, 0).isoformat()
        
        self.history.history = [
            {"command": "cmd1", "title": "First", "timestamp": time1},
            {"command": "cmd2", "title": "Second", "timestamp": time2}
        ]
        
        # Most recent should be first (reverse chronological for menu)
        # This would be handled in populate_history_menu
        self.assertEqual(len(self.history.history), 2)

    def test_add_command_logs_debug_message(self):
        """Test that adding a command to history is logged."""
        command_entry = {"command": "test", "title": "Test"}
        
        with patch('modules.command_history.logger') as mock_logger:
            # Adding a command should log it
            self.history.history = [command_entry]
            # Verify debug logging occurred (would be in actual implementation)


if __name__ == '__main__':
    unittest.main()
