# SPDX-License-Identifier: GPL-3.0-or-later

"""
CommandManagerDialog — Full CRUD dialog for managing commands and groups.

Features:
  • QTreeWidget mirroring the group/command hierarchy
  • Add / Edit / Delete / Move-Up / Move-Down toolbar actions
  • Live menu rebuild on Save (no app restart required)
  • Save button disabled while any QProcess is running
"""

import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPushButton,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from ui.dialog_conventions import (
    configure_dialog_layout,
    responsive_dialog_size,
    responsive_minimum_width,
)
from utils.dialogs import confirm_action, show_info, show_warning

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command form dialog (shared by Add and Edit)
# ---------------------------------------------------------------------------


class _CommandFormDialog(QDialog):
    """Simple form to create or edit a single command."""

    def __init__(self, groups: list[str], initial: dict | None = None, parent=None):
        super().__init__(parent)
        initial = initial or {}
        self.setWindowTitle("Add Command" if not initial else "Edit Command")
        responsive_minimum_width(self, 400)

        layout = QVBoxLayout(self)
        configure_dialog_layout(layout)
        form_box = QGroupBox("Command Details")
        form = QFormLayout(form_box)
        form.setSpacing(8)

        # Group
        self._group_combo = QComboBox()
        self._group_combo.addItems(groups)
        self._group_combo.setEditable(True)
        current_group = initial.get("group", groups[0] if groups else "")
        idx = self._group_combo.findText(current_group)
        if idx >= 0:
            self._group_combo.setCurrentIndex(idx)
        else:
            self._group_combo.setCurrentText(current_group)
        form.addRow("Group:", self._group_combo)

        # Name
        self._name_edit = QLineEdit(initial.get("label", ""))
        form.addRow("Name:", self._name_edit)

        # Command
        self._cmd_edit = QLineEdit(initial.get("command", ""))
        form.addRow("Command:", self._cmd_edit)

        # Icon
        self._icon_edit = QLineEdit(initial.get("icon", ""))
        self._icon_edit.setPlaceholderText("Optional path/URL")
        form.addRow("Icon:", self._icon_edit)

        layout.addWidget(form_box)

        # Options
        opts_box = QGroupBox("Options")
        opts_layout = QVBoxLayout(opts_box)
        self._show_output_check = QCheckBox("Show Output")
        self._show_output_check.setChecked(initial.get("showOutput", False))
        self._confirm_check = QCheckBox("Confirm Before Execution")
        self._confirm_check.setChecked(initial.get("confirm", False))
        self._prompt_check = QCheckBox("Prompt for Input")
        self._prompt_edit = QLineEdit(initial.get("prompt", ""))
        self._prompt_edit.setPlaceholderText("Prompt text…")
        self._prompt_edit.setEnabled(initial.get("prompt") is not None)
        self._prompt_check.setChecked(initial.get("prompt") is not None)
        self._prompt_check.toggled.connect(lambda c: self._prompt_edit.setEnabled(c))
        opts_layout.addWidget(self._show_output_check)
        opts_layout.addWidget(self._confirm_check)
        opts_layout.addWidget(self._prompt_check)
        opts_layout.addWidget(self._prompt_edit)
        layout.addWidget(opts_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        accept_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if accept_button is None or cancel_button is None:
            raise RuntimeError("Command form could not create OK and Cancel buttons")
        accept_button.setDefault(True)
        cancel_button.setDefault(False)
        cancel_button.setAutoDefault(False)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setTabOrder(self._group_combo, self._name_edit)
        self.setTabOrder(self._name_edit, self._cmd_edit)
        self.setTabOrder(self._cmd_edit, self._icon_edit)
        self.setTabOrder(self._icon_edit, self._show_output_check)
        self.setTabOrder(self._show_output_check, self._confirm_check)
        self.setTabOrder(self._confirm_check, self._prompt_check)
        self.setTabOrder(self._prompt_check, self._prompt_edit)
        self.setTabOrder(self._prompt_edit, accept_button)
        self.setTabOrder(accept_button, cancel_button)
        self._group_combo.setFocus()

    def _validate_and_accept(self):
        if not self._group_combo.currentText().strip():
            show_warning(self, "Error", "Group is required.")
            return
        if not self._name_edit.text().strip():
            show_warning(self, "Error", "Name is required.")
            return
        if not self._cmd_edit.text().strip():
            show_warning(self, "Error", "Command is required.")
            return
        self.accept()

    def result_data(self) -> dict:
        data = {
            "group": self._group_combo.currentText().strip(),
            "label": self._name_edit.text().strip(),
            "command": self._cmd_edit.text().strip(),
            "showOutput": self._show_output_check.isChecked(),
            "confirm": self._confirm_check.isChecked(),
        }
        if self._icon_edit.text().strip():
            data["icon"] = self._icon_edit.text().strip()
        if self._prompt_check.isChecked() and self._prompt_edit.text().strip():
            data["prompt"] = self._prompt_edit.text().strip()
        return data


# ---------------------------------------------------------------------------
# CommandManagerDialog
# ---------------------------------------------------------------------------


class CommandManagerDialog(QDialog):
    """CRUD dialog for commands — no app restart required on save."""

    def __init__(self, services, running_processes: dict, parent=None):
        """
        Args:
            services: AppServices instance.
            running_processes: Reference to TrayApp's running-process dict.
        """
        super().__init__(parent)
        self._services = services
        self._running = running_processes
        self.setWindowTitle("Manage Commands")
        layout = QVBoxLayout(self)
        configure_dialog_layout(layout)
        responsive_dialog_size(self, preferred=(900, 650), minimum=(700, 500))

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_command)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_command)
        del_btn = QPushButton("Delete")
        del_btn.clicked.connect(self._delete_command)
        up_btn = QPushButton("▲")
        up_btn.setToolTip("Move Up")
        up_btn.clicked.connect(self._move_up)
        down_btn = QPushButton("▼")
        down_btn.setToolTip("Move Down")
        down_btn.clicked.connect(self._move_down)

        for btn in (add_btn, edit_btn, del_btn, up_btn, down_btn):
            toolbar.addWidget(btn)

        layout.addWidget(toolbar)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Name", "Command", "Options"])
        self._tree.header().setStretchLastSection(False)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree)
        tab_widgets = (add_btn, edit_btn, del_btn, up_btn, down_btn, self._tree)
        for current, following in zip(tab_widgets[:-1], tab_widgets[1:], strict=True):
            self.setTabOrder(current, following)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is None or cancel_btn is None:
            raise RuntimeError("Command manager could not create Save and Cancel buttons")
        self._save_btn = save_button
        self._save_btn.setText("Save && Rebuild Menu")
        self._save_btn.setDefault(True)
        cancel_btn.setDefault(False)
        cancel_btn.setAutoDefault(False)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setTabOrder(self._tree, self._save_btn)
        self.setTabOrder(self._save_btn, cancel_btn)

        # Disable Save while processes are running; poll every second so the
        # button re-enables automatically once all processes finish.
        self._update_save_btn()
        self._save_btn_timer = QTimer(self)
        self._save_btn_timer.setInterval(1000)
        self._save_btn_timer.timeout.connect(self._update_save_btn)
        self._save_btn_timer.start()

        self._load_tree()
        self._tree.setFocus()

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _load_tree(self):
        self._tree.clear()
        commands = self._services.config_manager.get_commands()
        for group_name, group_data in commands.items():
            if not isinstance(group_data, dict):
                continue
            group_item = QTreeWidgetItem([group_name, "", ""])
            group_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "group", "name": group_name})
            self._tree.addTopLevelItem(group_item)
            self._populate_group(group_item, group_name, group_data)
            group_item.setExpanded(True)

    def _populate_group(self, parent_item: QTreeWidgetItem, group_name: str, data: dict):
        for label, item in data.items():
            if label == "icon":
                continue
            if isinstance(item, dict) and "command" in item:
                flags = []
                if item.get("showOutput"):
                    flags.append("output")
                if item.get("confirm"):
                    flags.append("confirm")
                if item.get("prompt"):
                    flags.append("prompt")
                child = QTreeWidgetItem(
                    [
                        label,
                        item.get("command", ""),
                        ", ".join(flags),
                    ]
                )
                child.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "type": "command",
                        "group": group_name,
                        "label": label,
                        "data": item,
                    },
                )
                parent_item.addChild(child)
            elif isinstance(item, dict):
                sub_item = QTreeWidgetItem([label, "", ""])
                sub_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "type": "group",
                        "name": f"{group_name}.{label}",
                    },
                )
                parent_item.addChild(sub_item)
                self._populate_group(sub_item, f"{group_name}.{label}", item)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_group(commands: dict, group_path: str):
        """Resolve a dot-separated group path into the dict that holds the group
        and the group's key within that dict.

        For a top-level group the container is the commands dict itself. If the
        path does not exist, or any segment is missing / not a dict, returns
        (None, None).
        """
        if not group_path:
            return None, None
        parts = group_path.split(".")
        parent = commands
        for part in parts[:-1]:
            if not isinstance(parent, dict) or part not in parent:
                return None, None
            parent = parent[part]
            if not isinstance(parent, dict):
                return None, None
        return parent, parts[-1]

    def _collect_group_paths(self, commands: dict, prefix: str = "") -> list[str]:
        """Return every group path present in the configuration, including nested
        subgroups, as dot-separated strings (e.g. 'Nested.Sub.Deep').

        A key is treated as a group when its value is a dict that does not have
        a top-level 'command' key (which would make it a command entry).
        """
        paths = []
        for key, value in commands.items():
            if key == "icon":
                continue
            full = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict) and "command" not in value:
                paths.append(full)
                paths.extend(self._collect_group_paths(value, full))
        return paths

    def _add_command(self):
        commands = self._services.config_manager.get_commands()
        groups = self._collect_group_paths(commands)
        dlg = _CommandFormDialog(groups, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result_data()
            group = d["group"]
            cmd_data = {k: v for k, v in d.items() if k not in ("group", "label")}

            new_parent, new_key = self._resolve_group(commands, group)
            if new_parent is not None and new_key in new_parent:
                # Path exists (top-level or nested): add the command to the
                # existing subgroup, preserving its unrelated sibling entries.
                new_parent[new_key][d["label"]] = cmd_data
            else:
                # New group path: create any missing intermediate groups, then
                # the leaf group, and insert the command inside it.
                parts = group.split(".")
                parent = commands
                for part in parts[:-1]:
                    if part not in parent or not isinstance(parent.get(part), dict):
                        parent[part] = {}
                    parent = parent[part]
                new_parent = parent.setdefault(parts[-1], {})
                new_parent[d["label"]] = cmd_data
            self._services.config_manager.save_commands(commands)
            self._load_tree()

    def _edit_command(self):
        item = self._tree.currentItem()
        if not item:
            show_info(self, "Edit", "Select a command to edit.")
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if meta.get("type") != "command":
            show_info(self, "Edit", "Select a command (not a group) to edit.")
            return

        commands = self._services.config_manager.get_commands()
        group_path = meta["group"]
        label = meta["label"]
        item_data = meta.get("data", {})
        initial = {"group": group_path, "label": label, **item_data}
        dlg = _CommandFormDialog(self._collect_group_paths(commands), initial=initial, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result_data()
            new_group = d["group"]
            new_label = d["label"]
            cmd_data = {k: v for k, v in d.items() if k not in ("group", "label")}

            # Resolve the command's current location using its full dot-separated
            # group path so that nested groups (e.g. 'Nested.Sub') resolve to the
            # subgroup that directly holds the command.
            old_parent, old_key = self._resolve_group(commands, group_path)
            if (
                old_parent is None
                or old_key is None
                or not isinstance(old_parent, dict)
                or old_key not in old_parent
                or not isinstance(old_parent[old_key], dict)
                or label not in old_parent[old_key]
            ):
                show_warning(
                    self,
                    "Edit",
                    f"Could not locate command '{label}' under group '{group_path}'.",
                )
                return

            # Remove only the labelled command. The surrounding subgroup (and its
            # metadata such as icon) and all unrelated siblings are preserved.
            del old_parent[old_key][label]

            # Resolve (or create) the parent container for the new group path.
            new_parent, new_key = self._resolve_group(commands, new_group)
            if new_parent is not None and new_key in new_parent:
                # Existing group: add the command to the existing subgroup,
                # preserving the subgroup's unrelated sibling entries.
                new_parent[new_key][new_label] = cmd_data
            else:
                # New group path: create any missing intermediate groups, then
                # the leaf group, and insert the command inside it.
                parts = new_group.split(".")
                parent = commands
                for part in parts[:-1]:
                    if part not in parent or not isinstance(parent.get(part), dict):
                        parent[part] = {}
                    parent = parent[part]
                new_parent = parent.setdefault(parts[-1], {})
                new_parent[new_label] = cmd_data

            self._services.config_manager.save_commands(commands)
            self._load_tree()

    def _delete_command(self):
        item = self._tree.currentItem()
        if not item:
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        name = meta.get("label") or meta.get("name", "")

        if not confirm_action(self, "Confirm Delete", f"Delete '{name}'?"):
            return

        commands = self._services.config_manager.get_commands()
        if meta.get("type") == "command":
            group_path = meta["group"]
            label = meta["label"]

            # The command is stored one level deeper than the group path: the
            # group path resolves to a (parent, key) pair whose value is the
            # subgroup that directly holds the command.
            parent, key = self._resolve_group(commands, group_path)
            if (
                parent is not None
                and isinstance(parent, dict)
                and key is not None
                and key in parent
                and isinstance(parent[key], dict)
                and label in parent[key]
            ):
                del parent[key][label]
        elif meta.get("type") == "group":
            group_path = meta["name"]
            parts = group_path.split(".")
            if len(parts) == 1:
                # Top-level group
                if parts[0] in commands:
                    del commands[parts[0]]
            else:
                # Nested subgroup: delete only the selected sub-key in its parent
                parent, _ = self._resolve_group(commands, group_path)
                if parent is not None and isinstance(parent, dict) and parts[-1] in parent:
                    del parent[parts[-1]]

        self._services.config_manager.save_commands(commands)
        self._load_tree()

    def _move_up(self):
        """Move the selected command one position up within its group."""
        self._move_item(-1)

    def _move_down(self):
        """Move the selected command one position down within its group."""
        self._move_item(1)

    def _move_item(self, direction: int):
        """Move the selected command one position up/down within its parent
        subgroup. Works for both top-level and nested subgroup paths."""
        item = self._tree.currentItem()
        if not item:
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if meta.get("type") != "command":
            return

        commands = self._services.config_manager.get_commands()
        group_path = meta["group"]
        label = meta["label"]

        # Resolve the command's parent subgroup so that nested commands (e.g.
        # group 'Nested.Sub', label 'GrandChild') are moved inside 'Sub'.
        parent, key = self._resolve_group(commands, group_path)
        if parent is None or key is None or not isinstance(parent, dict):
            return

        group = parent[key]
        keys = [k for k in group if k != "icon"]
        if label not in keys:
            return

        idx = keys.index(label)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(keys):
            return

        # Rebuild the subgroup preserving icon and unrelated sibling entries.
        icon_val = group.get("icon")
        reordered = {}
        if icon_val is not None:
            reordered["icon"] = icon_val
        keys.insert(new_idx, keys.pop(idx))
        for k in keys:
            reordered[k] = group[k]

        parent[key] = reordered
        self._services.config_manager.save_commands(commands)
        self._load_tree()

    # ------------------------------------------------------------------
    # Save & helpers
    # ------------------------------------------------------------------

    def _save(self):
        """Rebuild tray menu from updated commands.json."""
        if self._running:
            show_warning(
                self,
                "Processes Running",
                "Cannot rebuild the menu while commands are running.\nPlease wait for them to finish.",
            )
            return
        self._services.reload_commands(rebuild_menu=True)
        self.accept()

    def closeEvent(self, event):
        """Stop the save-button polling timer when the dialog is closed."""
        self._save_btn_timer.stop()
        super().closeEvent(event)

    def _update_save_btn(self):
        self._save_btn.setEnabled(not bool(self._running))
