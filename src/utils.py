from email import message
import os
import json
from PyQt6.QtWidgets import QMessageBox

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "../config/commands.json")

def load_commands():
    """Load commands from the JSON configuration file."""
    try:
        # Open the configuration file in read mode
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        message = f"Failed to load commands from {CONFIG_FILE}."
        QMessageBox.critical(None, "Error", message)
        raise ValueError(message)
