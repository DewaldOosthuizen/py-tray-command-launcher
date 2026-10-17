# SPDX-License-Identifier: GPL-3.0-or-later
"""Isolated tests for tray menu lifecycle coordination."""

from unittest.mock import MagicMock

from core.menu_controller import MenuController


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self):
        for slot in self.slots:
            slot()


def _controller():
    menu = MagicMock()
    menu.aboutToShow = _Signal()
    tray_icon = MagicMock()
    builder = MagicMock()
    command_data = {"System": {"Terminal": {"command": "xterm"}}}
    reload_data = MagicMock(return_value=command_data)
    controller = MenuController(
        menu=menu,
        tray_icon=tray_icon,
        menu_builder=builder,
        get_command_menu=lambda: command_data,
        reload_command_data=reload_data,
        update_tooltip=MagicMock(),
        get_history=MagicMock(),
        get_favorites=MagicMock(),
    )
    return controller, menu, tray_icon, builder, command_data, reload_data


def test_first_show_builds_menu_and_subsequent_shows_are_idempotent():
    controller, menu, tray_icon, builder, commands, reload_data = _controller()
    controller.attach()

    assert builder.build.call_count == 0
    menu.aboutToShow.emit()
    menu.aboutToShow.emit()

    builder.build.assert_called_once_with(menu, commands)
    reload_data.assert_not_called()
    tray_icon.setContextMenu.assert_called_once_with(menu)


def test_explicit_reload_rebuilds_attached_menu():
    controller, menu, _, builder, commands, reload_data = _controller()
    controller.attach()
    menu.aboutToShow.emit()
    replacement = {"Tools": {"Editor": {"command": "vim"}}}
    reload_data.return_value = replacement

    controller.reload_commands(rebuild_menu=True)

    reload_data.assert_called_with()
    assert builder.build.call_count == 2
    builder.build.assert_called_with(menu, replacement)
    menu.clear.assert_called_once_with()


def test_history_and_favorites_refresh_only_when_their_menus_exist():
    controller, _, _, _, _, _ = _controller()
    history = MagicMock()
    favorites = MagicMock()
    controller._get_history = MagicMock(return_value=history)
    controller._get_favorites = MagicMock(return_value=favorites)

    controller.reload_history_commands()
    controller.reload_favorites_commands()
    history.populate_menu.assert_not_called()
    favorites.populate_favorites_menu.assert_not_called()

    controller.history_menu = MagicMock()
    controller.favorites_menu = MagicMock()
    controller.reload_history_commands()
    controller.reload_favorites_commands()

    history.populate_menu.assert_called_once_with(controller.history_menu)
    controller.favorites_menu.clear.assert_called_once_with()
    favorites.populate_favorites_menu.assert_called_once_with(controller.favorites_menu)


def test_load_tray_menu_builds_immediately_and_marks_first_show_complete():
    controller, menu, _, builder, commands, _ = _controller()

    controller.load_tray_menu()
    menu.aboutToShow.emit()

    builder.build.assert_called_once_with(menu, commands)
