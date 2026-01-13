#  SPDX-License-Identifier: GPL-3.0-or-later

import os
import json
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from utils.utils import load_commands


class CommandCreator:
    """Handles the creation of new commands via a GUI interface."""

    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def show_dialog(self):
        """Show a dialog to create a new command."""
        dialog = QDialog()
        dialog.setWindowTitle("Create New Command")
        layout = QVBoxLayout()

        # Group selection
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Group:"))
        group_combo = QComboBox()

        commands = load_commands()
        groups = list(commands.keys())
        group_combo.addItems(groups)
        group_combo.setEditable(True)
        group_layout.addWidget(group_combo)
        layout.addLayout(group_layout)

        # Command name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        name_edit = QLineEdit()
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)

        # Command
        cmd_layout = QHBoxLayout()
        cmd_layout.addWidget(QLabel("Command:"))
        cmd_edit = QLineEdit()
        cmd_layout.addWidget(cmd_edit)
        layout.addLayout(cmd_layout)

        # Icon selection
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(QLabel("Icon:"))
        icon_edit = QLineEdit()
        icon_edit.setText("")
        icon_layout.addWidget(icon_edit)
        browse_btn = QPushButton("Browse...")

        def browse_icon():
            file_path, _ = QFileDialog.getOpenFileName(
                dialog,
                "Select Icon",
                "",
                "Image Files (*.png *.jpg *.jpeg *.ico *.svg)",
            )
            if file_path:
                icon_edit.setText(file_path)

        browse_btn.clicked.connect(browse_icon)
        icon_layout.addWidget(browse_btn)
        layout.addLayout(icon_layout)

        # Options
        options_layout = QVBoxLayout()
        show_output_check = QCheckBox("Show Output")
        confirm_check = QCheckBox("Confirm Before Execution")
        prompt_check = QCheckBox("Prompt for Input")
        prompt_edit = QLineEdit()
        prompt_edit.setPlaceholderText("Enter prompt text...")
        prompt_edit.setEnabled(False)

        def toggle_prompt():
            prompt_edit.setEnabled(prompt_check.isChecked())

        prompt_check.stateChanged.connect(toggle_prompt)

        options_layout.addWidget(show_output_check)
        options_layout.addWidget(confirm_check)
        options_layout.addWidget(prompt_check)
        options_layout.addWidget(prompt_edit)
        layout.addLayout(options_layout)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        create_btn = QPushButton("Create")

        cancel_btn.clicked.connect(dialog.reject)

        def create_command():
            group = group_combo.currentText()
            name = name_edit.text()
            command = cmd_edit.text()

            if not group or not name or not command:
                QMessageBox.critical(
                    dialog, "Error", "Group, Name, and Command are required!"
                )
                return

            # Create command data
            cmd_data = {
                "command": command,
                "showOutput": show_output_check.isChecked(),
                "confirm": confirm_check.isChecked(),
            }

            if icon_edit.text():
                cmd_data["icon"] = icon_edit.text()

            if prompt_check.isChecked() and prompt_edit.text():
                cmd_data["prompt"] = prompt_edit.text()

            # Add the command to the config
            commands = load_commands()
            if group not in commands:
                commands[group] = {}

            commands[group][name] = cmd_data

            # Save the config
            self.app.save_commands(commands)

            # Reload the menu
            self.app.restart_app()

            dialog.accept()

        create_btn.clicked.connect(create_command)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(create_btn)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec()
