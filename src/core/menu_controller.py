# SPDX-License-Identifier: GPL-3.0-or-later
"""Coordinates tray-menu construction, reloads, and lazy submenu refreshes."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

    from core.menu_builder import MenuBuilder
    from modules.command_history import CommandHistory
    from modules.favorites import Favorites


class MenuController:
    """Own menu lifecycle while delegating rendering to ``MenuBuilder``."""

    def __init__(
        self,
        menu: QMenu,
        tray_icon: QSystemTrayIcon,
        menu_builder: MenuBuilder,
        get_command_menu: Callable[[], dict],
        reload_command_data: Callable[[], dict],
        update_tooltip: Callable[[], None],
        get_history: Callable[[], CommandHistory],
        get_favorites: Callable[[], Favorites],
    ) -> None:
        """Store collaborators and initialize the deferred-build state.

        Args:
            menu: Tray menu to attach and populate.
            tray_icon: Tray icon that owns and displays ``menu``.
            menu_builder: Renderer that creates menu actions.
            get_command_menu: Read the current command configuration snapshot.
            reload_command_data: Refresh configuration and return the new snapshot.
            update_tooltip: Refresh the tray icon tooltip after reloads.
            get_history: Lazily retrieve the history module for an existing submenu.
            get_favorites: Lazily retrieve favorites for an existing submenu.
        """
        self.menu = menu
        self.tray_icon = tray_icon
        self.menu_builder = menu_builder
        self._get_command_menu = get_command_menu
        self._reload_command_data = reload_command_data
        self._update_tooltip = update_tooltip
        self._get_history = get_history
        self._get_favorites = get_favorites
        self.history_menu: QMenu | None = None
        self.favorites_menu: QMenu | None = None
        self._heavy_menu_built = False
        self._attached = False

    def attach(self) -> None:
        """Attach and show the tray icon, leaving feature construction deferred."""
        self.tray_icon.setContextMenu(self.menu)
        if not self._attached:
            self.menu.aboutToShow.connect(self._build_on_first_show)
            self._attached = True
        self.tray_icon.show()
        print("TRAY_ICON_SHOWN", flush=True)
        self._update_tooltip()

    def _build_on_first_show(self) -> None:
        """Build menu actions once, on first display of the tray menu."""
        if self._heavy_menu_built:
            return
        self.build_menu(self._get_command_menu())

    def build_menu(self, command_menu: dict) -> None:
        """Render a snapshot and complete first-show construction.

        Args:
            command_menu: Commands arranged as groups and command definitions.
        """
        self._heavy_menu_built = True
        self.menu_builder.build(self.menu, command_menu)

    def load_tray_menu(self) -> None:
        """Reload command configuration and render the tray menu immediately."""
        self._reload_command_data()
        self.build_menu(self._get_command_menu())

    def reload_commands(self, rebuild_menu: bool = False) -> dict:
        """Reload command data and optionally replace the rendered menu.

        Args:
            rebuild_menu: Whether to replace the current menu contents now.

        Returns:
            The current command configuration snapshot.

        Raises:
            ValueError: If the configured command data cannot be loaded and the
                injected reload operation raises that error.
        """
        command_menu = self._reload_command_data()
        if rebuild_menu:
            self.menu.clear()
            self.build_menu(command_menu)
            self.tray_icon.setContextMenu(self.menu)
            self._update_tooltip()
        return command_menu

    def set_history_menu(self, menu: QMenu) -> None:
        """Store the history submenu created by the renderer.

        Args:
            menu: Recently-used commands submenu.
        """
        self.history_menu = menu

    def set_favorites_menu(self, menu: QMenu) -> None:
        """Store the favorites submenu created by the renderer.

        Args:
            menu: Favorites submenu.
        """
        self.favorites_menu = menu

    def reload_history_commands(self) -> None:
        """Refresh history only after its lazy submenu has been rendered."""
        if self.history_menu is not None:
            self._get_history().populate_menu(self.history_menu)

    def reload_favorites_commands(self) -> None:
        """Refresh favorites only after its lazy submenu has been rendered."""
        if self.favorites_menu is None:
            return
        self.favorites_menu.clear()
        self._get_favorites().populate_favorites_menu(self.favorites_menu)

    def resolve_command_reference(self, group: str, label: str, item: dict) -> dict:
        """Resolve a reference using the builder's command-data contract.

        Args:
            group: Display group containing the reference.
            label: Reference label.
            item: Reference definition.

        Returns:
            Resolved command data, or the unchanged item if unresolved.
        """
        return self.menu_builder.resolve_command_reference(group, label, item)
