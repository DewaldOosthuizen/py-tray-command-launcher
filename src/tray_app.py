from ast import Str
import os
import subprocess
import sys
import datetime
import json
import shutil
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QMessageBox, QInputDialog, QLineEdit, QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel, QComboBox, QCheckBox, QFileDialog
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
        self.output_windows = []
        self.command_history = self.load_command_history()
        self.load_tray_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

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
        
        history_menu = QMenu("Recent Commands", self.menu)
        history_menu.setIcon(QIcon(ICON_FILE))
        self.populate_history_menu(history_menu)
        self.menu.addMenu(history_menu)
        
        self.menu.addSeparator()
        # Grouped menu actions for utility features

        # Commands group
        commands_menu = QMenu("Commands", self.menu)
        commands_menu.setIcon(QIcon(ICON_FILE))
        commands_menu.addAction('Search Commands', self.show_search_dialog)
        commands_menu.addAction('Create New Command', self.show_command_creator)
        commands_menu.addAction('Edit commands.json', self.open_commands_json)
        self.menu.addMenu(commands_menu)

        # Tools group
        tools_menu = QMenu("Tools", self.menu)
        tools_menu.setIcon(QIcon(ICON_FILE))

        # Import/Export submenu
        import_export_menu = QMenu("Import/Export", tools_menu)
        import_export_menu.setIcon(QIcon(ICON_FILE))
        import_export_menu.addAction("Export Command Group", self.export_command_group)
        import_export_menu.addAction("Import Command Group", self.import_command_group)
        tools_menu.addMenu(import_export_menu)

        # Backup/Restore submenu
        backup_restore_menu = QMenu("Backup/Restore", tools_menu)
        backup_restore_menu.setIcon(QIcon(ICON_FILE))
        backup_restore_menu.addAction("Backup Commands", self.backup_commands)
        backup_restore_menu.addAction("Restore Commands", self.restore_commands)
        tools_menu.addMenu(backup_restore_menu)

        self.menu.addMenu(tools_menu)
        self.menu.addAction("Restart App", self.restart_app)
        self.menu.addAction("Exit", self.confirm_exit)

    def add_menu_items(self, menu, items, parent_icon_path, group_name=""):
        """Recursively add items to the menu."""
        for label, item in items.items():
            if isinstance(item, dict) and "command" not in item and label not in ["icon"]:
                # Check if the icon entry exists, else default to parent_icon_path
                icon_path = os.path.expanduser(item.get("icon", parent_icon_path))
                
                # Check if the icon file exists, else default to parent_icon_path
                if icon_path != parent_icon_path and not os.path.isfile(icon_path):
                    icon_path = parent_icon_path
                
                # Create a submenu for nested dictionaries
                submenu = QMenu(label, menu)
                submenu.setIcon(QIcon(icon_path))
                new_group = label if not group_name else f"{group_name} → {label}"
                self.add_menu_items(submenu, item, icon_path, new_group)
                menu.addMenu(submenu)
            elif isinstance(item, dict) and "command" in item and label not in ["icon"]:
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
                    lambda _, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: 
                    self.execute(lbl, cmd, conf, show, prmpt)
                )
                
                # QAction does not support context menus; consider adding "Add to Favorites" elsewhere if needed.
                # Example: Add to favorites via a dedicated menu or dialog, or by extending the UI.
                
                # # Add context menu for adding to favorites
                # context_menu = QMenu()
                # add_to_fav_action = QAction("Add to Favorites", context_menu)
                # add_to_fav_action.triggered.connect(
                #     lambda _, grp=group_name, lbl=label, item=item:
                #     self.add_to_favorites(grp, lbl, item)
                # )
                # context_menu.addAction(add_to_fav_action)
                # action.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                # action.customContextMenuRequested.connect(
                #     lambda pos, menu=context_menu: menu.exec(QCursor.pos())
                # )
                
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
        # Add to history first
        self.add_to_history(title, command, confirm, show_output, prompt)
        
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
                if item is not None:
                    item.setHidden(search_text not in item.text().lower())
        
        search_box.textChanged.connect(filter_commands)
        
        # Execute the selected command
        def on_execute():
            current_item = command_list.currentItem()
            if current_item is not None:
                selected = current_item.text()
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

    def load_command_history(self):
        """Load command history from file."""
        history_file = os.path.join(BASE_DIR, "../config/history.json")
        try:
            if (os.path.exists(history_file)):
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception:
            return []

    def save_command_history(self):
        """Save command history to file."""
        history_file = os.path.join(BASE_DIR, "../config/history.json")
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(self.command_history, f, indent=4)
        except Exception as e:
            print(f"Failed to save command history: {e}")

    def add_to_history(self, title, command, confirm, show_output, prompt):
        """Add a command to history."""
        # Limit history to 10 items
        self.command_history = [cmd for cmd in self.command_history 
                               if cmd['command'] != command][:9]
        
        # Add the new command to the beginning
        self.command_history.insert(0, {
            'title': title,
            'command': command,
            'confirm': confirm,
            'showOutput': show_output,
            'prompt': prompt,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Save the updated history
        self.save_command_history()

    def populate_history_menu(self, menu):
        """Populate the history menu."""
        menu.clear()
        if not self.command_history:
            action = QAction("No Recent Commands", menu)
            action.setEnabled(False)
            menu.addAction(action)
            return
        
        for cmd in self.command_history:
            action = QAction(f"{cmd['title']} ({cmd['timestamp']})", menu)
            action.triggered.connect(
                lambda _, cmd=cmd: self.execute(
                    cmd['title'],
                    cmd['command'],
                    cmd['confirm'],
                    cmd['showOutput'],
                    cmd.get('prompt')
                )
            )
            menu.addAction(action)
        
        menu.addSeparator()
        menu.addAction("Clear History", self.clear_history)

    def clear_history(self):
        """Clear the command history."""
        self.command_history = []
        self.save_command_history()
        self.load_tray_menu()

    def add_to_favorites(self, group, label, command_data):
        """Add a command to favorites."""
        commands = load_commands()
        
        # Ensure Favorites group exists
        if "Favorites" not in commands:
            commands["Favorites"] = {"icon": "icons/icon.png"}
        
        # Add the command to favorites
        commands["Favorites"][f"{group} → {label}"] = command_data
        
        # Save the updated commands
        self.save_commands(commands)
        
        # Reload the menu
        self.restart_app()

    def save_commands(self, commands):
        """Save commands to the JSON configuration file."""
        try:
            config_file = os.path.join(BASE_DIR, "../config/commands.json")
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(commands, f, indent=4)
        except Exception as e:
            show_error_and_raise(f"Failed to save commands: {e}")

    def show_command_creator(self):
        """Show a dialog to create a new command."""
        dialog = QDialog()
        dialog.setWindowTitle("Create New Command")
        layout = QVBoxLayout()
        
        # Group selection
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Group:"))
        group_combo = QComboBox()
        
        commands = load_commands()
        groups = list(commands.keys())
        group_combo.addItems(groups)
        group_combo.setEditable(True)
        group_layout.addWidget(group_combo)
        layout.addLayout(group_layout)
        
        # Command name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        name_edit = QLineEdit()
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)
        
        # Command
        cmd_layout = QHBoxLayout()
        cmd_layout.addWidget(QLabel("Command:"))
        cmd_edit = QLineEdit()
        cmd_layout.addWidget(cmd_edit)
        layout.addLayout(cmd_layout)
        
        # Icon selection
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(QLabel("Icon:"))
        icon_edit = QLineEdit()
        icon_edit.setText("")
        icon_layout.addWidget(icon_edit)
        browse_btn = QPushButton("Browse...")
        
        def browse_icon():
            file_path, _ = QFileDialog.getOpenFileName(
                dialog, "Select Icon", "", "Image Files (*.png *.jpg *.jpeg *.ico *.svg)"
            )
            if file_path:
                icon_edit.setText(file_path)
        
        browse_btn.clicked.connect(browse_icon)
        icon_layout.addWidget(browse_btn)
        layout.addLayout(icon_layout)
        
        # Options
        options_layout = QVBoxLayout()
        show_output_check = QCheckBox("Show Output")
        confirm_check = QCheckBox("Confirm Before Execution")
        prompt_check = QCheckBox("Prompt for Input")
        prompt_edit = QLineEdit()
        prompt_edit.setPlaceholderText("Enter prompt text...")
        prompt_edit.setEnabled(False)
        
        def toggle_prompt():
            prompt_edit.setEnabled(prompt_check.isChecked())
        
        prompt_check.stateChanged.connect(toggle_prompt)
        
        options_layout.addWidget(show_output_check)
        options_layout.addWidget(confirm_check)
        options_layout.addWidget(prompt_check)
        options_layout.addWidget(prompt_edit)
        layout.addLayout(options_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        create_btn = QPushButton("Create")
        
        cancel_btn.clicked.connect(dialog.reject)
        
        def create_command():
            group = group_combo.currentText()
            name = name_edit.text()
            command = cmd_edit.text()
            
            if not group or not name or not command:
                QMessageBox.critical(dialog, "Error", "Group, Name, and Command are required!")
                return
            
            # Create command data
            cmd_data = {
                "command": command,
                "showOutput": show_output_check.isChecked(),
                "confirm": confirm_check.isChecked()
            }
            
            if icon_edit.text():
                cmd_data["icon"] = icon_edit.text()
            
            if prompt_check.isChecked() and prompt_edit.text():
                cmd_data["prompt"] = prompt_edit.text()
            
            # Add the command to the config
            if group not in commands:
                commands[group] = {}
            
            commands[group][name] = cmd_data
            
            # Save the config
            self.save_commands(commands)
            
            # Reload the menu
            self.restart_app()
            
            dialog.accept()
        
        create_btn.clicked.connect(create_command)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(create_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.exec()

    def backup_commands(self):
        """Backup the commands.json file."""
        commands_file = os.path.join(BASE_DIR, "../config/commands.json")
        backup_dir = os.path.join(BASE_DIR, "../config/backups")
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Generate backup filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"commands_{timestamp}.json")
        
        try:
            # Copy the commands file to the backup location
            shutil.copy2(commands_file, backup_file)
            QMessageBox.information(None, "Backup", f"Successfully backed up commands to:\n{backup_file}")
        except Exception as e:
            QMessageBox.critical(None, "Backup Failed", f"Failed to backup commands: {e}")

    def restore_commands(self):
        """Restore the commands.json file from a backup."""
        backup_dir = os.path.join(BASE_DIR, "../config/backups")
        
        # Check if backup directory exists
        if not os.path.exists(backup_dir):
            QMessageBox.critical(None, "Restore Failed", "No backups found!")
            return
        
        # Get list of backup files
        backup_files = [f for f in os.listdir(backup_dir) if f.startswith("commands_") and f.endswith(".json")]
        
        if not backup_files:
            QMessageBox.critical(None, "Restore Failed", "No backup files found!")
            return
        
        # Sort backup files by name (timestamp) in descending order
        backup_files.sort(reverse=True)
        
        # Create a dialog to select a backup
        dialog = QDialog()
        dialog.setWindowTitle("Restore Commands")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Select a backup to restore:"))
        
        list_widget = QListWidget()
        for file in backup_files:
            # Extract timestamp and format it
            timestamp = file.replace("commands_", "").replace(".json", "")
            formatted_date = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
            list_widget.addItem(f"{formatted_date} - {file}")
        
        layout.addWidget(list_widget)
        
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        restore_btn = QPushButton("Restore")
        
        cancel_btn.clicked.connect(dialog.reject)
        
        def do_restore():
            if not list_widget.currentItem():
                QMessageBox.critical(dialog, "Error", "Please select a backup to restore!")
                return
            
            current_item = list_widget.currentItem()
            if current_item is None:
                QMessageBox.critical(dialog, "Error", "Please select a backup to restore!")
                return
            selected = current_item.text()
            backup_file = selected.split(" - ")[1]
            
            if QMessageBox.question(
                dialog, "Confirm Restore", 
                f"Are you sure you want to restore from:\n{backup_file}?\n\nThis will overwrite your current commands.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                try:
                    commands_file = os.path.join(BASE_DIR, "../config/commands.json")
                    backup_path = os.path.join(backup_dir, backup_file)
                    
                    # Make a backup of the current file before restoring
                    self.backup_commands()
                    
                    # Copy the backup file to the commands file
                    shutil.copy2(backup_path, commands_file)
                    
                    QMessageBox.information(None, "Restore", "Successfully restored commands!")
                    
                    # Reload the menu
                    self.restart_app()
                    
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(dialog, "Restore Failed", f"Failed to restore commands: {e}")

        restore_btn.clicked.connect(do_restore)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(restore_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.resize(400, 300)
        dialog.exec()

    def export_command_group(self):
        """Export a command group to a JSON file."""
        commands = load_commands()
        
        # Create a dialog to select a group
        dialog = QDialog()
        dialog.setWindowTitle("Export Command Group")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Select a group to export:"))
        
        list_widget = QListWidget()
        list_widget.addItems(commands.keys())
        layout.addWidget(list_widget)
        
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        export_btn = QPushButton("Export")
        
        cancel_btn.clicked.connect(dialog.reject)
        
        def do_export():
            if not list_widget.currentItem():
                QMessageBox.critical(dialog, "Error", "Please select a group to export!")
                return
            
            current_item = list_widget.currentItem()
            if not current_item:
                QMessageBox.critical(dialog, "Error", "Please select a group to export!")
                return
            group_name = current_item.text()
            
            # Get export file path
            file_path, _ = QFileDialog.getSaveFileName(
                dialog, "Export Group", f"{group_name}.json", "JSON Files (*.json)"
            )
            
            if file_path:
                try:
                    # Export the group to the file
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump({group_name: commands[group_name]}, f, indent=4)
                    
                    QMessageBox.information(None, "Export", f"Successfully exported group '{group_name}' to:\n{file_path}")
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(dialog, "Export Failed", f"Failed to export group: {e}")
        
        export_btn.clicked.connect(do_export)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(export_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.resize(300, 200)
        dialog.exec()

    def import_command_group(self):
        """Import a command group from a JSON file."""
        # Get import file path
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Import Group", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Read the import file
                with open(file_path, "r", encoding="utf-8") as f:
                    import_data = json.load(f)
                
                if not isinstance(import_data, dict):
                    QMessageBox.critical(None, "Import Failed", "Invalid import file format!")
                    return
                
                # Get current commands
                commands = load_commands()
                
                # Check for conflicts
                conflicts = []
                for group_name in import_data.keys():
                    if group_name in commands:
                        conflicts.append(group_name)
                
                # Handle conflicts
                if conflicts:
                    reply = QMessageBox.question(
                        None, "Import Conflicts",
                        f"The following groups already exist:\n{', '.join(conflicts)}\n\nDo you want to overwrite them?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.No:
                        return
                
                # Merge the import data with current commands
                for group_name, group_data in import_data.items():
                    commands[group_name] = group_data
                
                # Save the updated commands
                self.save_commands(commands)
                
                QMessageBox.information(None, "Import", "Successfully imported command groups!")
                
                # Reload the menu
                self.restart_app()
                
            except Exception as e:
                QMessageBox.critical(None, "Import Failed", f"Failed to import group: {e}")