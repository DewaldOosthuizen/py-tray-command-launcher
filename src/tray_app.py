from ast import Str
import os
import subprocess
import sys
import datetime
import json
import shutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QMessageBox, QInputDialog
from PyQt6.QtGui import QIcon, QAction

from command_executor import execute_command, execute_command_process
from utils import load_commands
from dialogs import confirm_execute, show_error_and_raise, confirm_exit
from output_window import OutputWindow

# Modules for various functionalities
from modules.command_history import CommandHistory
from modules.command_creator import CommandCreator
from modules.command_search import CommandSearch
from modules.backup_restore import BackupRestore
from modules.import_export import ImportExport
from modules.favorites import Favorites

# Define the base directory and icon file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FILE = os.path.join(BASE_DIR, "../icons/icon.png")

class TrayApp:
    """Main tray application class that manages the system tray icon and menu."""
    
    def __init__(self, app):
        """Initialize the TrayApp with the given QApplication instance."""
        self.app = app
        self.app.aboutToQuit.connect(self.cleanup)
        # Keep the app running even if all windows are closed
        self.app.setQuitOnLastWindowClosed(False)
        
        # Initialize tray icon and menu
        self.tray_icon = QSystemTrayIcon(QIcon(ICON_FILE))
        self.tray_icon.setVisible(True)
        self.menu = QMenu()
        self.output_windows = []
        
        # Initialize module components
        self.command_menu = load_commands();
        self.history_menu = load_commands();
        self.history = CommandHistory(self)
        self.creator = CommandCreator(self)
        self.search = CommandSearch(self)
        self.backup = BackupRestore(self)
        self.importExport = ImportExport(self)
        self.favorites = Favorites(self)
        
        # Load menu and set up tray icon
        self.load_tray_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
    
    # Core menu handling methods
    def load_tray_menu(self):
        """Load commands into the tray menu."""
        self.reload_commands()
        
        # Check if commands is a dictionary
        if not isinstance(self.command_menu, dict):
            show_error_and_raise("Invalid commands.json format. Root element must be a dictionary.")
    
        # Iterate over the commands and create menu items
        for group, items in self.command_menu.items():
            # Check if each group is a dictionary
            if not isinstance(items, dict):
                show_error_and_raise(f"Invalid command group format in commands.json: {group}. Each group must be a dictionary.")
                
            # Check if the icon entry exists, else default to ICON_FILE
            icon_path = os.path.expanduser(items.get("icon", ICON_FILE))
            
            # Check if the icon file exists, else default to ICON_FILE
            if icon_path != ICON_FILE and not os.path.isfile(icon_path):
                icon_path = ICON_FILE
            
             # Create a submenu for each group
            submenu = QMenu(group, self.menu)
            submenu.setIcon(QIcon(icon_path))
            
            # Recursively add items to the submenu
            self.add_menu_items(submenu, items, icon_path)
            
            self.menu.addMenu(submenu)
        
        # Add history menu
        self.history_menu = QMenu("Recent Commands", self.menu)
        self.history_menu.setIcon(QIcon(ICON_FILE))
        self.menu.addMenu(self.history_menu)
        self.reload_history_commands()
        
        self.menu.addSeparator()
        
        # Commands group
        commands_menu = QMenu("Commands", self.menu)
        commands_menu.setIcon(QIcon(ICON_FILE))
        commands_menu.addAction('Search Commands', self.search.show_dialog)
        commands_menu.addAction('Create New Command', self.creator.show_dialog)
        commands_menu.addAction('Edit commands.json', self.open_commands_json)
        commands_menu.addAction('Reload Commands', self.reload_commands)
        commands_menu.addAction('Reload History Commands', self.reload_history_commands)
        # commands_menu.addAction('Add command to Fav', self.favorites.add_to_favorites)
        self.menu.addMenu(commands_menu)

        # Tools group
        tools_menu = QMenu("Tools", self.menu)
        tools_menu.setIcon(QIcon(ICON_FILE))

        # Import/Export submenu
        import_export_menu = QMenu("Import/Export", tools_menu)
        import_export_menu.setIcon(QIcon(ICON_FILE))
        import_export_menu.addAction("Export Command Group", self.importExport.export_command_group)
        import_export_menu.addAction("Import Command Group", self.importExport.import_command_group)
        tools_menu.addMenu(import_export_menu)

        # Backup/Restore submenu
        backup_restore_menu = QMenu("Backup/Restore", tools_menu)
        backup_restore_menu.setIcon(QIcon(ICON_FILE))
        backup_restore_menu.addAction("Backup Commands", self.backup.backup_commands)
        backup_restore_menu.addAction("Restore Commands", self.backup.restore_commands)
        tools_menu.addMenu(backup_restore_menu)

        self.menu.addMenu(tools_menu)
        self.menu.addAction("Restart App", self.restart_app)
        self.menu.addAction("Exit", self.confirm_exit)

    def add_menu_items(self, menu, items, parent_icon_path, group_name=""):
        """Recursively add items to the menu."""
        for label, item in items.items():
            if isinstance(item, dict) and "command" not in item and label not in ["icon"]:
                # Create submenu for nested dictionaries
                icon_path = os.path.expanduser(item.get("icon", parent_icon_path))
                
                if icon_path != parent_icon_path and not os.path.isfile(icon_path):
                    icon_path = parent_icon_path
                
                submenu = QMenu(label, menu)
                submenu.setIcon(QIcon(icon_path))
                new_group = label if not group_name else f"{group_name} → {label}"
                self.add_menu_items(submenu, item, icon_path, new_group)
                menu.addMenu(submenu)
            elif isinstance(item, dict) and "command" in item and label not in ["icon"]:
                # Add command item to menu
                self._add_command_to_menu(menu, label, item, parent_icon_path, group_name)
    
    def _add_command_to_menu(self, menu, label, item, parent_icon_path, group_name=""):
        """Add a command item to the menu."""
        command = item.get("command")
        
        # Validate required fields
        if not command:
            show_error_and_raise(f"Invalid command format in commands.json: {label}. 'command' is required.")
        
        icon_path = os.path.expanduser(item.get("icon", parent_icon_path))
        show_output = item.get("showOutput", False)
        confirm = item.get("confirm", False)
        prompt = item.get("prompt", None)
        action = QAction(QIcon(icon_path), label, menu)
        
        # Connect the action to execute command
        action.triggered.connect(
            lambda _, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: 
            self.execute(lbl, cmd, conf, show, prmpt)
        )
        
        menu.addAction(action)
    
    # Command execution methods
    def execute(self, title, command, confirm, show_output, prompt):
        """Execute a command with optional confirmation and input prompt."""
        # Add to history first
        self.history.add_to_history(title, command, confirm, show_output, prompt)
        
        if confirm:
            if not confirm_execute(command):
                return

        if prompt:
            input_value, ok = QInputDialog.getText(None, 'Input Required', prompt)
            if not ok or not input_value:
                return
            command = command.replace("{promptInput}", input_value)

        if show_output:
            self.show_command_output(title, command)
        else:
            execute_command(command)
        
        self.reload_commands()
        self.reload_history_commands()

    def show_command_output(self, title, command):
        """Execute a command and show the output in a new window."""
        process = execute_command_process(self.app, command)
        
        def handle_finished(exit_code, exit_status):
            stdout = process.readAllStandardOutput().data().decode()
            stderr = process.readAllStandardError().data().decode()
            output = stdout if stdout else stderr
            output_window = OutputWindow(title, output, parent=self.app.activeWindow())
            self.output_windows.append(output_window)
            output_window.destroyed.connect(lambda _, :self.output_windows.remove(output_window) if output_window in self.output_windows else None)
            output_window.show()
        process.finished.connect(handle_finished)
        process.start()
    
    # Utility methods
    def save_commands(self, commands):
        """Save commands to the JSON configuration file."""
        try:
            config_file = os.path.join(BASE_DIR, "../config/commands.json")
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(commands, f, indent=4)
        except Exception as e:
            show_error_and_raise(f"Failed to save commands: {e}")
    
    def get_all_commands(self):
        """Get all commands from the configuration."""
        commands = load_commands()
        result = []
        
        def process_items(group_name, items):
            for label, item in items.items():
                if isinstance(item, dict) and "command" in item:
                    result.append({
                        'group': group_name,
                        'label': label,
                        'command': item['command'],
                        'confirm': item.get('confirm', False),
                        'showOutput': item.get('showOutput', False),
                        'prompt': item.get('prompt')
                    })
                elif isinstance(item, dict) and "command" not in item:
                    # For nested menus
                    for sublabel, subitem in item.items():
                        if isinstance(subitem, dict) and "command" in subitem:
                            result.append({
                                'group': f"{group_name} → {label}",
                                'label': sublabel,
                                'command': subitem['command'],
                                'confirm': subitem.get('confirm', False),
                                'showOutput': subitem.get('showOutput', False),
                                'prompt': subitem.get('prompt')
                            })
        
        for group_name, items in commands.items():
            if isinstance(items, dict) and "command" not in items:
                process_items(group_name, items)
        
        return result
    
    def open_commands_json(self):
        """Open the commands.json file with the default text editor."""
        commands_json_path = os.path.join(BASE_DIR, "../config/commands.json")
        try:
            # Open the commands.json file with the default text editor
            if sys.platform == "win32":
                os.startfile(commands_json_path)
            elif sys.platform == "darwin":
                subprocess.call(("open", commands_json_path))
            else:
                subprocess.call(("xdg-open", commands_json_path))
        except Exception as e:
            show_error_and_raise(f"Failed to open commands.json: {e}")
            
    def reload_commands(self):
        """Reload the commands from the configuration file."""
        self.command_menu = load_commands()
        
    def reload_history_commands(self):
        """Reload the commands from the configuration file."""
        self.history.populate_menu(self.history_menu)

    def restart_app(self):
        """Restart the application."""
        self.cleanup()
        python = sys.executable
        os.execl(python, python, *sys.argv)
    
    def confirm_exit(self):
        """Show confirmation dialog for exiting the application."""
        if confirm_exit():
            self.app.quit()

    def cleanup(self):
        """Perform any cleanup before quitting."""
        print("Cleaning up before exit...")
        for window in self.output_windows:
            window.close()

    def run(self):
        """Run the application event loop."""
        sys.exit(self.app.exec())