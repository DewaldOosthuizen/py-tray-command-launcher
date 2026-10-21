from unittest.mock import MagicMock, patch

from ui.command_manager import CommandManagerDialog, _CommandFormDialog
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog


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


def _tree_item(dialog, *path):
    """Return the tree item at an exact sequence of displayed path components."""
    item = dialog._tree.topLevelItem(0)
    assert item.text(0) == path[0]
    for component in path[1:]:
        item = next(item.child(i) for i in range(item.childCount()) if item.child(i).text(0) == component)
    return item


def _visible_command_names(dialog):
    names = []

    def visit(item):
        for index in range(item.childCount()):
            child = item.child(index)
            if not child.isHidden():
                if child.data(0, Qt.ItemDataRole.UserRole)["type"] == "command":
                    names.append(child.text(0))
                visit(child)

    for index in range(dialog._tree.topLevelItemCount()):
        visit(dialog._tree.topLevelItem(index))
    return names


def _nested_commands():
    return {
        "System": {
            "Tools": {
                "Terminal": {
                    "command": "gnome-terminal --window",
                    "showOutput": True,
                    "confirm": False,
                    "prompt": "Terminal title",
                    "icon": "terminal.png",
                },
                "Editor": {"command": "code", "confirm": True},
                "icon": "tools.png",
            },
            "Keep": {"command": "keep"},
            "icon": "system.png",
        },
        "System.Tools": {"Literal dot group": {"command": "literal"}},
        "Utilities": {"Cleanup": {"command": "cleanup temp files"}},
    }


def _real_manager(commands, qtbot):
    services = MagicMock()
    services.config_manager.get_commands.return_value = commands
    dialog = CommandManagerDialog(services, {})
    qtbot.addWidget(dialog)
    return dialog, services


def test_filter_matches_name_command_and_group_path_retaining_ancestors(mock_services, qtbot):
    commands = _nested_commands()
    mock_services.config_manager.get_commands.return_value = commands
    dialog = CommandManagerDialog(mock_services, {})
    qtbot.addWidget(dialog)

    dialog._search_edit.setText("terminal")
    assert _visible_command_names(dialog) == ["Terminal"]
    assert not _tree_item(dialog, "System", "Tools").isHidden()
    assert not _tree_item(dialog, "System").isHidden()

    dialog._search_edit.setText("system.tools")
    assert _visible_command_names(dialog) == ["Terminal", "Editor"]

    dialog._search_edit.setText("cleanup temp")
    assert _visible_command_names(dialog) == ["Cleanup"]


def test_filter_restores_tree_and_shows_empty_state_without_persistence(mock_services, qtbot):
    commands = _nested_commands()
    mock_services.config_manager.get_commands.return_value = commands
    dialog = CommandManagerDialog(mock_services, {})
    qtbot.addWidget(dialog)
    initial_names = sorted(_visible_command_names(dialog))

    dialog._search_edit.setText("no such command")
    assert _visible_command_names(dialog) == []
    assert not dialog._empty_label.isHidden()
    assert "No commands" in dialog._empty_label.text()

    dialog._search_edit.clear()
    assert sorted(_visible_command_names(dialog)) == initial_names
    assert dialog._empty_label.isHidden()
    mock_services.config_manager.save_commands.assert_not_called()
    mock_services.reload_commands.assert_not_called()


def test_selected_command_details_show_full_configured_values_without_saving(mock_services, qtbot):
    commands = _nested_commands()
    mock_services.config_manager.get_commands.return_value = commands
    dialog = CommandManagerDialog(mock_services, {})
    qtbot.addWidget(dialog)

    item = _tree_item(dialog, "System", "Tools", "Terminal")
    dialog._tree.setCurrentItem(item)
    details = dialog._details_view.toPlainText()
    assert "System / Tools" in details
    for value in ("Terminal", "gnome-terminal --window", "terminal.png", "Terminal title", "showOutput"):
        assert value in details
    assert dialog._details_view.isReadOnly()
    mock_services.config_manager.save_commands.assert_not_called()
    mock_services.reload_commands.assert_not_called()


def test_tree_metadata_preserves_group_components_containing_dots(mock_services, qtbot):
    mock_services.config_manager.get_commands.return_value = _nested_commands()
    dialog = CommandManagerDialog(mock_services, {})
    qtbot.addWidget(dialog)
    item = _tree_item(dialog, "System.Tools", "Literal dot group")
    metadata = item.data(0, Qt.ItemDataRole.UserRole)
    assert metadata["group_path"] == ("System.Tools",)


def _select_nested_command(dialog, label="Terminal"):
    dialog._tree.setCurrentItem(_tree_item(dialog, "System", "Tools", label))


def _accepted_form(result):
    form = MagicMock()
    form.exec.return_value = QDialog.DialogCode.Accepted
    form.result_data.return_value = result
    return form


def test_edit_nested_command_in_place_preserves_siblings_and_exact_parent(qtbot):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, qtbot)
    _select_nested_command(dialog)
    form = _accepted_form(
        {"group_path": ("System", "Tools"), "group": "System / Tools", "label": "Terminal", "command": "new-terminal", "showOutput": False, "confirm": True}
    )
    with patch("ui.command_manager._CommandFormDialog", return_value=form):
        dialog._edit_command()

    assert commands["System"]["Tools"]["Terminal"]["command"] == "new-terminal"
    assert commands["System"]["Tools"]["Editor"] == {"command": "code", "confirm": True}
    assert commands["System"]["Tools"]["icon"] == "tools.png"
    assert "System.Tools" in commands
    assert "Terminal" not in commands["System"]
    services.config_manager.save_commands.assert_called_once_with(commands)


def test_edit_nested_command_to_other_path_preserves_siblings(qtbot):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, qtbot)
    _select_nested_command(dialog)
    form = _accepted_form(
        {"group_path": ("Utilities",), "group": "Utilities", "label": "Terminal New", "command": "new-terminal", "showOutput": True, "confirm": False}
    )
    with patch("ui.command_manager._CommandFormDialog", return_value=form):
        dialog._edit_command()

    assert "Terminal" not in commands["System"]["Tools"]
    assert commands["System"]["Tools"]["Editor"] == {"command": "code", "confirm": True}
    assert commands["System"]["Tools"]["icon"] == "tools.png"
    assert commands["Utilities"]["Terminal New"]["command"] == "new-terminal"
    assert commands["Utilities"]["Cleanup"] == {"command": "cleanup temp files"}
    assert "Utilities" not in commands["System"]
    services.config_manager.save_commands.assert_called_once_with(commands)


def test_delete_nested_command_removes_only_target_and_preserves_subgroups(qtbot):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, qtbot)
    _select_nested_command(dialog)
    with patch("ui.command_manager.confirm_action", return_value=True):
        dialog._delete_command()

    assert "Terminal" not in commands["System"]["Tools"]
    assert commands["System"]["Tools"]["Editor"] == {"command": "code", "confirm": True}
    assert commands["System"]["Tools"]["icon"] == "tools.png"
    assert commands["System"]["Keep"] == {"command": "keep"}
    services.config_manager.save_commands.assert_called_once_with(commands)


def test_delete_nested_command_cancel_keeps_configuration_unchanged(qtbot):
    commands = _nested_commands()
    original = {key: value.copy() for key, value in commands.items()}
    dialog, services = _real_manager(commands, qtbot)
    _select_nested_command(dialog)
    with patch("ui.command_manager.confirm_action", return_value=False):
        dialog._delete_command()
    assert commands == original
    services.config_manager.save_commands.assert_not_called()


def test_move_nested_commands_reorders_direct_entries_and_preserves_icon_and_siblings(qtbot):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, qtbot)
    _select_nested_command(dialog, "Editor")
    dialog._move_up()
    assert list(commands["System"]["Tools"]) == ["icon", "Editor", "Terminal"]
    assert commands["System"]["Tools"]["icon"] == "tools.png"
    assert commands["System"]["Tools"]["Editor"] == {"command": "code", "confirm": True}
    assert commands["System"]["Keep"] == {"command": "keep"}

    _select_nested_command(dialog, "Editor")
    dialog._move_down()
    assert list(commands["System"]["Tools"]) == ["icon", "Terminal", "Editor"]
    assert commands["System"]["Tools"]["Terminal"]["command"] == "gnome-terminal --window"
    assert commands["System"]["icon"] == "system.png"
    assert services.config_manager.save_commands.call_count == 2


def test_typed_group_name_with_dot_remains_one_top_level_component(qtbot):
    dialog = _CommandFormDialog([("System", "Tools")])
    qtbot.addWidget(dialog)
    dialog._group_combo.setEditText("New.Group")
    dialog._name_edit.setText("Example")
    dialog._cmd_edit.setText("example")
    assert dialog.result_data()["group_path"] == ("New.Group",)
