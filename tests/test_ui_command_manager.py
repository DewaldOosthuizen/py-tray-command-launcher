from unittest.mock import patch

from ui.command_manager import CommandManagerDialog, _CommandFormDialog


def test_command_manager_dialog_instantiates(mock_services, qtbot):
    # Patch the module-level config_manager.get_commands() call inside
    # _load_tree() so the dialog does not touch the real filesystem or
    # JSON-schema resolver during the smoke test.
    with patch("ui.command_manager.config_manager") as mock_cm:
        mock_cm.get_commands.return_value = {}
        dialog = CommandManagerDialog(
            services=mock_services,
            running_processes={},
        )
        qtbot.addWidget(dialog)
        assert dialog is not None


def test_command_manager_loads_commands(mock_services, qtbot):
    """CommandManagerDialog._load_tree and _populate_group with real data."""
    commands = {
        "System": {
            "Terminal": {"command": "gnome-terminal"},
            "Editor": {
                "command": "gedit",
                "showOutput": True,
                "confirm": True,
                "prompt": "Open file:",
            },
            "icon": "system.png",
        },
        "Nested": {
            "Sub": {
                "Child": {"command": "child-cmd"},
            },
        },
    }
    with patch("ui.command_manager.config_manager") as mock_cm:
        mock_cm.get_commands.return_value = commands
        dialog = CommandManagerDialog(
            services=mock_services,
            running_processes={},
        )
        qtbot.addWidget(dialog)
    assert dialog is not None


def test_command_form_dialog_empty_groups(qtbot):
    """_CommandFormDialog instantiates with an empty group list."""
    dialog = _CommandFormDialog([])
    qtbot.addWidget(dialog)
    assert dialog is not None


def test_command_form_dialog_with_groups_and_initial(qtbot):
    """_CommandFormDialog with pre-populated initial data and groups."""
    initial = {
        "group": "System",
        "label": "Terminal",
        "command": "gnome-terminal",
        "showOutput": True,
        "confirm": False,
        "icon": "icon.png",
        "prompt": "Enter argument:",
    }
    dialog = _CommandFormDialog(["System", "Git"], initial=initial)
    qtbot.addWidget(dialog)
    data = dialog.result_data()
    assert isinstance(data, dict)
    assert "group" in data
    assert "label" in data
    assert "command" in data
