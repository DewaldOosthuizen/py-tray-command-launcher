import sys
import json
import subprocess
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PyQt6.QtGui import QIcon

CONFIG_FILE = "commands.json"

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
        self.tray_icon = QSystemTrayIcon(QIcon("icon.png"))
        self.menu = QMenu()
        self.load_tray_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def load_tray_menu(self):
        """Load commands into the tray menu."""
        commands = load_commands()
        for group, items in commands.items():
            submenu = QMenu(group, self.menu)
            for label, command in items.items():
                submenu.addAction(label, lambda cmd=command: execute_command(cmd))
            self.menu.addMenu(submenu)
        self.menu.addSeparator()
        self.menu.addAction("Exit", self.app.quit)

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    app = TrayApp()
    app.run()
