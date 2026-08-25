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
from core.menu_builder import MenuBuilder  # noqa: E402


def _stub_icon_file():
    """Return a path that does not exist on disk (used as icon_file fallback)."""
    return "/nonexistent/tray_icon.png"


def _make_tray_app(command_menu=None):
    """Build a minimal tray_app stub that MenuBuilder methods touch."""
    tray_app = MagicMock()
    tray_app.icon_file = _stub_icon_file()
    tray_app.command_menu = command_menu if command_menu is not None else {}
    tray_app.favorites = MagicMock()
    tray_app.favorites_menu = None
    tray_app.history_menu = None
    tray_app.palette = MagicMock()
    tray_app.palette.show_palette = MagicMock()
    tray_app.palette.show_app_launcher = MagicMock()
    tray_app.search = MagicMock()
    tray_app.search.show_dialog = MagicMock()
    tray_app._open_command_manager = MagicMock()
    tray_app.open_commands_json = MagicMock()
    tray_app.reload_history_commands = MagicMock()
    tray_app.reload_favorites_commands = MagicMock()
    tray_app.importExport = MagicMock()
    tray_app.importExport.import_command_group = MagicMock()
    tray_app.importExport.export_command_group = MagicMock()
    tray_app.backup = MagicMock()
    tray_app.backup.backup_commands = MagicMock()
    tray_app.backup.restore_commands = MagicMock()
    tray_app.file_encryptor = MagicMock()
    tray_app.file_encryptor.encrypt_file_or_folder = MagicMock()
    tray_app.file_encryptor.decrypt_file_or_folder = MagicMock()
    tray_app.schedule_creator = MagicMock()
    tray_app.schedule_creator.show_dialog = MagicMock()
    tray_app.schedule_viewer = MagicMock()
    tray_app.schedule_viewer.show_dialog = MagicMock()
    tray_app._open_settings = MagicMock()
    tray_app.quick_launch_bar = MagicMock()
    tray_app.quick_launch_bar.toggle = MagicMock()
    tray_app.restart_app = MagicMock()
    tray_app.confirm_exit = MagicMock()
    tray_app.execute = MagicMock()
    tray_app._pin_to_quick_launch = MagicMock()
    tray_app._resolve_icon_path = MagicMock(return_value=None)
    return tray_app


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
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)
    parent_menu = MagicMock()

    qmenu_make, qmenus = _qmenu_factory()

    with patch("core.menu_builder.QMenu", side_effect=qmenu_make):
        builder.build(parent_menu, command_menu)

    group_a = [m for label, m in qmenus if label == "GroupA"][0]
    group_b = [m for label, m in qmenus if label == "GroupB"][0]

    assert group_a.addAction.call_count == 2
    assert group_b.addAction.call_count == 1


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
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)
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
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)

    result = builder._get_item_icon_path("nonexistent.png", tray_app.icon_file)

    assert result == tray_app.icon_file
    tray_app._resolve_icon_path.assert_called_once_with("nonexistent.png")


# ---------------------------------------------------------------------------
# 4. test_reference_entry_resolves_and_links_to_target_command
# ---------------------------------------------------------------------------


def test_reference_entry_resolves_and_links_to_target_command():
    """A {"ref": "Group.Label"} entry causes _resolve_command_reference to look
    up the target command in tray_app.command_menu and return its data."""
    command_menu = {
        "TargetGroup": {
            "TargetCmd": {"command": "real-cmd", "icon": "real.png"},
        },
        "RefGroup": {
            "RefCmd": {"ref": "TargetGroup.TargetCmd"},
        },
    }
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)

    ref_item = {"ref": "TargetGroup.TargetCmd"}
    resolved = builder._resolve_command_reference("RefGroup", "RefCmd", ref_item)

    assert resolved == {"command": "real-cmd", "icon": "real.png"}


def test_resolve_reference_invalid_path_returns_item():
    """A ref with no dot separator (e.g. "BadRef") returns the item unchanged
    after logging a warning."""
    tray_app = _make_tray_app()
    builder = MenuBuilder(tray_app)

    with patch("core.menu_builder.logger") as mock_logger:
        result = builder._resolve_command_reference("G", "L", {"ref": "BadRef"})

    assert result == {"ref": "BadRef"}
    mock_logger.warning.assert_called_once()


def test_resolve_reference_missing_group_returns_item():
    """A ref to a group that is not in command_menu returns the item unchanged."""
    command_menu = {"OtherGroup": {"X": {"command": "x"}}}
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)

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
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)

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
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)

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
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)
    menu = MagicMock()

    action = builder._add_command_to_menu(
        menu, "RefItem", {"ref": "Target.Real"}, tray_app.icon_file, "RefGroup"
    )

    assert action is not None
    assert menu.addAction.called
    tray_app.execute.assert_not_called()


def test_add_command_to_menu_missing_command_raises():
    """An item with no 'command' and no 'ref' causes show_error_and_raise to be
    called with a message containing the label."""
    tray_app = _make_tray_app()
    builder = MenuBuilder(tray_app)
    menu = MagicMock()

    with patch("core.menu_builder.show_error_and_raise") as mock_error:
        try:
            builder._add_command_to_menu(menu, "BadItem", {"icon": "x.png"}, tray_app.icon_file)
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
    tray_app = _make_tray_app()
    builder = MenuBuilder(tray_app)
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
    tray_app = _make_tray_app(command_menu)
    builder = MenuBuilder(tray_app)
    parent_menu = MagicMock()

    with patch("core.menu_builder.show_error_and_raise") as mock_error:
        try:
            builder.build(parent_menu, command_menu)
        except Exception:
            pass

    mock_error.assert_called_once()
    assert "BadGroup" in mock_error.call_args[0][0]
    assert "dictionary" in mock_error.call_args[0][0].lower()
