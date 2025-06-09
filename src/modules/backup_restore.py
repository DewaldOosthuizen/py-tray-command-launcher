import os
import json
import shutil
import datetime
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QHBoxLayout, QPushButton, QMessageBox, QFileDialog

from utils import load_commands

class BackupRestore:
    """Manages backup and restore functionality for commands."""
    
    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def backup_commands(self):
        """Backup the commands.json file."""
        commands_file = os.path.join(self.BASE_DIR, "../config/commands.json")
        backup_dir = os.path.join(self.BASE_DIR, "../config/backups")
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Generate backup filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"commands_{timestamp}.json")
        
        try:
            # Copy the commands file to the backup location
            shutil.copy2(commands_file, backup_file)
            QMessageBox.information(None, "Backup", f"Successfully backed up commands to:\n{backup_file}")
        except Exception as e:
            QMessageBox.critical(None, "Backup Failed", f"Failed to backup commands: {e}")
    
    def restore_commands(self):
        """Restore the commands.json file from a backup."""
        backup_dir = os.path.join(self.BASE_DIR, "../config/backups")
        
        # Check if backup directory exists
        if not os.path.exists(backup_dir):
            QMessageBox.critical(None, "Restore Failed", "No backups found!")
            return
        
        # Get list of backup files
        backup_files = [f for f in os.listdir(backup_dir) if f.startswith("commands_") and f.endswith(".json")]
        
        if not backup_files:
            QMessageBox.critical(None, "Restore Failed", "No backup files found!")
            return
        
        # Sort backup files by name (timestamp) in descending order
        backup_files.sort(reverse=True)
        
        # Create a dialog to select a backup
        dialog = QDialog()
        dialog.setWindowTitle("Restore Commands")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Select a backup to restore:"))
        
        list_widget = QListWidget()
        for file in backup_files:
            # Extract timestamp and format it
            timestamp = file.replace("commands_", "").replace(".json", "")
            formatted_date = f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
            list_widget.addItem(f"{formatted_date} - {file}")
        
        layout.addWidget(list_widget)
        
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        restore_btn = QPushButton("Restore")
        
        cancel_btn.clicked.connect(dialog.reject)
        
        def do_restore():
            current_item = list_widget.currentItem()
            if not current_item:
                QMessageBox.critical(dialog, "Error", "Please select a backup to restore!")
                return
            
            selected = current_item.text()
            backup_file = selected.split(" - ")[1]
            
            if QMessageBox.question(
                dialog, "Confirm Restore", 
                f"Are you sure you want to restore from:\n{backup_file}?\n\nThis will overwrite your current commands.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                try:
                    commands_file = os.path.join(self.BASE_DIR, "../config/commands.json")
                    backup_path = os.path.join(backup_dir, backup_file)
                    
                    # Make a backup of the current file before restoring
                    self.backup_commands()
                    
                    # Copy the backup file to the commands file
                    shutil.copy2(backup_path, commands_file)
                    
                    QMessageBox.information(None, "Restore", "Successfully restored commands!")
                    
                    # Reload the menu
                    self.app.restart_app()
                    
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(dialog, "Restore Failed", f"Failed to restore commands: {e}")
        
        restore_btn.clicked.connect(do_restore)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(restore_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.resize(400, 300)
        dialog.exec()