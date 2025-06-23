import os
import json
import datetime
from PyQt6.QtGui import QIcon, QAction
from core.config_manager import config_manager


class CommandHistory:
    """Manages the command history functionality."""

    def __init__(self, tray_app):
        """Initialize with a reference to the TrayApp."""
        self.tray_app = tray_app

    def load_history(self):
        """Load command history from file."""
        history_file = os.path.join(self.BASE_DIR, "../config/history.json")
        try:
            if os.path.exists(history_file):
                with open(history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            return []
        except Exception:
            return []

    def save_history(self):
        """Save command history to file."""
        history_file = os.path.join(self.BASE_DIR, "../config/history.json")
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=4)
        except Exception as e:
            print(f"Failed to save command history: {e}")

    def add_to_history(self, title, command, confirm, show_output, prompt):
        """Add a command to the history."""
        history_entry = {
            "command": command,
            "title": title,
            "confirm": confirm,
            "showOutput": show_output,
            "prompt": prompt,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        config_manager.add_to_history(history_entry)

    def populate_menu(self, menu):
        """Populate the history menu with recent commands."""
        menu.clear()
        history = config_manager.get_history(refresh=True)

        if not history:
            menu.addAction("No recent commands").setEnabled(False)
            return

        # Add clear history action
        menu.addAction("Clear History", self.clear_history)
        menu.addSeparator()

        # Add recent commands
        for entry in history:
            title = entry.get("title", "Unknown Command")
            command = entry.get("command", "")
            confirm = entry.get("confirm", False)
            show_output = entry.get("showOutput", False)
            prompt = entry.get("prompt")

            action = QAction(title, menu)
            action.triggered.connect(
                lambda checked,
                t=title,
                c=command,
                cf=confirm,
                so=show_output,
                p=prompt: self.tray_app.execute(t, c, cf, so, p)
            )
            menu.addAction(action)

    def clear_history(self):
        """Clear the command history."""
        config_manager.clear_history()
        self.populate_menu(self.tray_app.history_menu)
