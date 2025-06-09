import os
import json
from PyQt6.QtWidgets import QMenu, QMessageBox
from PyQt6.QtGui import QIcon, QCursor, QAction
from PyQt6.QtCore import Qt

from utils import load_commands

class Favorites:
    """Manages favorite commands functionality."""
    
    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def add_to_favorites(self, group, label, command_data):
        """Add a command to favorites."""
        commands = load_commands()
        
        # Ensure Favorites group exists
        if "Favorites" not in commands:
            commands["Favorites"] = {"icon": os.path.join(self.BASE_DIR, "../icons/icon.png")}
        
        # Add the command to favorites
        if group:
            favorite_name = f"{group} → {label}"
        else:
            favorite_name = label
            
        commands["Favorites"][favorite_name] = command_data
        
        # Save the updated commands
        self.app.save_commands(commands)
        
        # Show confirmation
        QMessageBox.information(None, "Favorites", f"Added '{favorite_name}' to Favorites!")
        
        # Reload the menu
        self.app.restart_app()
    
    def remove_from_favorites(self, label):
        """Remove a command from favorites."""
        commands = load_commands()
        
        # Ensure Favorites group exists
        if "Favorites" not in commands:
            return
        
        # Remove the command from favorites
        if label in commands["Favorites"]:
            del commands["Favorites"][label]
            
            # Save the updated commands
            self.app.save_commands(commands)
            
            # Show confirmation
            QMessageBox.information(None, "Favorites", f"Removed '{label}' from Favorites!")
            
            # Reload the menu
            self.app.restart_app()
    
    def create_context_menu(self, cmd_info, action):
        """Create a context menu for a command to add it to favorites."""
        context_menu = QMenu()
        add_to_fav_action = QAction("Add to Favorites", context_menu)
        add_to_fav_action.triggered.connect(
            lambda: self.add_to_favorites(
                cmd_info.get('group', ''),
                cmd_info.get('label', ''),
                {
                    "command": cmd_info.get('command', ''),
                    "showOutput": cmd_info.get('showOutput', False),
                    "confirm": cmd_info.get('confirm', False),
                    "prompt": cmd_info.get('prompt')
                }
            )
        )
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
        if "Favorites" not in commands or len(commands["Favorites"]) <= 1:  # 1 for the icon
            action = QAction("No Favorites", menu)
            action.setEnabled(False)
            menu.addAction(action)
            
            help_action = QAction("Right-click on any command and select 'Add to Favorites'", menu)
            help_action.setEnabled(False)
            menu.addAction(help_action)
            return
        
        # Add favorite commands to menu
        for label, item in commands["Favorites"].items():
            if label == "icon":
                continue
                
            if isinstance(item, dict) and "command" in item:
                icon_path = os.path.expanduser(item.get("icon", os.path.join(self.BASE_DIR, "../icons/icon.png")))
                action = QAction(QIcon(icon_path), label, menu)
                
                command = item.get("command")
                show_output = item.get("showOutput", False)
                confirm = item.get("confirm", False)
                prompt = item.get("prompt", None)
                
                action.triggered.connect(
                    lambda checked=False, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: 
                    self.app.execute(lbl, cmd, conf, show, prmpt)
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