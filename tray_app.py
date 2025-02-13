import os
import sys
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QMessageBox
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QProcess
from output_window import OutputWindow
from command_executor import execute_command
from utils import load_commands
import subprocess

# Define the base directory and icon file path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FILE = os.path.join(BASE_DIR, "icons/icon.png")

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
        
        # Iterate over the commands and create menu items
        for group, items in commands.items():
            
            # Create a submenu for each group
            submenu = QMenu(group, self.menu)
            
            # Iterate over the items in the group
            for label, item in items.items():
                
                # Check if the item is a dictionary
                if isinstance(item, dict):
                    command = item.get("command")
                    icon_path = os.path.join(BASE_DIR, item.get("icon", ICON_FILE))
                    show_output = item.get("showOutput", False)
                    confirm = item.get("confirm", False)
                    action = QAction(QIcon(icon_path), label, self.menu)
                    
                    # Check if the item has a confirmation prompt
                    if show_output:
                        # Connect the action to execute_with_confirmation with show_output=True
                        action.triggered.connect(
                            lambda _,
                            cmd=command,
                            lbl=label,
                            conf=confirm: self.execute_with_confirmation(lbl, cmd, conf, show_output=True)
                        )
                    else:
                        # Connect the action to execute_with_confirmation with show_output=False
                        action.triggered.connect(
                            lambda _,
                            cmd=command,
                            conf=confirm: self.execute_with_confirmation(None, cmd, conf, show_output=False)
                        )
                    
                    # Add the action to the submenu
                    submenu.addAction(action)
                else:
                    # WE SHOULD NEVER REACH THIS POINT, COMMANDS.JSON IS MALFORMED
                    raise Exception("Invalid command format in commands.json. Stopping the process to avoid app from misbehaving.")
                
            self.menu.addMenu(submenu)
        self.menu.addSeparator()
        self.menu.addAction('Edit commands.json', self.open_commands_json)
        self.menu.addAction("Restart App", self.restart_app)
        self.menu.addAction("Exit", self.confirm_exit)


    def open_commands_json(self):
        """Open the commands.json file with the default text editor."""
        commands_json_path = os.path.join(BASE_DIR, "commands.json")
        try:
            # Open the commands.json file with the default text editor
            if sys.platform == "win32":
                # Use os.startfile to open the file with the default application on Windows
                os.startfile(commands_json_path)
            elif sys.platform == "darwin":
                # Use subprocess to open the file with the default application on macOS
                subprocess.call(("open", commands_json_path))
            else:
                # Use subprocess to open the file with the default application on Linux
                subprocess.call(("xdg-open", commands_json_path))
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to open commands.json: {e}")


    def restart_app(self):
        """Restart the application."""
        # Perform cleanup before restarting
        self.cleanup()
        # Restart the application by re-executing the script
        python = sys.executable
        # Use os.execl to replace the current process with a new one
        os.execl(python, python, *sys.argv)


    def execute_with_confirmation(self, title, command, confirm, show_output):
        """Execute a command with optional confirmation."""
        if confirm:
            reply = QMessageBox.question(None, 'Confirmation',
                                        f'Are you sure you want to execute "{command}"?',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Check if the command should show the output in a new window
        if show_output:
            # Show the command output in a new window
            self.show_command_output(title, command)
        else:
            # Execute the command directly
            execute_command(command)


    def show_command_output(self, title, command):
        """Execute a command and show the output in a new window."""
        process = QProcess(self.app)  # Use self.app as the parent
        process.setProgram("bash")
        process.setArguments(["-c", command])
        
        def handle_finished(exit_code, exit_status):
            stdout = process.readAllStandardOutput().data().decode()
            stderr = process.readAllStandardError().data().decode()
            output = stdout if stdout else stderr
            # Create a new output window
            output_window = OutputWindow(title, output, parent=self.app.activeWindow())  # Ensure app stays alive
            self.output_windows.append(output_window)
            # Ensure it is removed when closed
            output_window.destroyed.connect(lambda: self.output_windows.remove(output_window) if output_window in self.output_windows else None)
            output_window.show()
        # Connect the finished signal to handle_finished
        process.finished.connect(handle_finished)
        process.start()


    def confirm_exit(self):
        """Show confirmation dialog for exiting the application."""
        reply = QMessageBox.question(
            None, 'Exit Confirmation',
            'Are you sure you want to exit?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.app.quit()


    def cleanup(self):
        """Perform any cleanup before quitting."""
        print("Cleaning up before exit...")
        # Close all output windows
        for window in self.output_windows:
            window.close()


    def run(self):
        """Run the application event loop."""
        sys.exit(self.app.exec())