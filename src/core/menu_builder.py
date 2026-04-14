#  SPDX-License-Identifier: GPL-3.0-or-later

"""MenuBuilder: Encapsulates all menu construction logic for TrayApp.

This module provides the MenuBuilder class that handles hierarchical menu
building, command resolution, and icon resolution. It decouples menu
construction from the main TrayApp class, reducing complexity and improving
testability.
"""

import logging
import os
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QIcon, QAction

from utils.dialogs import show_error_and_raise

logger = logging.getLogger(__name__)


class MenuBuilder:
    """Encapsulates menu building logic for the tray application.
    
    Responsibilities:
    - Build hierarchical menus from command configuration
    - Resolve command references
    - Handle icon resolution and fallback
    - Create menu actions with proper signal connections
    """

    def __init__(self, tray_app):
        """Initialize MenuBuilder with reference to parent TrayApp.
        
        Args:
            tray_app: The parent TrayApp instance providing context and methods
        """
        self.tray_app = tray_app

    def build(self, menu, command_menu):
        """Build the complete tray menu from command configuration.
        
        Args:
            menu: The QMenu to add items to
            command_menu: Dictionary of commands from config
        """
        # Check if commands is a dictionary
        if not isinstance(command_menu, dict):
            show_error_and_raise(
                "Invalid commands configuration. Root element must be a dictionary."
            )

        # Iterate over the commands and create menu items
        for group, items in command_menu.items():
            # Check if each group is a dictionary
            if not isinstance(items, dict):
                show_error_and_raise(
                    f"Invalid command group format: {group}. Each group must be a dictionary."
                )

            # Resolve the icon path correctly
            icon_path = self._get_item_icon_path(
                items.get("icon"), self.tray_app.icon_file
            )

            # Create a submenu for each group
            submenu = QMenu(group, menu)
            submenu.setIcon(QIcon(icon_path))

            # Recursively add items to the submenu
            self._add_menu_items(submenu, items, icon_path)

            menu.addMenu(submenu)

        # Add favorites menu
        favorites_menu = QMenu("Favorites", menu)
        favorites_menu.setIcon(QIcon(self.tray_app.icon_file))
        self.tray_app.favorites.populate_favorites_menu(favorites_menu)
        self.tray_app.favorites_menu = favorites_menu
        menu.addMenu(favorites_menu)

        # Add history menu
        history_menu = QMenu("Recent Commands", menu)
        history_menu.setIcon(QIcon(self.tray_app.icon_file))
        menu.addMenu(history_menu)
        self.tray_app.history_menu = history_menu
        self.tray_app.reload_history_commands()
        self.tray_app.reload_favorites_commands()

        menu.addSeparator()

        # Commands group
        commands_menu = QMenu("Commands", menu)
        commands_menu.setIcon(QIcon(self.tray_app.icon_file))
        commands_menu.addAction("Quick Launch (Palette)", self.tray_app.palette.show_palette)
        commands_menu.addAction("Search Commands", self.tray_app.search.show_dialog)
        commands_menu.addAction("Manage Commands", self.tray_app._open_command_manager)
        commands_menu.addAction("Edit commands file", self.tray_app.open_commands_json)
        commands_menu.addAction(
            "Reload Commands", lambda: self.tray_app.reload_commands(rebuild_menu=True)
        )
        commands_menu.addAction("Reload History Commands", self.tray_app.reload_history_commands)
        commands_menu.addAction("Add to Favorites", self.tray_app.favorites.add_to_favorites)
        menu.addMenu(commands_menu)

        # Tools group
        tools_menu = QMenu("Tools", menu)
        tools_menu.setIcon(QIcon(self.tray_app.icon_file))

        # Import/Export submenu
        import_export_menu = QMenu("Import/Export", tools_menu)
        import_export_menu.setIcon(QIcon(self.tray_app.icon_file))
        import_export_menu.addAction(
            "Import Command Group", self.tray_app.importExport.import_command_group
        )
        import_export_menu.addAction(
            "Export Command Group", self.tray_app.importExport.export_command_group
        )
        tools_menu.addMenu(import_export_menu)

        # Backup/Restore submenu
        backup_restore_menu = QMenu("Backup/Restore", tools_menu)
        backup_restore_menu.setIcon(QIcon(self.tray_app.icon_file))
        backup_restore_menu.addAction("Backup Commands", self.tray_app.backup.backup_commands)
        backup_restore_menu.addAction("Restore Commands", self.tray_app.backup.restore_commands)
        tools_menu.addMenu(backup_restore_menu)

        # Encryption submenu
        encryption_menu = QMenu("Encrypt/Decrypt", tools_menu)
        encryption_menu.setIcon(QIcon(self.tray_app.icon_file))
        encryption_menu.addAction(
            "Encrypt File/Folder", self.tray_app.file_encryptor.encrypt_file_or_folder
        )
        encryption_menu.addAction(
            "Decrypt File/Folder", self.tray_app.file_encryptor.decrypt_file_or_folder
        )
        tools_menu.addMenu(encryption_menu)

        # Add Create Schedule option
        tools_menu.addAction("Create Schedule", self.tray_app.schedule_creator.show_dialog)
        
        # Add View Schedules option
        tools_menu.addAction("View Schedules", self.tray_app.schedule_viewer.show_dialog)

        menu.addMenu(tools_menu)
        menu.addAction("Settings", self.tray_app._open_settings)
        menu.addAction("Quick Launch Bar", self.tray_app.quick_launch_bar.toggle)

        # Dynamic "Running: N" indicator (non-interactive, hidden when idle)
        menu.addSeparator()
        running_action = QAction("Running: 0", menu)
        running_action.setEnabled(False)
        running_action.setVisible(False)
        self.tray_app._running_action = running_action
        menu.addAction(running_action)

        menu.addAction("Restart App", self.tray_app.restart_app)
        menu.addAction("Exit", self.tray_app.confirm_exit)

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
                icon_path = self._get_item_icon_path(
                    item.get("icon"), parent_icon_path
                )

                submenu = QMenu(label, menu)
                submenu.setIcon(QIcon(icon_path))
                new_group = label if not group_name else f"{group_name} → {label}"
                self._add_menu_items(submenu, item, icon_path, new_group)
                menu.addMenu(submenu)

            # Handle command case (direct commands or references)
            elif isinstance(item, dict) and ("command" in item or "ref" in item):
                # Add command item to menu
                self._add_command_to_menu(
                    menu, label, item, parent_icon_path, group_name
                )

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
                commands = self.tray_app.command_menu

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
                icon_path = self._get_item_icon_path(
                    resolved_item.get("icon"), parent_icon_path
                )
                show_output = resolved_item.get("showOutput", False)
                confirm = resolved_item.get("confirm", False)
                prompt = resolved_item.get("prompt", None)

                # Create action with reference indicator
                action = QAction(QIcon(icon_path), f"{label}", menu)

                # Connect the action to execute command
                action.triggered.connect(
                    lambda checked=False, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: self.tray_app.execute(
                        lbl, cmd, conf, show, prmpt
                    )
                )

                menu.addAction(action)
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
        action = QAction(QIcon(icon_path), label, menu)

        # Connect the action to execute command
        action.triggered.connect(
            lambda checked=False, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: self.tray_app.execute(
                lbl, cmd, conf, show, prmpt
            )
        )

        menu.addAction(action)
        return action

    def _get_item_icon_path(self, icon_spec, fallback_path):
        """Resolve icon path with fallback to parent or default.
        
        Args:
            icon_spec: Icon path from config (or None)
            fallback_path: Path to use if icon_spec doesn't exist or is None
            
        Returns:
            Valid icon path (either resolved icon_spec or fallback_path)
        """
        if icon_spec:
            resolved = self.tray_app._resolve_icon_path(icon_spec)
            if resolved and os.path.isfile(resolved):
                return resolved
        return fallback_path
