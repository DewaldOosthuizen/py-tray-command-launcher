# SPDX-License-Identifier: GPL-3.0-or-later

"""Smoke tests for CommandCreator module.

Tests construct CommandCreator with mock_services where
mock_services.config_manager is pre-configured, following the
self.services.config_manager DI pattern.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config_manager import ConfigManager  # noqa: E402  # after src path setup
from modules.command_creator import CommandCreator  # noqa: E402  # after src path setup


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


def test_create_command_preserves_multiline_text_through_persistence(tmp_path, monkeypatch):
    """The creator saves and reloads the exact multiline command text."""
    monkeypatch.setattr(ConfigManager, "_get_user_config_dir", lambda self: tmp_path / "app-config")
    config_manager = ConfigManager()
    commands_file = tmp_path / "commands.json"
    commands_file.write_text(json.dumps({"System": {}}), encoding="utf-8")
    config_manager.set_commands_override(commands_file)

    services = MagicMock()
    services.config_manager = config_manager
    services.save_commands.side_effect = config_manager.save_commands
    command = "  #!/bin/sh\necho 'first line'\necho 'last line'  "
    group_combo = MagicMock()
    group_combo.currentText.return_value = "System"
    line_edits = [MagicMock(), MagicMock(), MagicMock()]
    line_edits[0].text.return_value = "Multiline Script"
    line_edits[1].text.return_value = ""
    line_edits[2].text.return_value = ""
    command_edit = MagicMock()
    command_edit.toPlainText.return_value = command
    create_button = MagicMock()
    dialog = MagicMock()
    dialog.exec.side_effect = lambda: create_button.clicked.connect.call_args.args[0]()

    with (
        patch("modules.command_creator.QDialog", return_value=dialog),
        patch("modules.command_creator.QComboBox", return_value=group_combo),
        patch("modules.command_creator.QLineEdit", side_effect=line_edits),
        patch("modules.command_creator.QPlainTextEdit", return_value=command_edit, create=True),
        patch(
            "modules.command_creator.QPushButton",
            side_effect=lambda text: create_button if text == "Create" else MagicMock(),
        ),
        patch("modules.command_creator.QMessageBox"),
    ):
        CommandCreator(services).show_dialog()

    reloaded = json.loads(commands_file.read_text(encoding="utf-8"))
    assert reloaded["System"]["Multiline Script"]["command"] == command


if __name__ == "__main__":
    unittest.main()
