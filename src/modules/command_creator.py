# SPDX-License-Identifier: GPL-3.0-or-later

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class CommandCreator:
    """Create command entries through a dialog using injected AppServices.

    The dialog loads existing groups and captures a group, command name, and
    command string, plus optional icon, output, confirmation, and prompt
    settings. On creation it updates the command mapping, saves through the
    injected service, and requests a menu reload. See
    [the architecture guide](../../docs/architecture.md) and
    [the configuration reference](../../docs/configuration.md).
    """

    def __init__(self, services):
        """Initialize with the application service contract.

        Args:
            services: AppServices providing command configuration, save, and
                reload operations.
        """
        self.services = services

    def show_dialog(self):
        """Show the modal dialog for collecting and saving a command entry.

        The dialog captures the group, name, command, and optional command
        settings. A valid submission is saved through ``services`` and
        requests a menu rebuild; cancelling makes no configuration changes.

        Returns:
            None.

        Raises:
            Exceptions raised while loading, saving, or reloading commands are
            allowed to propagate from the injected services.
        """
        dialog = QDialog()
        dialog.setWindowTitle("Create New Command")
        layout = QVBoxLayout()

        # Group selection
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Group:"))
        group_combo = QComboBox()

        commands = self.services.config_manager.get_commands()
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
        cmd_edit = QPlainTextEdit()
        cmd_edit.setMinimumHeight(120)
        cmd_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
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
            command = cmd_edit.toPlainText()

            if not group or not name or not command.strip():
                QMessageBox.critical(dialog, "Error", "Group, Name, and Command are required!")
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
            commands = self.services.config_manager.get_commands()
            if group not in commands:
                commands[group] = {}

            commands[group][name] = cmd_data

            # Save the config
            self.services.save_commands(commands)

            # Rebuild the menu without restarting
            self.services.reload_commands(rebuild_menu=True)

            dialog.accept()

        create_btn.clicked.connect(create_command)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(create_btn)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec()
