import sys
import json
import subprocess
import os
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QCoreApplication

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "commands.json")
ICON_FILE = os.path.join(BASE_DIR, "icon.png")

def load_commands():
    """Load commands from the JSON configuration file."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def execute_command(command):
    """Execute a shell command."""
    subprocess.Popen(command, shell=True)

class TrayApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.aboutToQuit.connect(self.cleanup)
        self.tray_icon = QSystemTrayIcon(QIcon(ICON_FILE))
        self.menu = QMenu()
        self.load_tray_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def cleanup(self):
        """Perform any cleanup before quitting."""
        print("Cleaning up before exit...")

    def load_tray_menu(self):
        """Load commands into the tray menu."""
        commands = load_commands()
        for group, items in commands.items():
            submenu = QMenu(group, self.menu)
            for label, command in items.items():
                submenu.addAction(label, lambda cmd=command: execute_command(cmd))
            self.menu.addMenu(submenu)
        self.menu.addSeparator()
        self.menu.addAction("Exit", self.confirm_exit)
        self.menu.addAction("Force Quit", self.confirm_force_quit)

    def confirm_exit(self):
        """Show confirmation dialog for exiting the application."""
        reply = QMessageBox.question(None, 'Exit Confirmation', 
                                     'Are you sure you want to exit?', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.app.quit()

    def confirm_force_quit(self):
        """Show confirmation dialog for force quitting the application."""
        reply = QMessageBox.question(None, 'Force Quit Confirmation', 
                                     'Are you sure you want to force quit?', 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.force_quit()

    def force_quit(self):
        """Force quit the application."""
        self.cleanup()
        sys.exit()
        QCoreApplication.exit()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app = TrayApp()
    app.run()
