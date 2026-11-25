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


def _parse_group_path(group_text: str) -> tuple[str, ...]:
    """Split a typed group string on the `` / `` separator into non-empty components.

    Args:
        group_text: The user-typed group path, with `` / `` separating each
            path component.

    Returns:
        An ordered tuple of the path components, with any empty components
        removed.
    """
    return tuple(component for component in group_text.split(" / ") if component)


def _collect_group_paths(commands: dict) -> list[tuple[str, ...]]:
    """Collect every existing group path as an ordered tuple of component keys.

    Mirrors ``_command_groups`` in ``src.ui.command_manager``: walks the
    command map and returns every group path (top-level and nested) as an
    ordered tuple of component keys, skipping the ``"icon"`` key and leaf
    command objects.

    Args:
        commands: Root command configuration mapping.

    Returns:
        Paths for top-level and nested groups in configuration order.
    """
    groups = []

    def visit(data: dict, path: tuple[str, ...]):
        groups.append(path)
        for key, value in data.items():
            if key != "icon" and isinstance(value, dict) and "command" not in value:
                visit(value, (*path, key))

    for name, data in commands.items():
        if isinstance(data, dict):
            visit(data, (name,))
    return groups


def _validate_group_path(commands: dict, group_path: tuple[str, ...]) -> bool:
    """Validate a resolved group path for command creation.

    Rejects empty components, rejects a final component that already holds a
    command in the resolved parent, and allows missing intermediate groups
    because they are auto-created during the write.

    Args:
        commands: Root command configuration mapping.
        group_path: Ordered group keys from the root to the target subgroup
            (a closed tuple of component keys).

    Returns:
        True when the path is usable; False when it contains an empty
        component, a non-mapping intermediate, or a final component that is a
        command leaf.
    """
    if not group_path or any(not component for component in group_path):
        return False

    target = commands
    for index, component in enumerate(group_path):
        if component not in target:
            # Missing intermediate or leaf group: acceptable for
            # auto-creation, or the leaf is a genuine new group.
            continue
        candidate = target[component]
        if not isinstance(candidate, dict):
            return False
        # An intermediate component must be a group holder, not a command leaf:
        # a component that already holds a command cannot contain a subgroup.
        if index < len(group_path) - 1 and "command" in candidate:
            return False
        # The final component must not already hold a command.
        if index == len(group_path) - 1 and "command" in candidate:
            return False
        target = candidate

    return True


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
        group_layout.addWidget(QLabel("Group path:"))
        group_combo = QComboBox()

        commands = self.services.config_manager.get_commands()
        for path in _collect_group_paths(commands):
            if path:  # skip the root grouping
                group_combo.addItem(" / ".join(path), path)
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
            name = name_edit.text()
            command = cmd_edit.toPlainText()

            if not name or not command.strip():
                QMessageBox.critical(dialog, "Error", "Name and Command are required!")
                return

            # Resolve: itemData when an existing item is selected, else parse typed text.
            current_index = group_combo.currentIndex()
            selected_path = (
                group_combo.itemData(current_index)
                if current_index >= 0
                else _parse_group_path(group_combo.currentText())
            )

            # Load the latest commands and validate the group path before writing.
            commands = self.services.config_manager.get_commands()
            if not _validate_group_path(commands, selected_path):
                QMessageBox.critical(
                    dialog,
                    "Error",
                    "Invalid group path. Intermediate groups are created "
                    "automatically; the final component must not clash with an "
                    "existing command.",
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

            # Traverse the resolved path, auto-creating intermediate groups, and merge
            # the command into the correct subgroup (no new top-level key).
            target = commands
            for component in selected_path:
                if component not in target:
                    # Missing intermediate group: create it so the path resolves.
                    target[component] = {}
                elif "command" in target[component]:
                    # The selected path reaches an existing command leaf, which
                    # cannot hold a subgroup. Validation already rejected this
                    # case, but guard against it so a stale path can never
                    # corrupt the configuration.
                    return
                target = target[component]
            target[name] = cmd_data

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
