#  SPDX-License-Identifier: GPL-3.0-or-later

import os
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QPushButton
from PyQt6.QtCore import Qt


class CommandSearch:
    """Provides search functionality for commands."""

    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def show_dialog(self):
        """Show a dialog to search for commands."""
        dialog = QDialog()
        dialog.setWindowTitle("Search Commands")
        layout = QVBoxLayout()

        search_box = QLineEdit()
        search_box.setPlaceholderText("Type to search...")
        layout.addWidget(search_box)

        command_list = QListWidget()
        layout.addWidget(command_list)

        execute_button = QPushButton("Execute")
        layout.addWidget(execute_button)

        dialog.setLayout(layout)

        # Populate the list with all commands
        all_commands = self.app.get_all_commands()
        for cmd_info in all_commands:
            command_list.addItem(f"{cmd_info['group']} → {cmd_info['label']}")

        # Filter as user types
        def filter_commands():
            search_text = search_box.text().lower()
            for i in range(command_list.count()):
                item = command_list.item(i)
                if item is not None:
                    item.setHidden(search_text not in item.text().lower())

        search_box.textChanged.connect(filter_commands)

        # Execute the selected command
        def on_execute():
            current_item = command_list.currentItem()
            if current_item is not None:
                selected = current_item.text()
                for cmd_info in all_commands:
                    if f"{cmd_info['group']} → {cmd_info['label']}" == selected:
                        self.app.execute(
                            cmd_info["label"],
                            cmd_info["command"],
                            cmd_info["confirm"],
                            cmd_info["showOutput"],
                            cmd_info.get("prompt"),
                        )
                        dialog.accept()
                        break

        execute_button.clicked.connect(on_execute)
        command_list.itemDoubleClicked.connect(lambda: on_execute())

        # Set focus to search box
        search_box.setFocus()

        # Set dialog size
        dialog.resize(500, 400)

        dialog.exec()
