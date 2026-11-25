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

from core.config_manager import ConfigManager
from modules.command_creator import (  # noqa: E402  # after src path setup
    CommandCreator,
    _collect_group_paths,
    _parse_group_path,
    _validate_group_path,
)


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
    group_combo.currentIndex.return_value = -1
    group_combo.currentText.return_value = "System"
    line_edits = [MagicMock(), MagicMock(), MagicMock()]
    line_edits[0].text.return_value = "Multiline Script"
    line_edits[1].text.return_value = ""
    line_edits[2].text.return_value = ""
    command_edit = MagicMock()
    command_edit.toPlainText.return_value = command
    checkboxes = [MagicMock(), MagicMock(), MagicMock()]
    for checkbox in checkboxes:
        checkbox.isChecked.return_value = False
    create_button = MagicMock()
    dialog = MagicMock()
    dialog.exec.side_effect = lambda: create_button.clicked.connect.call_args.args[0]()

    with (
        patch("modules.command_creator.QDialog", return_value=dialog),
        patch("modules.command_creator.QComboBox", return_value=group_combo),
        patch("modules.command_creator.QLineEdit", side_effect=line_edits),
        patch("modules.command_creator.QPlainTextEdit", return_value=command_edit, create=True),
        patch("modules.command_creator.QSizePolicy") as size_policy,
        patch("modules.command_creator.QCheckBox", side_effect=checkboxes),
        patch(
            "modules.command_creator.QPushButton",
            side_effect=lambda text: create_button if text == "Create" else MagicMock(),
        ),
        patch("modules.command_creator.QMessageBox"),
    ):
        CommandCreator(services).show_dialog()

    command_edit.setMinimumHeight.assert_called_once_with(120)
    command_edit.setSizePolicy.assert_called_once_with(
        size_policy.Policy.Expanding, size_policy.Policy.Expanding
    )
    reloaded = json.loads(commands_file.read_text(encoding="utf-8"))
    assert reloaded["System"]["Multiline Script"]["command"] == command


# ---------------------------------------------------------------------------
# Group path helpers (private helpers of command_creator)
# ---------------------------------------------------------------------------


def test_parse_group_path_splits_and_filters_empty():
    """_parse_group_path should split a path on separators and drop empties."""
    assert _parse_group_path("System / Tools / New") == ("System", "Tools", "New")
    assert _parse_group_path("System /  / Tools") == ("System", "Tools")
    assert _parse_group_path("System") == ("System",)
    assert _parse_group_path("") == ()


def test_collect_group_paths_returns_all_groups():
    """_collect_group_paths should return every top-level and nested group path."""
    commands = {
        "System": {
            "Tools": {},
            "Terminal": {"command": "gnome-terminal"},
        },
        "Media": {
            "icon": "icons/categories/media.png",
            "Youtube Music": {"command": "brave"},
        },
    }
    assert _collect_group_paths(commands) == [
        ("System",),
        ("System", "Tools"),
        ("Media",),
    ]


def test_validate_group_path_rejects_empty_components():
    """_validate_group_path should return False for paths containing empty components."""
    commands = {"System": {"Tools": {}}}
    assert _validate_group_path(commands, ("System", "", "Tools")) is False
    assert _validate_group_path(commands, ("", "Tools")) is False
    assert _validate_group_path(commands, ()) is False


def test_validate_group_path_rejects_final_command_collision():
    """_validate_group_path should return False when the leaf already holds a command."""
    commands = {"System": {"Terminal": {"command": "gnome-terminal"}}}
    assert _validate_group_path(commands, ("System", "Terminal")) is False
    assert _validate_group_path(commands, ("System", "Tools")) is True


def test_validate_group_path_rejects_intermediate_command_leaf():
    """_validate_group_path should return False when an intermediate component is a command leaf.

    A component that already holds a command cannot hold a subgroup, so paths
    that descend through it (for example "System / Terminal / New") are
    rejected rather than written inside the leaf.
    """
    commands = {"System": {"Terminal": {"command": "gnome-terminal"}}}
    assert _validate_group_path(commands, ("System", "Terminal", "New")) is False


# ---------------------------------------------------------------------------
# Command Creator dialog integration tests
# ---------------------------------------------------------------------------


def test_create_command_into_new_nested_group(tmp_path, monkeypatch):
    """AC-1 — creating into a new nested group path lands the command under the correct subgroup."""
    monkeypatch.setattr(ConfigManager, "_get_user_config_dir", lambda self: tmp_path / "app-config")
    config_manager = ConfigManager()
    commands_file = tmp_path / "commands.json"
    commands_file.write_text(json.dumps({"System": {"Tools": {}}}), encoding="utf-8")
    config_manager.set_commands_override(commands_file)

    services = MagicMock()
    services.config_manager = config_manager
    services.save_commands.side_effect = config_manager.save_commands

    group_combo = MagicMock()
    group_combo.currentIndex.return_value = -1
    group_combo.currentText.return_value = "System / Tools / New"
    line_edits = [MagicMock(), MagicMock(), MagicMock()]
    line_edits[0].text.return_value = "New Tool"
    line_edits[1].text.return_value = ""
    line_edits[2].text.return_value = "echo hello"
    checkboxes = [MagicMock(), MagicMock(), MagicMock()]
    for checkbox in checkboxes:
        checkbox.isChecked.return_value = False
    create_button = MagicMock()
    dialog = MagicMock()
    command_edit = MagicMock()
    command_edit.toPlainText.return_value = "echo hello"
    dialog.exec.side_effect = lambda: create_button.clicked.connect.call_args.args[0]()

    with (
        patch("modules.command_creator.QDialog", return_value=dialog),
        patch("modules.command_creator.QComboBox", return_value=group_combo),
        patch("modules.command_creator.QLineEdit", side_effect=line_edits),
        patch("modules.command_creator.QPlainTextEdit", return_value=command_edit, create=True),
        patch("modules.command_creator.QSizePolicy"),
        patch("modules.command_creator.QCheckBox", side_effect=checkboxes),
        patch(
            "modules.command_creator.QPushButton",
            side_effect=lambda text: create_button if text == "Create" else MagicMock(),
        ),
        patch("modules.command_creator.QMessageBox"),
    ):
        CommandCreator(services).show_dialog()

    expected = {
        "System": {
            "Tools": {
                "New": {
                    "New Tool": {
                        "command": "echo hello",
                        "showOutput": False,
                        "confirm": False,
                    }
                }
            }
        }
    }
    assert services.save_commands.call_count == 1
    saved = services.save_commands.call_args[0][0]
    assert saved == expected


def test_create_command_into_existing_nested_group_merges(tmp_path, monkeypatch):
    """AC-2 — creating into an existing nested group merges into that subgroup."""
    monkeypatch.setattr(ConfigManager, "_get_user_config_dir", lambda self: tmp_path / "app-config")
    config_manager = ConfigManager()
    commands_file = tmp_path / "commands.json"
    commands_file.write_text(json.dumps({"System": {"Tools": {}}}), encoding="utf-8")
    config_manager.set_commands_override(commands_file)

    services = MagicMock()
    services.config_manager = config_manager
    services.save_commands.side_effect = config_manager.save_commands

    group_combo = MagicMock()
    group_combo.currentIndex.return_value = 0
    group_combo.itemData.return_value = ("System", "Tools")
    line_edits = [MagicMock(), MagicMock(), MagicMock()]
    line_edits[0].text.return_value = "New Tool"
    line_edits[1].text.return_value = ""
    line_edits[2].text.return_value = "echo hello"
    checkboxes = [MagicMock(), MagicMock(), MagicMock()]
    for checkbox in checkboxes:
        checkbox.isChecked.return_value = False
    create_button = MagicMock()
    dialog = MagicMock()
    command_edit = MagicMock()
    command_edit.toPlainText.return_value = "echo hello"
    dialog.exec.side_effect = lambda: create_button.clicked.connect.call_args.args[0]()

    with (
        patch("modules.command_creator.QDialog", return_value=dialog),
        patch("modules.command_creator.QComboBox", return_value=group_combo),
        patch("modules.command_creator.QLineEdit", side_effect=line_edits),
        patch("modules.command_creator.QPlainTextEdit", return_value=command_edit, create=True),
        patch("modules.command_creator.QSizePolicy"),
        patch("modules.command_creator.QCheckBox", side_effect=checkboxes),
        patch(
            "modules.command_creator.QPushButton",
            side_effect=lambda text: create_button if text == "Create" else MagicMock(),
        ),
        patch("modules.command_creator.QMessageBox"),
    ):
        CommandCreator(services).show_dialog()

    expected = {
        "System": {
            "Tools": {
                "New Tool": {
                    "command": "echo hello",
                    "showOutput": False,
                    "confirm": False,
                }
            }
        }
    }
    assert services.save_commands.call_count == 1
    saved = services.save_commands.call_args[0][0]
    assert saved == expected


def test_create_command_preserves_existing_flat_groups(tmp_path, monkeypatch):
    """AC-3 — save/reload round-trip leaves existing flat groups and commands unchanged."""
    monkeypatch.setattr(ConfigManager, "_get_user_config_dir", lambda self: tmp_path / "app-config")
    config_manager = ConfigManager()
    commands_file = tmp_path / "commands.json"
    commands_file.write_text(
        json.dumps(
            {
                "System": {
                    "Terminal": {"command": "gnome-terminal", "showOutput": False, "confirm": False}
                },
                "Media": {
                    "icon": "icons/categories/media.png",
                    "Youtube Music": {
                        "command": "brave",
                        "showOutput": False,
                        "confirm": False,
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    config_manager.set_commands_override(commands_file)

    services = MagicMock()
    services.config_manager = config_manager
    services.save_commands.side_effect = config_manager.save_commands

    group_combo = MagicMock()
    group_combo.currentIndex.return_value = -1
    group_combo.currentText.return_value = "System / Tools / New"
    line_edits = [MagicMock(), MagicMock(), MagicMock()]
    line_edits[0].text.return_value = "New Tool"
    line_edits[1].text.return_value = ""
    line_edits[2].text.return_value = "echo hello"
    checkboxes = [MagicMock(), MagicMock(), MagicMock()]
    for checkbox in checkboxes:
        checkbox.isChecked.return_value = False
    create_button = MagicMock()
    dialog = MagicMock()
    command_edit = MagicMock()
    command_edit.toPlainText.return_value = "echo hello"
    dialog.exec.side_effect = lambda: create_button.clicked.connect.call_args.args[0]()

    with (
        patch("modules.command_creator.QDialog", return_value=dialog),
        patch("modules.command_creator.QComboBox", return_value=group_combo),
        patch("modules.command_creator.QLineEdit", side_effect=line_edits),
        patch("modules.command_creator.QPlainTextEdit", return_value=command_edit, create=True),
        patch("modules.command_creator.QSizePolicy"),
        patch("modules.command_creator.QCheckBox", side_effect=checkboxes),
        patch(
            "modules.command_creator.QPushButton",
            side_effect=lambda text: create_button if text == "Create" else MagicMock(),
        ),
        patch("modules.command_creator.QMessageBox"),
    ):
        CommandCreator(services).show_dialog()

    saved = json.loads(commands_file.read_text(encoding="utf-8"))
    # Existing flat groups and previously saved commands unchanged
    assert "System" in saved
    assert "Terminal" in saved["System"]
    assert saved["System"]["Terminal"]["command"] == "gnome-terminal"
    assert "Media" in saved
    assert "icon" in saved["Media"]
    assert "Youtube Music" in saved["Media"]
    assert saved["Media"]["Youtube Music"]["command"] == "brave"
    # New nested group created under System
    assert "Tools" in saved["System"]
    assert "New Tool" in saved["System"]["Tools"]["New"]
    assert saved["System"]["Tools"]["New"]["New Tool"]["command"] == "echo hello"


def test_create_command_rejects_collision_with_existing_command(tmp_path, monkeypatch):
    """Path validation rejects a final component that collides with an existing command."""
    monkeypatch.setattr(ConfigManager, "_get_user_config_dir", lambda self: tmp_path / "app-config")
    config_manager = ConfigManager()
    commands_file = tmp_path / "commands.json"
    commands_file.write_text(
        json.dumps(
            {
                "System": {
                    "Terminal": {"command": "gnome-terminal", "showOutput": False, "confirm": False}
                }
            }
        ),
        encoding="utf-8",
    )
    config_manager.set_commands_override(commands_file)

    services = MagicMock()
    services.config_manager = config_manager
    services.save_commands.side_effect = config_manager.save_commands

    group_combo = MagicMock()
    group_combo.currentIndex.return_value = -1
    group_combo.currentText.return_value = "System / Terminal"  # final component is a command
    line_edits = [MagicMock(), MagicMock(), MagicMock()]
    line_edits[0].text.return_value = "New Tool"
    line_edits[1].text.return_value = ""
    line_edits[2].text.return_value = "echo hello"
    checkboxes = [MagicMock(), MagicMock(), MagicMock()]
    for checkbox in checkboxes:
        checkbox.isChecked.return_value = False
    create_button = MagicMock()
    dialog = MagicMock()
    command_edit = MagicMock()
    command_edit.toPlainText.return_value = "echo hello"
    dialog.exec.side_effect = lambda: create_button.clicked.connect.call_args.args[0]()

    with (
        patch("modules.command_creator.QDialog", return_value=dialog),
        patch("modules.command_creator.QComboBox", return_value=group_combo),
        patch("modules.command_creator.QLineEdit", side_effect=line_edits),
        patch("modules.command_creator.QPlainTextEdit", return_value=command_edit, create=True),
        patch("modules.command_creator.QSizePolicy"),
        patch("modules.command_creator.QCheckBox", side_effect=checkboxes),
        patch(
            "modules.command_creator.QPushButton",
            side_effect=lambda text: create_button if text == "Create" else MagicMock(),
        ),
        patch("modules.command_creator.QMessageBox") as mock_box,
    ):
        CommandCreator(services).show_dialog()

    # Should reject and not save anything
    assert services.save_commands.call_count == 0
    mock_box.critical.assert_called_once()
    dialog.accept.assert_not_called()


def test_create_command_rejects_intermediate_command_leaf(tmp_path, monkeypatch):
    """AC-4 — a path through an existing command leaf is rejected and saves nothing."""
    monkeypatch.setattr(ConfigManager, "_get_user_config_dir", lambda self: tmp_path / "app-config")
    config_manager = ConfigManager()
    commands_file = tmp_path / "commands.json"
    commands_file.write_text(
        json.dumps(
            {
                "System": {
                    "Terminal": {"command": "gnome-terminal", "showOutput": False, "confirm": False}
                }
            }
        ),
        encoding="utf-8",
    )
    config_manager.set_commands_override(commands_file)

    services = MagicMock()
    services.config_manager = config_manager
    services.save_commands.side_effect = config_manager.save_commands

    group_combo = MagicMock()
    group_combo.currentIndex.return_value = -1
    group_combo.currentText.return_value = "System / Terminal / New"
    line_edits = [MagicMock(), MagicMock(), MagicMock()]
    line_edits[0].text.return_value = "New Tool"
    line_edits[1].text.return_value = ""
    line_edits[2].text.return_value = "echo hello"
    checkboxes = [MagicMock(), MagicMock(), MagicMock()]
    for checkbox in checkboxes:
        checkbox.isChecked.return_value = False
    create_button = MagicMock()
    dialog = MagicMock()
    command_edit = MagicMock()
    command_edit.toPlainText.return_value = "echo hello"
    dialog.exec.side_effect = lambda: create_button.clicked.connect.call_args.args[0]()

    with (
        patch("modules.command_creator.QDialog", return_value=dialog),
        patch("modules.command_creator.QComboBox", return_value=group_combo),
        patch("modules.command_creator.QLineEdit", side_effect=line_edits),
        patch("modules.command_creator.QPlainTextEdit", return_value=command_edit, create=True),
        patch("modules.command_creator.QSizePolicy"),
        patch("modules.command_creator.QCheckBox", side_effect=checkboxes),
        patch(
            "modules.command_creator.QPushButton",
            side_effect=lambda text: create_button if text == "Create" else MagicMock(),
        ),
        patch("modules.command_creator.QMessageBox") as mock_box,
    ):
        CommandCreator(services).show_dialog()

    # Should reject: "Terminal" holds a command and cannot hold a subgroup.
    assert services.save_commands.call_count == 0
    mock_box.critical.assert_called_once()
    dialog.accept.assert_not_called()

    # The configuration must remain untouched (including the canonical command
    # leaf shape: command + showOutput + confirm).
    assert json.loads(commands_file.read_text(encoding="utf-8")) == {
        "System": {"Terminal": {"command": "gnome-terminal", "showOutput": False, "confirm": False}}
    }


if __name__ == "__main__":
    unittest.main()
