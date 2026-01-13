#  SPDX-License-Identifier: GPL-3.0-or-later

from PyQt6.QtWidgets import QMessageBox


def show_error_and_raise(message):
    """Show an error message and raise an exception."""
    QMessageBox.critical(None, "Error", message)
    raise ValueError(message)


def confirm_execute(command=None):
    """Show confirmation dialog for executing a command."""
    if command:
        reply = QMessageBox.question(
            None,
            "Confirmation",
            f'Are you sure you want to execute "{command}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes


def confirm_exit():
    """Show confirmation dialog for exiting the application"""
    reply = QMessageBox.question(
        None,
        "Exit Confirmation",
        "Are you sure you want to exit?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return reply == QMessageBox.StandardButton.Yes
