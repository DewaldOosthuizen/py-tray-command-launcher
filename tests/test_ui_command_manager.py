from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

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
    item.data.return_value = {"type": "command", "group_path": ("System",), "label": "Terminal"}
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
        item = next(
            item.child(i) for i in range(item.childCount()) if item.child(i).text(0) == component
        )
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
                "Diagnostics": {"Logs": {"command": "journalctl"}},
                "icon": "tools.png",
            },
            "Keep": {"command": "keep"},
            "icon": "system.png",
        },
        "System.Tools": {"Literal dot group": {"command": "literal"}},
        "Utilities": {"Cleanup": {"command": "cleanup temp files"}},
    }


class _FakeTreeItem:
    def __init__(self, text):
        self._texts = list(text)
        self._children = []
        self._data = {}
        self._hidden = False

    def text(self, column):
        return self._texts[column]

    def setData(self, column, role, value):
        self._data[column] = value

    def data(self, column, role):
        return self._data.get(column)

    def addChild(self, child):
        self._children.append(child)

    def childCount(self):
        return len(self._children)

    def child(self, index):
        return self._children[index]

    def setHidden(self, hidden):
        self._hidden = hidden

    def isHidden(self):
        return self._hidden

    def setExpanded(self, expanded):
        self._expanded = expanded


class _FakeTree:
    def __init__(self):
        self._roots = []
        self._current = None

    def clear(self):
        self._roots.clear()

    def addTopLevelItem(self, item):
        self._roots.append(item)

    def topLevelItemCount(self):
        return len(self._roots)

    def topLevelItem(self, index):
        return self._roots[index]

    def currentItem(self):
        return self._current

    def setCurrentItem(self, item):
        self._current = item


class _FakeTextView:
    def __init__(self):
        self.text = ""

    def clear(self):
        self.text = ""

    def setPlainText(self, text):
        self.text = text

    def toPlainText(self):
        return self.text


class _FakeLabel:
    def __init__(self):
        self.visible = False

    def setVisible(self, visible):
        self.visible = visible

    def isHidden(self):
        return not self.visible

    def text(self):
        return "No commands match your search."


def _real_manager(commands, monkeypatch):
    import ui.command_manager as command_manager

    services = MagicMock()
    services.config_manager.get_commands.return_value = commands
    dialog = CommandManagerDialog.__new__(CommandManagerDialog)
    dialog._services = services
    dialog._running = {}
    dialog._tree = _FakeTree()
    dialog._details_view = _FakeTextView()
    dialog._empty_label = _FakeLabel()
    monkeypatch.setattr(command_manager, "QTreeWidgetItem", _FakeTreeItem)
    dialog._load_tree = CommandManagerDialog._load_tree.__get__(dialog)
    dialog._load_tree()
    return dialog, services


def test_filter_matches_name_command_and_group_path_retaining_ancestors(mock_services, monkeypatch):
    commands = _nested_commands()
    mock_services.config_manager.get_commands.return_value = commands
    dialog, _ = _real_manager(commands, monkeypatch)

    dialog._filter_tree("terminal")
    assert _visible_command_names(dialog) == ["Terminal"]
    assert not _tree_item(dialog, "System", "Tools").isHidden()
    assert not _tree_item(dialog, "System").isHidden()

    dialog._filter_tree("system / tools")
    assert _visible_command_names(dialog) == ["Terminal", "Editor", "Logs"]

    dialog._filter_tree("cleanup temp")
    assert _visible_command_names(dialog) == ["Cleanup"]


def test_filter_restores_tree_and_shows_empty_state_without_persistence(mock_services, monkeypatch):
    commands = _nested_commands()
    mock_services.config_manager.get_commands.return_value = commands
    dialog, _ = _real_manager(commands, monkeypatch)
    initial_names = sorted(_visible_command_names(dialog))

    dialog._filter_tree("no such command")
    assert _visible_command_names(dialog) == []
    assert not dialog._empty_label.isHidden()
    assert "No commands" in dialog._empty_label.text()

    dialog._filter_tree("")
    assert sorted(_visible_command_names(dialog)) == initial_names
    assert dialog._empty_label.isHidden()
    mock_services.config_manager.save_commands.assert_not_called()
    mock_services.reload_commands.assert_not_called()


def test_selected_command_details_show_full_configured_values_without_saving(
    mock_services, monkeypatch
):
    commands = _nested_commands()
    mock_services.config_manager.get_commands.return_value = commands
    dialog, _ = _real_manager(commands, monkeypatch)

    item = _tree_item(dialog, "System", "Tools", "Terminal")
    dialog._tree.setCurrentItem(item)
    dialog._update_details(item)
    details = dialog._details_view.toPlainText()
    assert '["System", "Tools"]' in details
    for value in (
        "Terminal",
        "gnome-terminal --window",
        "terminal.png",
        "Terminal title",
        "showOutput",
    ):
        assert value in details

    mock_services.config_manager.save_commands.assert_not_called()
    mock_services.reload_commands.assert_not_called()


def test_tree_metadata_preserves_group_components_containing_dots(monkeypatch):
    dialog, _ = _real_manager(
        {"System.Tools": {"Literal dot group": {"command": "literal"}}}, monkeypatch
    )
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


def test_edit_nested_command_in_place_preserves_siblings_and_exact_parent(monkeypatch):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, monkeypatch)
    _select_nested_command(dialog)
    form = _accepted_form(
        {
            "group_path": ("System", "Tools"),
            "group": "System / Tools",
            "label": "Terminal",
            "command": "new-terminal",
            "showOutput": False,
            "confirm": True,
        }
    )
    with patch("ui.command_manager._CommandFormDialog", return_value=form):
        dialog._edit_command()

    assert commands["System"]["Tools"]["Terminal"]["command"] == "new-terminal"
    assert commands["System"]["Tools"]["Editor"] == {"command": "code", "confirm": True}
    assert commands["System"]["Tools"]["icon"] == "tools.png"
    assert "System.Tools" in commands
    assert "Terminal" not in commands["System"]
    services.config_manager.save_commands.assert_called_once_with(commands)


def test_edit_rejects_destination_label_collision_without_overwriting(monkeypatch):
    commands = _nested_commands()
    original = {
        "command": commands["System"]["Tools"]["Editor"]["command"],
        "confirm": commands["System"]["Tools"]["Editor"]["confirm"],
    }
    dialog, services = _real_manager(commands, monkeypatch)
    _select_nested_command(dialog)
    form = _accepted_form(
        {
            "group_path": ("System", "Tools"),
            "group": "System / Tools",
            "label": "Editor",
            "command": "replacement-command",
            "showOutput": False,
            "confirm": False,
        }
    )
    with patch("ui.command_manager._CommandFormDialog", return_value=form):
        dialog._edit_command()

    assert commands["System"]["Tools"]["Editor"] == original
    assert commands["System"]["Tools"]["Terminal"]["command"] == "gnome-terminal --window"
    services.config_manager.save_commands.assert_not_called()


def test_editing_command_in_place_preserves_menu_order(monkeypatch):
    commands = {
        "System": {
            "First": {"command": "first"},
            "Second": {"command": "second"},
            "Third": {"command": "third"},
        }
    }
    dialog, services = _real_manager(commands, monkeypatch)
    item = _tree_item(dialog, "System", "Second")
    dialog._tree.setCurrentItem(item)
    form = _accepted_form(
        {
            "group_path": ("System",),
            "group": "System",
            "label": "Second",
            "command": "updated-second",
            "showOutput": False,
            "confirm": False,
        }
    )
    with patch("ui.command_manager._CommandFormDialog", return_value=form):
        dialog._edit_command()

    assert list(commands["System"]) == ["First", "Second", "Third"]
    assert commands["System"]["Second"]["command"] == "updated-second"
    services.config_manager.save_commands.assert_called_once_with(commands)


def test_same_group_rename_preserves_original_menu_position(monkeypatch):
    commands = {
        "System": {
            "First": {"command": "first"},
            "Second": {"command": "second"},
            "Third": {"command": "third"},
        }
    }
    dialog, services = _real_manager(commands, monkeypatch)
    item = _tree_item(dialog, "System", "Second")
    dialog._tree.setCurrentItem(item)
    form = _accepted_form(
        {
            "group_path": ("System",),
            "group": "System",
            "label": "Renamed",
            "command": "second",
            "showOutput": False,
            "confirm": False,
        }
    )
    with patch("ui.command_manager._CommandFormDialog", return_value=form):
        dialog._edit_command()

    assert list(commands["System"]) == ["First", "Renamed", "Third"]
    services.config_manager.save_commands.assert_called_once_with(commands)


def test_edit_nested_command_to_other_path_preserves_siblings(monkeypatch):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, monkeypatch)
    _select_nested_command(dialog)
    form = _accepted_form(
        {
            "group_path": ("Utilities",),
            "group": "Utilities",
            "label": "Terminal New",
            "command": "new-terminal",
            "showOutput": True,
            "confirm": False,
        }
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


def test_delete_nested_command_removes_only_target_and_preserves_subgroups(monkeypatch):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, monkeypatch)
    _select_nested_command(dialog)
    with patch("ui.command_manager.confirm_action", return_value=True):
        dialog._delete_command()

    assert "Terminal" not in commands["System"]["Tools"]
    assert commands["System"]["Tools"]["Editor"] == {"command": "code", "confirm": True}
    assert commands["System"]["Tools"]["Diagnostics"] == {"Logs": {"command": "journalctl"}}
    assert commands["System"]["Tools"]["icon"] == "tools.png"
    assert commands["System"]["Keep"] == {"command": "keep"}
    services.config_manager.save_commands.assert_called_once_with(commands)


def test_delete_nested_command_cancel_keeps_configuration_unchanged(monkeypatch):
    commands = _nested_commands()
    original = {key: value.copy() for key, value in commands.items()}
    dialog, services = _real_manager(commands, monkeypatch)
    _select_nested_command(dialog)
    with patch("ui.command_manager.confirm_action", return_value=False):
        dialog._delete_command()
    assert commands == original
    services.config_manager.save_commands.assert_not_called()


def test_move_nested_commands_reorders_direct_entries_and_preserves_icon_and_siblings(monkeypatch):
    commands = _nested_commands()
    dialog, services = _real_manager(commands, monkeypatch)
    _select_nested_command(dialog, "Editor")
    dialog._move_up()
    assert list(commands["System"]["Tools"]) == ["icon", "Editor", "Terminal", "Diagnostics"]
    assert commands["System"]["Tools"]["icon"] == "tools.png"
    assert commands["System"]["Tools"]["Editor"] == {"command": "code", "confirm": True}
    assert commands["System"]["Keep"] == {"command": "keep"}

    _select_nested_command(dialog, "Editor")
    dialog._move_down()
    assert list(commands["System"]["Tools"]) == ["icon", "Terminal", "Editor", "Diagnostics"]
    assert commands["System"]["Tools"]["Terminal"]["command"] == "gnome-terminal --window"
    assert commands["System"]["icon"] == "system.png"
    assert services.config_manager.save_commands.call_count == 2


def test_typed_group_name_with_dot_remains_one_top_level_component(monkeypatch):
    commands = _nested_commands()
    dialog, _ = _real_manager(commands, monkeypatch)
    form = _accepted_form(
        {
            "group_path": ("New.Group",),
            "group": "New.Group",
            "label": "Example",
            "command": "example",
        }
    )
    with patch("ui.command_manager._CommandFormDialog", return_value=form):
        dialog._add_command()
    assert commands["New.Group"]["Example"]["command"] == "example"
