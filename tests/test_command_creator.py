# SPDX-License-Identifier: GPL-3.0-or-later

"""Smoke tests for CommandCreator module.

Tests construct CommandCreator with mock_services where
mock_services.config_manager is pre-configured, following the
self.services.config_manager DI pattern.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.command_creator import CommandCreator  # noqa: E402


class TestCommandCreator(unittest.TestCase):
    """Test suite for CommandCreator module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_services.config_manager = self.mock_config_manager
        self.mock_services.reload_commands = MagicMock()
        self.mock_config_manager.get_commands.return_value = {
            "System": {"Terminal": {"command": "gnome-terminal"}},
        }

    def test_constructor_with_services(self):
        """CommandCreator should accept services in constructor."""
        with (
            patch("modules.command_creator.QDialog"),
            patch("modules.command_creator.QComboBox"),
            patch("modules.command_creator.QLineEdit"),
            patch("modules.command_creator.QLabel"),
            patch("modules.command_creator.QPushButton"),
            patch("modules.command_creator.QVBoxLayout"),
            patch("modules.command_creator.QHBoxLayout"),
            patch("modules.command_creator.QCheckBox"),
            patch("modules.command_creator.QFileDialog"),
            patch("modules.command_creator.QMessageBox"),
        ):
            creator = CommandCreator(self.mock_services)
            assert creator is not None

    def test_show_dialog_calls_get_commands(self):
        """show_dialog should call config_manager.get_commands to populate group combo."""
        with (
            patch("modules.command_creator.QDialog"),
            patch("modules.command_creator.QComboBox") as mock_combo_cls,
            patch("modules.command_creator.QLineEdit"),
            patch("modules.command_creator.QLabel"),
            patch("modules.command_creator.QPushButton"),
            patch("modules.command_creator.QVBoxLayout"),
            patch("modules.command_creator.QHBoxLayout"),
            patch("modules.command_creator.QCheckBox"),
            patch("modules.command_creator.QFileDialog"),
            patch("modules.command_creator.QMessageBox"),
        ):
            mock_combo = MagicMock()
            mock_combo_cls.return_value = mock_combo

            creator = CommandCreator(self.mock_services)
            creator.show_dialog()

        self.mock_config_manager.get_commands.assert_called()

    def test_show_dialog_rejects_shows_dialog(self):
        """show_dialog when user cancels (DialogCode.Rejected) should complete without error."""
        with (
            patch("modules.command_creator.QDialog") as mock_dialog_cls,
            patch("modules.command_creator.QComboBox"),
            patch("modules.command_creator.QLineEdit"),
            patch("modules.command_creator.QLabel"),
            patch("modules.command_creator.QPushButton"),
            patch("modules.command_creator.QVBoxLayout"),
            patch("modules.command_creator.QHBoxLayout"),
            patch("modules.command_creator.QCheckBox"),
            patch("modules.command_creator.QFileDialog"),
            patch("modules.command_creator.QMessageBox"),
        ):
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = 0  # Rejected
            mock_dialog_cls.return_value = mock_dialog

            creator = CommandCreator(self.mock_services)
            # Should not raise
            creator.show_dialog()

            # Dialog should be shown
            mock_dialog.exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
