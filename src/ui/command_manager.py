#  SPDX-License-Identifier: GPL-3.0-or-later

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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.config_manager import config_manager

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
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form_box = QGroupBox("Command Details")
        form = QFormLayout(form_box)

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
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        if not self._group_combo.currentText().strip():
            QMessageBox.warning(self, "Error", "Group is required.")
            return
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Error", "Name is required.")
            return
        if not self._cmd_edit.text().strip():
            QMessageBox.warning(self, "Error", "Command is required.")
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
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

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

        # Dialog buttons
        self._save_btn = QPushButton("Save && Rebuild Menu")
        self._save_btn.setDefault(True)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self._save_btn.clicked.connect(self._save)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        # Disable Save while processes are running; poll every second so the
        # button re-enables automatically once all processes finish.
        self._update_save_btn()
        self._save_btn_timer = QTimer(self)
        self._save_btn_timer.setInterval(1000)
        self._save_btn_timer.timeout.connect(self._update_save_btn)
        self._save_btn_timer.start()

        self._load_tree()

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _load_tree(self):
        self._tree.clear()
        commands = config_manager.get_commands()
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
                child = QTreeWidgetItem([
                    label,
                    item.get("command", ""),
                    ", ".join(flags),
                ])
                child.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "command",
                    "group": group_name,
                    "label": label,
                    "data": item,
                })
                parent_item.addChild(child)
            elif isinstance(item, dict):
                sub_item = QTreeWidgetItem([label, "", ""])
                sub_item.setData(0, Qt.ItemDataRole.UserRole, {
                    "type": "group",
                    "name": f"{group_name}.{label}",
                })
                parent_item.addChild(sub_item)
                self._populate_group(sub_item, f"{group_name}.{label}", item)

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_command(self):
        commands = config_manager.get_commands()
        groups = list(commands.keys())
        dlg = _CommandFormDialog(groups, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result_data()
            group = d["group"]
            cmd_data = {k: v for k, v in d.items() if k not in ("group", "label")}
            if group not in commands:
                commands[group] = {}
            commands[group][d["label"]] = cmd_data
            config_manager.save_commands(commands)
            self._load_tree()

    def _edit_command(self):
        item = self._tree.currentItem()
        if not item:
            QMessageBox.information(self, "Edit", "Select a command to edit.")
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if meta.get("type") != "command":
            QMessageBox.information(self, "Edit", "Select a command (not a group) to edit.")
            return

        commands = config_manager.get_commands()
        group_name = meta["group"]
        label = meta["label"]
        item_data = meta.get("data", {})

        initial = {"group": group_name, "label": label, **item_data}
        dlg = _CommandFormDialog(list(commands.keys()), initial=initial, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result_data()
            new_group = d["group"]
            new_label = d["label"]
            cmd_data = {k: v for k, v in d.items() if k not in ("group", "label")}

            # Remove from old location
            if group_name in commands and label in commands[group_name]:
                del commands[group_name][label]

            # Insert at new location
            if new_group not in commands:
                commands[new_group] = {}
            commands[new_group][new_label] = cmd_data

            config_manager.save_commands(commands)
            self._load_tree()

    def _delete_command(self):
        item = self._tree.currentItem()
        if not item:
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        name = meta.get("label") or meta.get("name", "")

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        commands = config_manager.get_commands()
        if meta.get("type") == "command":
            group_name = meta["group"]
            label = meta["label"]
            if group_name in commands and label in commands[group_name]:
                del commands[group_name][label]
        elif meta.get("type") == "group":
            group_path = meta["name"]
            parts = group_path.split(".")
            if len(parts) == 1:
                # Top-level group
                if parts[0] in commands:
                    del commands[parts[0]]
            else:
                # Nested subgroup: delete only the selected sub-key in its parent
                parent = commands
                for part in parts[:-1]:
                    parent = parent.get(part)
                    if not isinstance(parent, dict):
                        parent = None
                        break
                if isinstance(parent, dict) and parts[-1] in parent:
                    del parent[parts[-1]]

        config_manager.save_commands(commands)
        self._load_tree()

    def _move_up(self):
        """Move the selected command one position up within its group."""
        self._move_item(-1)

    def _move_down(self):
        """Move the selected command one position down within its group."""
        self._move_item(1)

    def _move_item(self, direction: int):
        item = self._tree.currentItem()
        if not item:
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if meta.get("type") != "command":
            return

        commands = config_manager.get_commands()
        group_name = meta["group"]
        label = meta["label"]

        if group_name not in commands:
            return

        group = commands[group_name]
        keys = [k for k in group if k != "icon"]
        if label not in keys:
            return

        idx = keys.index(label)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(keys):
            return

        # Rebuild group preserving icon
        icon_val = group.get("icon")
        reordered = {}
        if icon_val is not None:
            reordered["icon"] = icon_val
        keys.insert(new_idx, keys.pop(idx))
        for k in keys:
            reordered[k] = group[k]
        commands[group_name] = reordered

        config_manager.save_commands(commands)
        self._load_tree()

    # ------------------------------------------------------------------
    # Save & helpers
    # ------------------------------------------------------------------

    def _save(self):
        """Rebuild tray menu from updated commands.json."""
        if self._running:
            QMessageBox.warning(
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
