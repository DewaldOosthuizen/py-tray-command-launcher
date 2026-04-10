

import logging
import datetime
from PyQt6.QtGui import QIcon, QAction
from core.config_manager import config_manager

logger = logging.getLogger(__name__)


class CommandHistory:
    """Manages the command history functionality."""

    def __init__(self, services):
        """Initialize with an AppServices instance."""
        self.services = services

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
                p=prompt: self.services.execute(t, c, cf, so, p)
            )
            menu.addAction(action)

    def clear_history(self):
        """Clear the command history."""
        config_manager.clear_history()
        self.services.reload_history_commands()
