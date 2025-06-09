from ast import Str
import os
import subprocess
import sys
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QMessageBox, QInputDialog, QLineEdit, QDialog, QVBoxLayout, QListWidget, QPushButton
from PyQt6.QtGui import QIcon, QAction
from command_executor import execute_command, execute_command_process
from utils import load_commands
from dialogs import confirm_execute, show_error_and_raise, confirm_exit
from output_window import OutputWindow

# Define the base directory and icon file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FILE = os.path.join(BASE_DIR, "../icons/icon.png")

class TrayApp:
    def __init__(self, app):
        """Initialize the TrayApp with the given QApplication instance."""
        self.app = app
        self.app.aboutToQuit.connect(self.cleanup)
        # Keep the app running even if all windows are closed
        self.app.setQuitOnLastWindowClosed(False)
        self.tray_icon = QSystemTrayIcon(QIcon(ICON_FILE))
        self.tray_icon.setVisible(True)
        self.menu = QMenu()
        self.load_tray_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        self.output_windows = []

    def load_tray_menu(self):
        """Load commands into the tray menu."""
        commands = load_commands()
        
        # Check if commands is a dictionary
        if not isinstance(commands, dict):
            show_error_and_raise("Invalid commands.json format. Root element must be a dictionary.")
    
        # Iterate over the commands and create menu items
        for group, items in commands.items():
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
        self.menu.addSeparator()
        self.menu.addAction('Search Commands', self.show_search_dialog)
        self.menu.addAction('Edit commands.json', self.open_commands_json)
        self.menu.addAction("Restart App", self.restart_app)
        self.menu.addAction("Exit", self.confirm_exit)

    def add_menu_items(self, menu, items, parent_icon_path):
        """Recursively add items to the menu."""
        for label, item in items.items():
            if isinstance(item, dict) and "command" not in item:
                
                # Check if the icon entry exists, else default to parent_icon_path
                icon_path = os.path.expanduser(items.get("icon", parent_icon_path))
                
                # Check if the icon file exists, else default to parent_icon_path
                if icon_path != parent_icon_path and not os.path.isfile(icon_path):
                    icon_path = parent_icon_path
                
                # Create a submenu for nested dictionaries
                submenu = QMenu(label, menu)
                submenu.setIcon(QIcon(icon_path))
                self.add_menu_items(submenu, item, icon_path)
                menu.addMenu(submenu)
            elif isinstance(item, dict):
                # Add a command item to the menu
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
                    lambda _, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: self.execute(lbl, cmd, conf, show, prmpt)
                )
                
                # Add the action to the menu
                menu.addAction(action)

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

    def restart_app(self):
        """Restart the application."""
        self.cleanup()
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def execute(self, title, command, confirm, show_output, prompt):
        """Execute a command with optional confirmation and input prompt."""
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

    def show_search_dialog(self):
        """Show a dialog to search for commands."""
        dialog = QDialog()
        dialog.setWindowTitle("Search Commands")
        layout = QVBoxLayout()
        
        search_box = QLineEdit()
        search_box.setPlaceholderText("Type to search...")
        layout.addWidget(search_box)
        
        command_list = QListWidget()
        layout.addWidget(command_list)
        
        execute_button = QPushButton("Execute")
        layout.addWidget(execute_button)
        
        dialog.setLayout(layout)
        
        # Populate the list with all commands
        all_commands = self.get_all_commands()
        for cmd_info in all_commands:
            command_list.addItem(f"{cmd_info['group']} → {cmd_info['label']}")
        
        # Filter as user types
        def filter_commands():
            search_text = search_box.text().lower()
            for i in range(command_list.count()):
                item = command_list.item(i)
                item.setHidden(search_text not in item.text().lower())
        
        search_box.textChanged.connect(filter_commands)
        
        # Execute the selected command
        def on_execute():
            if command_list.currentItem():
                selected = command_list.currentItem().text()
                for cmd_info in all_commands:
                    if f"{cmd_info['group']} → {cmd_info['label']}" == selected:
                        self.execute(
                            cmd_info['label'],
                            cmd_info['command'],
                            cmd_info['confirm'],
                            cmd_info['showOutput'],
                            cmd_info.get('prompt')
                        )
                        dialog.accept()
                        break
        
        execute_button.clicked.connect(on_execute)
        command_list.itemDoubleClicked.connect(lambda: on_execute())
        
        dialog.exec()

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