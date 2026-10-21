from unittest.mock import MagicMock, patch

from ui.command_manager import CommandManagerDialog, _CommandFormDialog


def test_command_manager_dialog_instantiates(mock_services, qtbot):
    # Patch the module-level config_manager.get_commands() call inside
    # _load_tree() so the dialog does not touch the real filesystem or
    # JSON-schema resolver during the smoke test.
    mock_services.config_manager.get_commands.return_value = {}
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
    mock_services.config_manager.get_commands.return_value = commands
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


def test_command_form_validation_uses_shared_warning_helper():
    dialog = object.__new__(_CommandFormDialog)
    dialog._group_combo = MagicMock()
    dialog._group_combo.currentText.return_value = ""
    dialog.accept = MagicMock()

    with patch("ui.command_manager.show_warning") as show_warning:
        dialog._validate_and_accept()

    show_warning.assert_called_once_with(dialog, "Error", "Group is required.")
    dialog.accept.assert_not_called()


def _manager_for_delete(commands):
    dialog = object.__new__(CommandManagerDialog)
    dialog._services = MagicMock()
    dialog._services.config_manager.get_commands.return_value = commands
    dialog._tree = MagicMock()
    item = MagicMock()
    item.data.return_value = {"type": "command", "group": "System", "label": "Terminal"}
    dialog._tree.currentItem.return_value = item
    dialog._load_tree = MagicMock()
    return dialog


def test_delete_command_uses_shared_confirmation_and_does_not_mutate_on_cancel():
    commands = {"System": {"Terminal": {"command": "terminal"}}}
    dialog = _manager_for_delete(commands)
    with patch("ui.command_manager.confirm_action", create=True, return_value=False) as confirm:
        dialog._delete_command()
    confirm.assert_called_once_with(dialog, "Confirm Delete", "Delete 'Terminal'?")
    assert commands == {"System": {"Terminal": {"command": "terminal"}}}
    dialog._services.config_manager.save_commands.assert_not_called()


def test_delete_command_uses_shared_confirmation_and_deletes_on_accept():
    commands = {"System": {"Terminal": {"command": "terminal"}}}
    dialog = _manager_for_delete(commands)
    with patch("ui.command_manager.confirm_action", create=True, return_value=True) as confirm:
        dialog._delete_command()
    confirm.assert_called_once_with(dialog, "Confirm Delete", "Delete 'Terminal'?")
    assert commands == {"System": {}}
    dialog._services.config_manager.save_commands.assert_called_once_with(commands)


def test_edit_command_in_nested_group_resolves_path_and_preserves_siblings():
    commands = {
        "Nested": {
            "Sub": {
                "Keep": {"command": "keep"},
                "Old": {"command": "old", "confirm": True, "icon": "old.png"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    dialog = object.__new__(CommandManagerDialog)
    dialog._services = MagicMock()
    dialog._services.config_manager.get_commands.return_value = commands
    dialog._tree = MagicMock()
    item = MagicMock()
    item.data.return_value = {
        "type": "command",
        "group": "Nested.Sub",
        "label": "Old",
        "data": {"command": "old", "confirm": True, "icon": "old.png"},
    }
    dialog._tree.currentItem.return_value = item
    dialog._load_tree = MagicMock()

    with patch("ui.command_manager._CommandFormDialog") as FormDlg:
        form = MagicMock()
        form.exec.return_value = 1  # QDialog.DialogCode.Accepted under stub & real Qt
        form.result_data.return_value = {
            "group": "Nested.Sub",
            "label": "New",
            "command": "old",
            "confirm": True,
            "icon": "old.png",
        }
        FormDlg.return_value = form
        dialog._edit_command()

    expected = {
        "Nested": {
            "Sub": {
                "Keep": {"command": "keep"},
                "New": {"command": "old", "confirm": True, "icon": "old.png"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    assert commands == expected
    dialog._services.config_manager.save_commands.assert_called_once()
    dialog._load_tree.assert_called_once()


def test_edit_command_can_move_into_new_nested_group():
    commands = {
        "Nested": {
            "Sub": {
                "Old": {"command": "old", "icon": "old.png"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    dialog = object.__new__(CommandManagerDialog)
    dialog._services = MagicMock()
    dialog._services.config_manager.get_commands.return_value = commands
    dialog._tree = MagicMock()
    item = MagicMock()
    item.data.return_value = {
        "type": "command",
        "group": "Nested.Sub",
        "label": "Old",
        "data": {"command": "old", "icon": "old.png"},
    }
    dialog._tree.currentItem.return_value = item
    dialog._load_tree = MagicMock()

    with patch("ui.command_manager._CommandFormDialog") as FormDlg:
        form = MagicMock()
        form.exec.return_value = 1
        form.result_data.return_value = {
            "group": "Nested.NewGroup",
            "label": "Old",
            "command": "old",
            "icon": "old.png",
        }
        FormDlg.return_value = form
        dialog._edit_command()

    expected = {
        "Nested": {
            "Sub": {},
            "NewGroup": {
                "Old": {"command": "old", "icon": "old.png"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    assert commands == expected
    dialog._services.config_manager.save_commands.assert_called_once()


def test_delete_command_in_nested_group_removals_only_that_command():
    commands = {
        "Nested": {
            "Sub": {
                "GrandChild": {"command": "grandchild"},
                "Keep": {"command": "keep"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    dialog = object.__new__(CommandManagerDialog)
    dialog._services = MagicMock()
    dialog._services.config_manager.get_commands.return_value = commands
    dialog._tree = MagicMock()
    item = MagicMock()
    item.data.return_value = {
        "type": "command",
        "group": "Nested.Sub",
        "label": "GrandChild",
        "data": {"command": "grandchild"},
    }
    dialog._tree.currentItem.return_value = item
    dialog._load_tree = MagicMock()

    with patch("ui.command_manager.confirm_action", create=True, return_value=True) as confirm:
        dialog._delete_command()

    assert commands == {
        "Nested": {
            "Sub": {
                "Keep": {"command": "keep"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    confirm.assert_called_once()
    dialog._services.config_manager.save_commands.assert_called_once()


def test_delete_nested_subgroup_removes_only_that_subgroup():
    commands = {
        "System": {"Terminal": {"command": "terminal"}},
        "Nested": {
            "Sub": {
                "Child": {"command": "child"},
            },
            "icon": "nested.png",
        },
    }
    dialog = object.__new__(CommandManagerDialog)
    dialog._services = MagicMock()
    dialog._services.config_manager.get_commands.return_value = commands
    dialog._tree = MagicMock()
    item = MagicMock()
    item.data.return_value = {
        "type": "group",
        "name": "Nested.Sub",
    }
    dialog._tree.currentItem.return_value = item
    dialog._load_tree = MagicMock()

    with patch("ui.command_manager.confirm_action", create=True, return_value=True) as confirm:
        dialog._delete_command()

    assert commands == {
        "System": {"Terminal": {"command": "terminal"}},
        "Nested": {
            "icon": "nested.png",
        },
    }
    confirm.assert_called_once()
    dialog._services.config_manager.save_commands.assert_called_once()


def test_move_command_within_nested_group_preserves_siblings_and_icon():
    commands = {
        "Nested": {
            "Sub": {
                "First": {"command": "first"},
                "Second": {"command": "second"},
                "icon": "nested.png",
            },
        },
    }
    dialog = object.__new__(CommandManagerDialog)
    dialog._services = MagicMock()
    dialog._services.config_manager.get_commands.return_value = commands
    dialog._tree = MagicMock()
    item = MagicMock()
    item.data.return_value = {
        "type": "command",
        "group": "Nested.Sub",
        "label": "Second",
        "data": {"command": "second"},
    }
    dialog._tree.currentItem.return_value = item
    dialog._load_tree = MagicMock()

    with patch("ui.command_manager.confirm_action", create=True, return_value=True):
        dialog._move_item(-1)

    expected = {
        "Nested": {
            "Sub": {
                "Second": {"command": "second"},
                "First": {"command": "first"},
                "icon": "nested.png",
            },
        },
    }
    assert commands == expected
    dialog._services.config_manager.save_commands.assert_called_once()


def test_add_command_to_existing_nested_group_preserves_siblings_and_path():
    commands = {
        "Nested": {
            "Sub": {
                "Sibling": {"command": "sibling"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    dialog = object.__new__(CommandManagerDialog)
    dialog._services = MagicMock()
    dialog._services.config_manager.get_commands.return_value = commands
    dialog._tree = MagicMock()
    dialog._load_tree = MagicMock()

    with patch("ui.command_manager._CommandFormDialog") as FormDlg:
        form = MagicMock()
        form.exec.return_value = 1  # QDialog.DialogCode.Accepted under stub & real Qt
        form.result_data.return_value = {
            "group": "Nested.Sub",
            "label": "Child",
            "command": "child-cmd",
            "confirm": True,
            "icon": "child.png",
        }
        FormDlg.return_value = form
        dialog._add_command()

    # The command must land under commands["Nested"]["Sub"] (path-aware resolve),
    # leaving the subgroup's unrelated sibling intact.
    expected = {
        "Nested": {
            "Sub": {
                "Sibling": {"command": "sibling"},
                "Child": {"command": "child-cmd", "confirm": True, "icon": "child.png"},
            },
            "icon": "nested.png",
        },
        "System": {"Terminal": {"command": "terminal"}},
    }
    assert commands == expected
    # No top-level "Nested.Sub" key was created for the nested path.
    assert "Nested.Sub" not in commands
    dialog._services.config_manager.save_commands.assert_called_once()
    dialog._load_tree.assert_called_once()
