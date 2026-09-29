# SPDX-License-Identifier: GPL-3.0-or-later

"""Smoke tests for CommandManagerDialog.

Tests construct CommandManagerDialog with mock_services where
mock_services.config_manager is pre-configured, following the
self._services.config_manager DI pattern.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ui.command_manager import CommandManagerDialog  # noqa: E402


class TestCommandManagerDialog(unittest.TestCase):
    """Test suite for CommandManagerDialog module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_services.config_manager = self.mock_config_manager
        self.mock_services.reload_commands = MagicMock()
        self.mock_services.config_manager.get_commands.return_value = {}
        self.mock_services.config_manager.save_commands.return_value = True
        self.mock_services.get_all_commands.return_value = []

    # ------------------------------------------------------------------
    # _load_tree
    # ------------------------------------------------------------------

    def test_load_tree_calls_get_commands(self):
        """_load_tree should call config_manager.get_commands."""
        with patch("ui.command_manager.QTreeWidget"):
            _ = CommandManagerDialog(services=self.mock_services, running_processes={})
        self.mock_services.config_manager.get_commands.assert_called()

    def test_load_tree_with_commands(self):
        """_load_tree should populate tree with commands from config_manager."""
        commands = {
            "System": {
                "Terminal": {"command": "gnome-terminal"},
            }
        }
        self.mock_services.config_manager.get_commands.return_value = commands

        with patch("ui.command_manager.QTreeWidget"):
            with patch("ui.command_manager.QTreeWidgetItem"):
                _ = CommandManagerDialog(services=self.mock_services, running_processes={})


if __name__ == "__main__":
    unittest.main()
