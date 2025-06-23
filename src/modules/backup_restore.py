import os
import json
import shutil
import datetime
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QFileDialog,
    QInputDialog,
)
from core.config_manager import config_manager


class BackupRestore:
    """Handles backup and restore operations for commands."""

    def __init__(self, tray_app):
        """Initialize with a reference to the TrayApp."""
        self.tray_app = tray_app

    def backup_commands(self):
        """Create a backup of the current commands."""
        backup_file = config_manager.backup_commands()
        if backup_file:
            QMessageBox.information(
                None,
                "Backup Created",
                f"Commands backup created successfully at:\n{backup_file}",
            )
        else:
            QMessageBox.warning(
                None, "Backup Failed", "Failed to create commands backup."
            )

    def restore_commands(self):
        """Restore commands from a backup."""
        backups = config_manager.list_backups()

        if not backups:
            QMessageBox.information(None, "No Backups", "No command backups found.")
            return

        # Create a selection dialog
        items = [f"{date} - {os.path.basename(file)}" for file, date in backups]
        selection, ok = QInputDialog.getItem(
            None, "Select Backup", "Choose a backup to restore:", items, 0, False
        )

        if ok and selection:
            # Extract file path from selection
            index = items.index(selection)
            backup_file, _ = backups[index]

            # Confirm restore
            if (
                QMessageBox.question(
                    None,
                    "Confirm Restore",
                    f"Are you sure you want to restore from this backup?\n\n{selection}",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                # Perform restore
                success = config_manager.restore_from_backup(backup_file)

                if success:
                    QMessageBox.information(
                        None,
                        "Restore Successful",
                        "Commands have been restored from backup.",
                    )
                    self.tray_app.reload_commands()
                else:
                    QMessageBox.warning(
                        None,
                        "Restore Failed",
                        "Failed to restore commands from backup.",
                    )
