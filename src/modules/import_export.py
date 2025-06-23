import os
import json
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QInputDialog,
)
from core.config_manager import config_manager

from utils.utils import load_commands


class ImportExport:
    """Handles import and export operations for commands."""

    def __init__(self, tray_app):
        """Initialize with a reference to the TrayApp."""
        self.tray_app = tray_app

    def export_command_group(self):
        """Export a command group to a JSON file."""
        # Get list of command groups
        commands = config_manager.get_commands()
        groups = list(commands.keys())

        if not groups:
            QMessageBox.warning(
                None, "Export Failed", "No command groups found to export."
            )
            return

        # Let user select a group
        group, ok = QInputDialog.getItem(
            None, "Select Group", "Choose a command group to export:", groups, 0, False
        )

        if ok and group:
            # Get export file path
            file_path, _ = QFileDialog.getSaveFileName(
                None,
                "Export Command Group",
                os.path.expanduser("~"),
                "JSON Files (*.json)",
            )

            if file_path:
                # Ensure file has .json extension
                if not file_path.endswith(".json"):
                    file_path += ".json"

                # Export the group
                success = config_manager.export_command_group(group, file_path)

                if success:
                    QMessageBox.information(
                        None,
                        "Export Successful",
                        f"Command group '{group}' has been exported to:\n{file_path}",
                    )
                else:
                    QMessageBox.warning(
                        None,
                        "Export Failed",
                        f"Failed to export command group '{group}'.",
                    )

    def import_command_group(self):
        """Import a command group from a JSON file."""
        # Get import file path
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Import Command Group", os.path.expanduser("~"), "JSON Files (*.json)"
        )

        if file_path:
            # Check for overwrite
            overwrite = (
                QMessageBox.question(
                    None,
                    "Import Options",
                    "Overwrite existing groups with the same name?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )

            # Import the group
            success = config_manager.import_command_group(file_path, overwrite)

            if success:
                QMessageBox.information(
                    None,
                    "Import Successful",
                    "Command group has been imported successfully.",
                )
                self.tray_app.reload_commands()
            else:
                QMessageBox.warning(
                    None,
                    "Import Failed",
                    "Failed to import command group. Check for conflicts or file format issues.",
                )
