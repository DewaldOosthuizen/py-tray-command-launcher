"""
Utility functions for py-tray-command-launcher.

This module provides utility functions used throughout the application.
"""

import os
from typing import Dict, Any
from PyQt6.QtWidgets import QMessageBox

from core.config_manager import config_manager, ConfigurationError


def load_commands() -> Dict[str, Any]:
    """
    Load commands from the configuration manager.

    This is a compatibility function that uses the ConfigManager under the hood,
    but maintains the same interface as the old load_commands function.

    Returns:
        Dictionary containing command configuration

    Raises:
        ValueError: If loading the configuration fails
    """
    try:
        return config_manager.get_commands()
    except ConfigurationError as e:
        message = str(e)
        QMessageBox.critical(None, "Error", message)
        raise ValueError(message)


def save_commands(commands: Dict[str, Any]) -> None:
    """
    Save commands using the configuration manager.

    Args:
        commands: Dictionary containing command configuration

    Raises:
        ValueError: If saving the configuration fails
    """
    try:
        config_manager.save_commands(commands)
    except ConfigurationError as e:
        message = str(e)
        QMessageBox.critical(None, "Error", message)
        raise ValueError(message)


def show_error_message(title: str, message: str) -> None:
    """
    Show an error message dialog.

    Args:
        title: Title of the error dialog
        message: Error message to display
    """
    QMessageBox.critical(None, title, message)


def show_info_message(title: str, message: str) -> None:
    """
    Show an information message dialog.

    Args:
        title: Title of the info dialog
        message: Information message to display
    """
    QMessageBox.information(None, title, message)


def show_warning_message(title: str, message: str) -> None:
    """
    Show a warning message dialog.

    Args:
        title: Title of the warning dialog
        message: Warning message to display
    """
    QMessageBox.warning(None, title, message)


def get_base_dir() -> str:
    """
    Get the base directory of the application.

    Returns:
        Path to the base directory
    """
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
