import os
import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                           QListWidget, QPushButton, QFileDialog, QMessageBox)

from utils import load_commands

class ImportExport:
    """Handles importing and exporting command groups."""
    
    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def export_command_group(self):
        """Export a command group to a JSON file."""
        commands = load_commands()
        
        # Create a dialog to select a group
        dialog = QDialog()
        dialog.setWindowTitle("Export Command Group")
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Select a group to export:"))
        
        list_widget = QListWidget()
        list_widget.addItems(commands.keys())
        layout.addWidget(list_widget)
        
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        export_btn = QPushButton("Export")
        
        cancel_btn.clicked.connect(dialog.reject)
        
        def do_export():
            current_item = list_widget.currentItem()
            if not current_item:
                QMessageBox.critical(dialog, "Error", "Please select a group to export!")
                return
            
            group_name = current_item.text()
            
            # Get export file path
            file_path, _ = QFileDialog.getSaveFileName(
                dialog, "Export Group", f"{group_name}.json", "JSON Files (*.json)"
            )
            
            if file_path:
                try:
                    # Export the group to the file
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump({group_name: commands[group_name]}, f, indent=4)
                    
                    QMessageBox.information(None, "Export", f"Successfully exported group '{group_name}' to:\n{file_path}")
                    dialog.accept()
                except Exception as e:
                    QMessageBox.critical(dialog, "Export Failed", f"Failed to export group: {e}")
        
        export_btn.clicked.connect(do_export)
        
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(export_btn)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.resize(400, 300)
        dialog.exec()
    
    def import_command_group(self):
        """Import a command group from a JSON file."""
        # Get import file path
        file_path, _ = QFileDialog.getOpenFileName(
            None, "Import Group", "", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # Read the import file
                with open(file_path, "r", encoding="utf-8") as f:
                    import_data = json.load(f)
                
                if not isinstance(import_data, dict):
                    QMessageBox.critical(None, "Import Failed", "Invalid import file format!")
                    return
                
                # Get current commands
                commands = load_commands()
                
                # Check for conflicts
                conflicts = []
                for group_name in import_data.keys():
                    if group_name in commands:
                        conflicts.append(group_name)
                
                # Handle conflicts
                if conflicts:
                    reply = QMessageBox.question(
                        None, "Import Conflicts",
                        f"The following groups already exist:\n{', '.join(conflicts)}\n\nDo you want to overwrite them?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.No:
                        return
                
                # Merge the import data with current commands
                for group_name, group_data in import_data.items():
                    commands[group_name] = group_data
                
                # Save the updated commands
                self.app.save_commands(commands)
                
                QMessageBox.information(None, "Import", "Successfully imported command groups!")
                
                # Reload the menu
                self.app.restart_app()
                
            except Exception as e:
                QMessageBox.critical(None, "Import Failed", f"Failed to import group: {e}")