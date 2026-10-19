# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for MenuBuilder — hierarchical menu construction, icon fallback, and reference resolution.

PyQt6 is stubbed in conftest.py (sys.modules injection) so these tests run
headlessly without a QApplication. The conftest stub supplies QMenu, QAction,
and QIcon with the chainable surface MenuBuilder accesses (construct, setIcon,
addAction, addMenu, triggered.connect, setMenu).
"""

from unittest.mock import MagicMock, patch

# The PyQt6 stub is already injected by conftest.py. Import MenuBuilder
# after the stub is in place — the src/ path is on sys.path via conftest.py.
from core.menu_builder import (  # noqa: E402  # after conftest installs Qt stub
    MenuBuilder,
    MenuBuilderDependencies,
)


def _stub_icon_file():
    """Return a path that does not exist on disk (used as icon_file fallback)."""
    return "/nonexistent/tray_icon.png"


def _make_dependencies(command_menu=None):
    """Build only the rendering inputs and callbacks declared by MenuBuilder."""

    def feature():
        return MagicMock()

    callbacks = {
        "icon_file": _stub_icon_file(),
        "get_command_menu": MagicMock(return_value=command_menu or {}),
        "resolve_icon_path": MagicMock(return_value=None),
        "execute": MagicMock(),
        "pin_to_quick_launch": MagicMock(),
        "get_favorites": MagicMock(return_value=feature()),
        "set_favorites_menu": MagicMock(),
        "reload_favorites_commands": MagicMock(),
        "set_history_menu": MagicMock(),
        "reload_history_commands": MagicMock(),
        "get_palette": MagicMock(return_value=feature()),
        "get_search": MagicMock(return_value=feature()),
        "open_command_manager": MagicMock(),
        "open_commands_json": MagicMock(),
        "reload_commands": MagicMock(),
        "get_import_export": MagicMock(return_value=feature()),
        "get_backup": MagicMock(return_value=feature()),
        "get_file_encryptor": MagicMock(return_value=feature()),
        "get_schedule_creator": MagicMock(return_value=feature()),
        "get_schedule_viewer": MagicMock(return_value=feature()),
        "open_settings": MagicMock(),
        "get_quick_launch_bar": MagicMock(return_value=feature()),
        "set_running_action": MagicMock(),
        "restart_app": MagicMock(),
        "confirm_exit": MagicMock(),
    }
    return MenuBuilderDependencies(**callbacks)


def _qmenu_factory():
    """Return a factory that creates trackable QMenu stubs.

    Each created menu is a MagicMock whose addAction and addMenu are also
    MagicMocks, so the test can assert on call counts.
    """
    menus = []

    def make(*args, **kwargs):
        m = MagicMock()
        m.addAction = MagicMock()
        m.addMenu = MagicMock()
        m.setIcon = MagicMock()
        menus.append((args[0] if args else "", m))
        return m

    return make, menus


def test_builder_uses_only_its_typed_dependency_contract():
    """The builder retains its dependency object, never an application object."""
    dependencies = _make_dependencies()
    builder = MenuBuilder(dependencies)

    assert builder.dependencies is dependencies
    assert not hasattr(builder, "tray_app")


# ---------------------------------------------------------------------------
# 1. test_build_flat_groups_creates_one_submenu_per_group
# ---------------------------------------------------------------------------


def test_build_flat_groups_creates_one_submenu_per_group():
    """A flat command dict with two groups yields two QMenu submenus, each
    populated with QAction entries for the commands in that group."""
    command_menu = {
        "GroupA": {
            "Cmd1": {"command": "echo one"},
            "Cmd2": {"command": "echo two"},
        },
        "GroupB": {
            "Cmd3": {"command": "echo three"},
        },
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)
    parent_menu = MagicMock()

    qmenu_make, qmenus = _qmenu_factory()

    with patch("core.menu_builder.QMenu", side_effect=qmenu_make):
        builder.build(parent_menu, command_menu)

    group_a = [m for label, m in qmenus if label == "GroupA"][0]
    group_b = [m for label, m in qmenus if label == "GroupB"][0]

    assert group_a.addAction.call_count == 2
    assert group_b.addAction.call_count == 1


def test_build_passes_root_group_name_to_command_actions():
    """Commands rendered from a root category retain that category as context."""
    command_menu = {"System": {"Terminal": {"command": "xterm"}}}
    builder = MenuBuilder(_make_dependencies(command_menu))
    parent_menu = MagicMock()
    qmenu_make, _ = _qmenu_factory()

    with (
        patch("core.menu_builder.QMenu", side_effect=qmenu_make),
        patch.object(builder, "_add_command_to_menu") as add_command,
    ):
        builder.build(parent_menu, command_menu)

    assert add_command.call_args.args[4] == "System"


# ---------------------------------------------------------------------------
# 2. test_nested_groups_recurse_correctly
# ---------------------------------------------------------------------------


def test_nested_groups_recurse_correctly():
    """A group containing a nested sub-dictionary (no command, no ref) produces
    a submenu whose own submenu is recursively populated; the nested label
    appears in the hierarchy."""
    command_menu = {
        "Parent": {
            "Nested": {
                "Leaf": {"command": "leaf-cmd"},
            },
        },
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)
    parent_menu = MagicMock()

    qmenu_make, qmenus = _qmenu_factory()

    with patch("core.menu_builder.QMenu", side_effect=qmenu_make):
        builder.build(parent_menu, command_menu)

    parent_submenu = [m for label, m in qmenus if label == "Parent"][0]
    nested_submenu = [m for label, m in qmenus if label == "Nested"][0]

    assert parent_submenu.addAction.call_count == 0
    assert parent_submenu.addMenu.call_count == 1
    assert nested_submenu.addAction.call_count == 1


# ---------------------------------------------------------------------------
# 3. test_unknown_icon_path_falls_back_to_tray_icon
# ---------------------------------------------------------------------------


def test_unknown_icon_path_falls_back_to_tray_icon():
    """When _get_item_icon_path receives an icon spec whose resolved path does
    not exist on disk, it returns the fallback_path (the tray icon path)
    instead of the non-existent spec."""
    command_menu = {
        "Group": {
            "Cmd": {"command": "echo x", "icon": "nonexistent.png"},
        },
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)

    result = builder._get_item_icon_path("nonexistent.png", dependencies.icon_file)

    assert result == dependencies.icon_file
    dependencies.resolve_icon_path.assert_called_once_with("nonexistent.png")


# ---------------------------------------------------------------------------
# 4. test_reference_entry_resolves_and_links_to_target_command
# ---------------------------------------------------------------------------


def test_reference_entry_resolves_and_links_to_target_command():
    """A {"ref": "Group.Label"} entry causes _resolve_command_reference to look
    up the target command in dependencies.command_menu and return its data."""
    command_menu = {
        "TargetGroup": {
            "TargetCmd": {"command": "real-cmd", "icon": "real.png"},
        },
        "RefGroup": {
            "RefCmd": {"ref": "TargetGroup.TargetCmd"},
        },
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)

    ref_item = {"ref": "TargetGroup.TargetCmd"}
    resolved = builder._resolve_command_reference("RefGroup", "RefCmd", ref_item)

    assert resolved == {"command": "real-cmd", "icon": "real.png"}


def test_resolve_reference_invalid_path_returns_item():
    """A ref with no dot separator (e.g. "BadRef") returns the item unchanged
    after logging a warning."""
    dependencies = _make_dependencies()
    builder = MenuBuilder(dependencies)

    with patch("core.menu_builder.logger") as mock_logger:
        result = builder._resolve_command_reference("G", "L", {"ref": "BadRef"})

    assert result == {"ref": "BadRef"}
    mock_logger.warning.assert_called_once()


def test_resolve_reference_missing_group_returns_item():
    """A ref to a group that is not in command_menu returns the item unchanged."""
    command_menu = {"OtherGroup": {"X": {"command": "x"}}}
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)

    with patch("core.menu_builder.logger") as mock_logger:
        result = builder._resolve_command_reference("G", "L", {"ref": "MissingGroup.Target"})

    assert result == {"ref": "MissingGroup.Target"}
    mock_logger.warning.assert_called_once()


def test_resolve_reference_nested_path_resolves():
    """A ref with 3+ parts (Group.Sub.SubCmd) traverses the nested dict and
    returns the resolved leaf command."""
    command_menu = {
        "G": {
            "Sub": {
                "Leaf": {"command": "deep-cmd"},
            },
        },
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)

    resolved = builder._resolve_command_reference("G", "L", {"ref": "G.Sub.Leaf"})

    assert resolved == {"command": "deep-cmd"}


def test_resolve_reference_invalid_target_returns_item():
    """A ref pointing to a non-command dict (no 'command' key) returns the
    original item after logging a warning."""
    command_menu = {
        "G": {
            "Bad": {"icon": "x.png"},
        },
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)

    with patch("core.menu_builder.logger") as mock_logger:
        result = builder._resolve_command_reference("G", "L", {"ref": "G.Bad"})

    assert result == {"ref": "G.Bad"}
    mock_logger.warning.assert_called_once()


def test_add_command_to_menu_reference_resolves_command():
    """When a command item has a 'ref', _add_command_to_menu resolves it and
    uses the resolved command string for the action."""
    command_menu = {
        "Target": {
            "Real": {"command": "real-exec", "icon": "real.png"},
        },
        "RefGroup": {
            "RefItem": {"ref": "Target.Real"},
        },
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)
    menu = MagicMock()

    action = builder._add_command_to_menu(
        menu, "RefItem", {"ref": "Target.Real"}, dependencies.icon_file, "RefGroup"
    )

    assert action is not None
    assert menu.addAction.called
    dependencies.execute.assert_not_called()


def test_command_and_pin_actions_use_injected_callbacks():
    """Rendered command actions and context-menu actions call injected handlers."""
    dependencies = _make_dependencies()
    builder = MenuBuilder(dependencies)
    menu = MagicMock()

    class _Signal:
        def connect(self, callback):
            self.callback = callback

        def emit(self):
            self.callback()

    class _Action:
        def __init__(self, *_args):
            self.triggered = _Signal()

        def setMenu(self, context_menu):
            self.context_menu = context_menu

    command_action = _Action()
    pin_action = _Action()
    with (
        patch("core.menu_builder.QAction", side_effect=[command_action, pin_action]),
        patch("core.menu_builder.QMenu", return_value=MagicMock()),
    ):
        builder._add_command_to_menu(
            menu,
            "Terminal",
            {"command": "xterm", "confirm": True, "showOutput": True},
            dependencies.icon_file,
            "System",
        )

    command_action.triggered.emit()
    pin_action.triggered.emit()

    dependencies.execute.assert_called_once_with("Terminal", "xterm", True, True, None)
    dependencies.pin_to_quick_launch.assert_called_once_with(
        {
            "group": "System",
            "label": "Terminal",
            "command": "xterm",
            "confirm": True,
            "showOutput": True,
            "prompt": None,
        }
    )


def test_add_command_to_menu_missing_command_raises():
    """An item with no 'command' and no 'ref' causes show_error_and_raise to be
    called with a message containing the label."""
    dependencies = _make_dependencies()
    builder = MenuBuilder(dependencies)
    menu = MagicMock()

    with patch("core.menu_builder.show_error_and_raise") as mock_error:
        try:
            builder._add_command_to_menu(menu, "BadItem", {"icon": "x.png"}, dependencies.icon_file)
        except Exception:
            pass

    mock_error.assert_called_once()
    assert "BadItem" in mock_error.call_args[0][0]
    assert "command" in mock_error.call_args[0][0]


# ---------------------------------------------------------------------------
# 5. test_build_raises_when_root_is_not_dict
# ---------------------------------------------------------------------------


def test_build_raises_when_root_is_not_dict():
    """Passing a non-dict root to build() causes show_error_and_raise to be
    called exactly once with the expected message."""
    dependencies = _make_dependencies()
    builder = MenuBuilder(dependencies)
    parent_menu = MagicMock()

    with patch("core.menu_builder.show_error_and_raise") as mock_error:
        try:
            builder.build(parent_menu, "not-a-dict")
        except Exception:
            pass

    mock_error.assert_called_once()
    assert (
        mock_error.call_args[0][0]
        == "Invalid commands configuration. Root element must be a dictionary."
    )


# ---------------------------------------------------------------------------
# 6. test_build_raises_when_group_value_is_not_dict
# ---------------------------------------------------------------------------


def test_build_raises_when_group_value_is_not_dict():
    """A group whose value is a non-dict (e.g. a string) causes
    show_error_and_raise to be called exactly once with a message containing
    the group name."""
    command_menu = {
        "BadGroup": "not-a-dict",
    }
    dependencies = _make_dependencies(command_menu)
    builder = MenuBuilder(dependencies)
    parent_menu = MagicMock()

    with patch("core.menu_builder.show_error_and_raise") as mock_error:
        try:
            builder.build(parent_menu, command_menu)
        except Exception:
            pass

    mock_error.assert_called_once()
    assert "BadGroup" in mock_error.call_args[0][0]
    assert "dictionary" in mock_error.call_args[0][0].lower()


def test_build_uses_lazy_quick_launch_bar_accessor():
    """Regression: the tray menu must obtain the Quick Launch Bar through the
    lazy accessor. Dereferencing the unset ``quick_launch_bar`` slot raised
    AttributeError inside the aboutToShow slot, which aborts the process."""
    dependencies = _make_dependencies({"GroupA": {"Cmd1": {"command": "echo one"}}})
    parent_menu = MagicMock()
    qmenu_make, _ = _qmenu_factory()

    with patch("core.menu_builder.QMenu", side_effect=qmenu_make):
        MenuBuilder(dependencies).build(parent_menu, dependencies.get_command_menu.return_value)

    dependencies.get_quick_launch_bar.assert_called_once_with()
    labels = [c.args[0] for c in parent_menu.addAction.call_args_list if c.args]
    assert "Quick Launch Bar" in labels


def test_build_invalidates_cached_command_search_results():
    from modules.command_search import (
        clear_command_search_cache,
        command_search_cache_info,
        search_commands,
    )

    commands = [{"group": "Group", "label": "Terminal", "command": "terminal"}]
    clear_command_search_cache()
    search_commands("terminal", commands)
    assert command_search_cache_info().currsize == 1

    dependencies = _make_dependencies({"Group": {"Terminal": {"command": "terminal"}}})
    parent_menu = MagicMock()
    qmenu_make, _ = _qmenu_factory()

    with patch("core.menu_builder.QMenu", side_effect=qmenu_make):
        MenuBuilder(dependencies).build(parent_menu, dependencies.get_command_menu.return_value)

    assert command_search_cache_info().currsize == 0
