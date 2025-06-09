import os
import json
import datetime
from PyQt6.QtGui import QAction

class CommandHistory:
    """Manages command history functionality."""
    
    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.history = self.load_history()
    
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
        """Add a command to history."""
        # Limit history to 10 items
        self.history = [cmd for cmd in self.history 
                       if cmd['command'] != command][:9]
        
        # Add the new command to the beginning
        self.history.insert(0, {
            'title': title,
            'command': command,
            'confirm': confirm,
            'showOutput': show_output,
            'prompt': prompt,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Save the updated history
        self.save_history()
    
    def populate_menu(self, menu):
        """Populate the history menu."""
        menu.clear()
        if not self.history:
            action = QAction("No Recent Commands", menu)
            action.setEnabled(False)
            menu.addAction(action)
            return
        
        for cmd in self.history:
            action = QAction(f"{cmd['title']} ({cmd['timestamp']})", menu)
            action.triggered.connect(
                lambda _, cmd=cmd: self.app.execute(
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
        self.history = []
        self.save_history()
        self.populate_menu(self.app.history_menu)