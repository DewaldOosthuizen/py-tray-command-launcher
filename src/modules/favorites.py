import os
import json
from PyQt6.QtWidgets import QMenu, QMessageBox, QInputDialog
from PyQt6.QtGui import QIcon, QCursor, QAction
from PyQt6.QtCore import Qt

from utils.utils import load_commands
from core.config_manager import config_manager


class Favorites:
    """Handles favorites functionality."""

    def __init__(self, tray_app):
        """Initialize with a reference to the TrayApp."""
        self.tray_app = tray_app

    def add_to_favorites(self):
        """Add a command to favorites by reference."""
        # Get all available commands
        all_commands = self.tray_app.get_all_commands()

        if not all_commands:
            QMessageBox.warning(
                None, "No Commands", "No commands available to add to favorites."
            )
            return

        # Create a list of command options
        command_options = [f"{cmd['group']} → {cmd['label']}" for cmd in all_commands]

        # Let user select a command
        selection, ok = QInputDialog.getItem(
            None,
            "Add to Favorites",
            "Select a command to add to favorites:",
            command_options,
            0,
            False,
        )

        if ok and selection:
            # Get the selected command
            index = command_options.index(selection)
            command_data = all_commands[index]

            # Create command path
            command_path = command_data["group"]
            if " → " in command_data["group"]:
                # Handle nested paths
                parts = command_data["group"].split(" → ")
                command_path = ".".join(parts)
            command_path += "." + command_data["label"]

            # Get a label for the favorite
            default_label = command_data["label"]
            label, ok = QInputDialog.getText(
                None,
                "Favorite Label",
                "Enter a label for this favorite:",
                text=default_label,
            )

            if ok and label:
                # Add to favorites
                success = config_manager.add_to_favorites(command_path, label)

                if success:
                    QMessageBox.information(
                        None,
                        "Added to Favorites",
                        f"'{label}' has been added to Favorites as a reference to the original command.",
                    )
                    self.tray_app.reload_commands()
                else:
                    QMessageBox.warning(
                        None, "Failed", "Failed to add command to Favorites."
                    )

    def add_to_favorites_directly(self, group, label):
        """Add a command to favorites directly when selected from context menu."""
        # Create command path
        command_path = group
        if " → " in group:
            # Handle nested paths
            parts = group.split(" → ")
            command_path = ".".join(parts)
        command_path += "." + label

        # Add to favorites
        success = config_manager.add_to_favorites(command_path, label)

        if success:
            QMessageBox.information(
                None, "Added to Favorites", f"'{label}' has been added to Favorites."
            )
            self.tray_app.reload_commands()
        else:
            QMessageBox.warning(None, "Failed", "Failed to add command to Favorites.")

    def remove_from_favorites(self, label):
        """Remove a command from favorites."""
        if config_manager.remove_from_favorites(label):
            QMessageBox.information(
                None,
                "Removed from Favorites",
                f"'{label}' has been removed from Favorites.",
            )
            self.tray_app.reload_commands()
        else:
            QMessageBox.warning(
                None, "Failed", f"Failed to remove '{label}' from Favorites."
            )

    def create_context_menu(self, cmd_info, action):
        """Create a context menu for a command to add it to favorites."""
        context_menu = QMenu()
        add_to_fav_action = QAction("Add to Favorites", context_menu)
        add_to_fav_action.triggered.connect(lambda: self.add_to_favorites())
        context_menu.addAction(add_to_fav_action)

        action.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        action.customContextMenuRequested.connect(
            lambda pos: context_menu.exec(QCursor.pos())
        )

        return action

    def populate_favorites_menu(self, menu):
        """Populate the favorites menu with favorite commands."""
        commands = load_commands()

        # Ensure Favorites group exists
        if (
            "Favorites" not in commands or len(commands["Favorites"]) <= 1
        ):  # 1 for the icon
            action = QAction("No Favorites", menu)
            action.setEnabled(False)
            menu.addAction(action)

            help_action = QAction(
                "Right-click on any command and select 'Add to Favorites'", menu
            )
            help_action.setEnabled(False)
            menu.addAction(help_action)
            return

        # Add favorite commands to menu
        for label, item in commands["Favorites"].items():
            if label == "icon":
                continue

            if isinstance(item, dict):
                # Handle both direct commands and references
                resolved_item = item
                
                # If this is a reference, resolve it to get the actual command data
                if "ref" in item:
                    resolved_item = self.tray_app._resolve_command_reference("Favorites", label, item)
                
                # Check if we have a valid command (either direct or resolved)
                if "command" in resolved_item:
                    icon_path = os.path.expanduser(
                        resolved_item.get(
                            "icon",
                            os.path.join(
                                config_manager.get_base_dir(), "../icons/icon.png"
                            ),
                        )
                    )
                    action = QAction(QIcon(icon_path), label, menu)

                    command = resolved_item.get("command")
                    show_output = resolved_item.get("showOutput", False)
                    confirm = resolved_item.get("confirm", False)
                    prompt = resolved_item.get("prompt", None)

                    action.triggered.connect(
                        lambda checked=False,
                        cmd=command,
                        lbl=label,
                        conf=confirm,
                        show=show_output,
                        prmpt=prompt: self.tray_app.execute(lbl, cmd, conf, show, prmpt)
                    )

                    # Add submenu for removing from favorites
                    remove_menu = QMenu("More", menu)
                    remove_action = QAction("Remove from Favorites", remove_menu)
                    remove_action.triggered.connect(
                        lambda checked=False, lbl=label: self.remove_from_favorites(lbl)
                    )
                    remove_menu.addAction(remove_action)
                    action.setMenu(remove_menu)

                    menu.addAction(action)
