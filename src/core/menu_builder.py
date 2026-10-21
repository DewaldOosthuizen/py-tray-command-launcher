# SPDX-License-Identifier: GPL-3.0-or-later

"""MenuBuilder: Encapsulates all menu construction logic for TrayApp.

This module provides the MenuBuilder class that handles hierarchical menu
building, command resolution, and icon resolution. It decouples menu
construction from the main TrayApp class, reducing complexity and improving
testability.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMenu

from modules.command_search import clear_command_search_cache
from utils.dialogs import show_error_and_raise
from utils.execution_cues import describe_execution_cues, format_execution_cues

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from modules.backup_restore import BackupRestore
    from modules.favorites import Favorites
    from modules.file_encryptor import FileEncryptor
    from modules.import_export import ImportExport
    from modules.schedule_creator import ScheduleCreator
    from modules.schedule_viewer import ScheduleViewer
    from ui.command_palette import CommandPalette
    from ui.quick_launch_bar import QuickLaunchBar


def _command_action_label(label: str, command: dict[str, Any]) -> str:
    """Render a configured command name with any conditional execution cues."""
    cues = format_execution_cues(command, concise=True)
    return f"{label} · {cues}" if cues else label


def _set_command_action_help(action: QAction, command: dict[str, Any]) -> None:
    """Expose detailed execution cues as supplemental native-action help."""
    description = describe_execution_cues(command)
    if description:
        action.setToolTip(description)
        action.setWhatsThis(description)


@dataclass(frozen=True)
class MenuBuilderDependencies:
    """Typed rendering data and callbacks required to assemble tray actions."""

    icon_file: str
    get_command_menu: Callable[[], dict[str, Any]]
    resolve_icon_path: Callable[[Any], str | None]
    execute: Callable[[str, str, bool, bool, str | None], None]
    pin_to_quick_launch: Callable[[dict[str, Any]], None]
    get_favorites: Callable[[], Favorites]
    set_favorites_menu: Callable[[QMenu], None]
    reload_favorites_commands: Callable[[], None]
    set_history_menu: Callable[[QMenu], None]
    reload_history_commands: Callable[[], None]
    get_palette: Callable[[], CommandPalette]
    open_command_manager: Callable[[], None]
    open_commands_json: Callable[[], None]
    reload_commands: Callable[..., None]
    get_import_export: Callable[[], ImportExport]
    get_backup: Callable[[], BackupRestore]
    get_file_encryptor: Callable[[], FileEncryptor]
    get_schedule_creator: Callable[[], ScheduleCreator]
    get_schedule_viewer: Callable[[], ScheduleViewer]
    open_settings: Callable[[], None]
    get_quick_launch_bar: Callable[[], QuickLaunchBar]
    set_running_action: Callable[[QAction], None]
    restart_app: Callable[[], None]
    confirm_exit: Callable[[], None]


class MenuBuilder:
    """Encapsulates menu building logic for the tray application.

    Responsibilities:
    - Build hierarchical menus from command configuration
    - Resolve command references
    - Handle icon resolution and fallback
    - Create menu actions with proper signal connections
    """

    def __init__(self, dependencies: MenuBuilderDependencies) -> None:
        """Initialize the builder with its narrow rendering contract.

        Args:
            dependencies: Data providers and action callbacks used for rendering.
        """
        self.dependencies = dependencies

    def build(self, menu, command_menu):
        """Build the complete tray menu from command configuration.

        Args:
            menu: The QMenu to add items to
            command_menu: Dictionary of commands from config

        Raises:
            ValueError: If the command root, a group, or a command definition is invalid.
        """
        clear_command_search_cache()

        # Check if commands is a dictionary
        if not isinstance(command_menu, dict):
            show_error_and_raise(
                "Invalid commands configuration. Root element must be a dictionary."
            )

        menu.addAction("Command Palette", self.dependencies.get_palette().show_palette)

        # Add favorites menu
        favorites_menu = QMenu("Favorites", menu)
        favorites_menu.setIcon(QIcon(self.dependencies.icon_file))
        self.dependencies.get_favorites().populate_favorites_menu(favorites_menu)
        self.dependencies.set_favorites_menu(favorites_menu)
        menu.addMenu(favorites_menu)

        # Add history menu
        history_menu = QMenu("Recent Commands", menu)
        history_menu.setIcon(QIcon(self.dependencies.icon_file))
        menu.addMenu(history_menu)
        self.dependencies.set_history_menu(history_menu)
        self.dependencies.reload_history_commands()
        self.dependencies.reload_favorites_commands()

        menu.addSeparator()

        # User-defined category submenus retain their configured hierarchy.
        for group, items in command_menu.items():
            if not isinstance(items, dict):
                show_error_and_raise(
                    f"Invalid command group format: {group}. Each group must be a dictionary."
                )
            icon_path = self._get_item_icon_path(items.get("icon"), self.dependencies.icon_file)
            submenu = QMenu(group, menu)
            submenu.setIcon(QIcon(icon_path))
            self._add_menu_items(submenu, items, icon_path, group)
            menu.addMenu(submenu)

        menu.addSeparator()

        management_menu = QMenu("Management", menu)
        management_menu.setIcon(QIcon(self.dependencies.icon_file))
        management_menu.addAction("Manage Commands", self.dependencies.open_command_manager)
        management_menu.addAction("Edit commands file", self.dependencies.open_commands_json)
        management_menu.addAction(
            "Reload Commands", lambda: self.dependencies.reload_commands(rebuild_menu=True)
        )
        management_menu.addAction(
            "Reload History Commands", self.dependencies.reload_history_commands
        )
        management_menu.addAction(
            "Add to Favorites", self.dependencies.get_favorites().add_to_favorites
        )
        management_menu.addAction("Restart App", self.dependencies.restart_app)
        menu.addMenu(management_menu)

        # Tools group
        tools_menu = QMenu("Tools", menu)
        tools_menu.setIcon(QIcon(self.dependencies.icon_file))

        # Import/Export submenu
        import_export_menu = QMenu("Import/Export", tools_menu)
        import_export_menu.setIcon(QIcon(self.dependencies.icon_file))
        import_export_menu.addAction(
            "Import Command Group", self.dependencies.get_import_export().import_command_group
        )
        import_export_menu.addAction(
            "Export Command Group", self.dependencies.get_import_export().export_command_group
        )
        tools_menu.addMenu(import_export_menu)

        # Backup/Restore submenu
        backup_restore_menu = QMenu("Backup/Restore", tools_menu)
        backup_restore_menu.setIcon(QIcon(self.dependencies.icon_file))
        backup_restore_menu.addAction(
            "Backup Commands", self.dependencies.get_backup().backup_commands
        )
        backup_restore_menu.addAction(
            "Restore Commands", self.dependencies.get_backup().restore_commands
        )
        tools_menu.addMenu(backup_restore_menu)

        # Encryption submenu
        encryption_menu = QMenu("Encrypt/Decrypt", tools_menu)
        encryption_menu.setIcon(QIcon(self.dependencies.icon_file))
        encryption_menu.addAction(
            "Encrypt File/Folder", self.dependencies.get_file_encryptor().encrypt_file_or_folder
        )
        encryption_menu.addAction(
            "Decrypt File/Folder", self.dependencies.get_file_encryptor().decrypt_file_or_folder
        )
        tools_menu.addMenu(encryption_menu)

        # Add Create Schedule option
        tools_menu.addAction(
            "Create Schedule", self.dependencies.get_schedule_creator().show_dialog
        )

        # Add View Schedules option
        tools_menu.addAction("View Schedules", self.dependencies.get_schedule_viewer().show_dialog)

        menu.addMenu(tools_menu)
        menu.addAction("Quick Launch Bar", self.dependencies.get_quick_launch_bar().toggle)
        menu.addAction("Settings", self.dependencies.open_settings)

        # Dynamic "Running: N" indicator (non-interactive, hidden when idle)
        running_action = QAction("Running: 0", menu)
        running_action.setEnabled(False)
        running_action.setVisible(False)
        self.dependencies.set_running_action(running_action)
        menu.addAction(running_action)

        menu.addAction("Exit", self.dependencies.confirm_exit)

    def _add_menu_items(self, menu, items, parent_icon_path, group_name=""):
        """Recursively add items to the menu.

        Args:
            menu: The QMenu to add items to
            items: Dictionary of menu items
            parent_icon_path: Path to parent icon for fallback
            group_name: Hierarchical name of the current group
        """
        for label, item in items.items():
            # Skip the icon entry
            if label == "icon":
                continue

            # Handle submenu case (nested dictionaries without command and not a reference)
            if isinstance(item, dict) and "command" not in item and "ref" not in item:
                # Create submenu for nested dictionaries
                icon_path = self._get_item_icon_path(item.get("icon"), parent_icon_path)

                submenu = QMenu(label, menu)
                submenu.setIcon(QIcon(icon_path))
                new_group = label if not group_name else f"{group_name} → {label}"
                self._add_menu_items(submenu, item, icon_path, new_group)
                menu.addMenu(submenu)

            # Handle command case (direct commands or references)
            elif isinstance(item, dict) and ("command" in item or "ref" in item):
                # Add command item to menu
                self._add_command_to_menu(menu, label, item, parent_icon_path, group_name)

    def resolve_command_reference(self, group, label, item):
        """Resolve a referenced command for favorite and shortcut rendering.

        Args:
            group: Display group containing the reference.
            label: Reference label.
            item: Reference definition.

        Returns:
            The referenced command definition or the original item when invalid.
        """
        return self._resolve_command_reference(group, label, item)

    def _resolve_command_reference(self, group, label, item):
        """Resolve a command reference to get the actual command data.

        Args:
            group: The group name (e.g., 'Favorites')
            label: The command label
            item: The command item data

        Returns:
            The resolved command data dictionary
        """
        if isinstance(item, dict) and "ref" in item:
            try:
                # This is a reference, resolve it
                ref_path = item["ref"]
                path_parts = ref_path.split(".")
                if len(path_parts) < 2:
                    logger.warning("Invalid reference path: %s", ref_path)
                    return item

                ref_group = path_parts[0]
                commands = self.dependencies.get_command_menu()

                if ref_group not in commands:
                    logger.warning("Referenced group not found: %s", ref_group)
                    return item

                if len(path_parts) == 2:
                    # Direct command in a group
                    ref_command = path_parts[1]
                    resolved = commands[ref_group].get(ref_command, {})
                else:
                    # Nested command
                    current = commands[ref_group]
                    for part in path_parts[1:-1]:
                        if part not in current:
                            logger.warning("Referenced path part not found: %s", part)
                            return item
                        current = current[part]
                    ref_command = path_parts[-1]
                    resolved = current.get(ref_command, {})

                # Validate the resolved command
                if isinstance(resolved, dict) and "command" in resolved:
                    return resolved
                else:
                    logger.warning("Referenced command is invalid: %s", ref_path)
                    return item
            except Exception as e:
                logger.exception("Error resolving reference: %s", str(e))
                return item

        return item

    def _add_command_to_menu(self, menu, label, item, parent_icon_path, group_name=""):
        """Add a command item to the menu.

        Args:
            menu: The QMenu to add the action to
            label: The label for the menu item
            item: The command configuration dictionary
            parent_icon_path: Path to parent icon for fallback
            group_name: Hierarchical name of the current group

        Returns:
            The created QAction object
        """
        # Check if this is a reference and resolve it
        if isinstance(item, dict) and "ref" in item:
            resolved_item = self._resolve_command_reference(group_name, label, item)
            if resolved_item != item:
                # Use the resolved item but keep track of the reference
                command = resolved_item.get("command", "")
                # If the resolved item has an icon, use it; otherwise inherit from parent
                icon_path = self._get_item_icon_path(resolved_item.get("icon"), parent_icon_path)
                show_output = resolved_item.get("showOutput", False)
                confirm = resolved_item.get("confirm", False)
                prompt = resolved_item.get("prompt", None)

                # Create action with reference indicator
                rendered_label = _command_action_label(label, resolved_item)
                action = QAction(QIcon(icon_path), rendered_label, menu)
                _set_command_action_help(action, resolved_item)

                # Connect the action to execute command
                action.triggered.connect(
                    lambda checked=False, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: (
                        self.dependencies.execute(lbl, cmd, conf, show, prmpt)
                    )
                )

                menu.addAction(action)
                self._attach_pin_context_menu(
                    action,
                    {
                        "group": group_name,
                        "label": label,
                        "command": command,
                        "confirm": confirm,
                        "showOutput": show_output,
                        "prompt": prompt,
                    },
                )
                return action

        # Regular command processing
        command = item.get("command")

        # Validate required fields
        if not command:
            show_error_and_raise(
                f"Invalid command format in commands.json: {label}. 'command' is required."
            )

        # Get icon path with fallback
        icon_path = self._get_item_icon_path(item.get("icon"), parent_icon_path)

        show_output = item.get("showOutput", False)
        confirm = item.get("confirm", False)
        prompt = item.get("prompt", None)
        rendered_label = _command_action_label(label, item)
        action = QAction(QIcon(icon_path), rendered_label, menu)
        _set_command_action_help(action, item)

        # Connect the action to execute command
        action.triggered.connect(
            lambda checked=False, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: (
                self.dependencies.execute(lbl, cmd, conf, show, prmpt)
            )
        )

        menu.addAction(action)
        self._attach_pin_context_menu(
            action,
            {
                "group": group_name,
                "label": label,
                "command": command,
                "confirm": confirm,
                "showOutput": show_output,
                "prompt": prompt,
            },
        )
        return action

    def _attach_pin_context_menu(self, action: QAction, cmd_info: dict) -> None:
        """Attach a right-click context menu with 'Pin to Quick-Launch Bar' to *action*."""
        context_menu = QMenu()
        pin_action = QAction("Pin to Quick-Launch Bar", context_menu)
        pin_action.triggered.connect(partial(self.dependencies.pin_to_quick_launch, cmd_info))
        context_menu.addAction(pin_action)
        action.setMenu(context_menu)

    def _get_item_icon_path(self, icon_spec, fallback_path):
        """Resolve icon path with fallback to parent or default.

        Args:
            icon_spec: Icon path from config (or None)
            fallback_path: Path to use if icon_spec doesn't exist or is None

        Returns:
            Valid icon path (either resolved icon_spec or fallback_path)
        """
        if icon_spec:
            resolved = self.dependencies.resolve_icon_path(icon_spec)
            if resolved and os.path.isfile(resolved):
                return resolved
        return fallback_path
