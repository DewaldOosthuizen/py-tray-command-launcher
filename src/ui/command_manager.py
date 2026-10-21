# SPDX-License-Identifier: GPL-3.0-or-later

"""
CommandManagerDialog — Full CRUD dialog for managing commands and groups.

Features:
  • QTreeWidget mirroring the group/command hierarchy
  • Add / Edit / Delete / Move-Up / Move-Down toolbar actions
  • Live menu rebuild on Save (no app restart required)
  • Save button disabled while any QProcess is running
"""

import json
import logging

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
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


def _resolve_group_path(commands: dict, group_path: tuple[str, ...]) -> dict | None:
    """Resolve exact group components without interpreting display separators.

    Args:
        commands: Root command configuration mapping.
        group_path: Ordered group keys from the root to the target mapping.

    Returns:
        The target group mapping, or None when a component is missing or not a mapping.
    """
    parent = commands
    for component in group_path:
        if not isinstance(parent, dict):
            return None
        parent = parent.get(component)
        if not isinstance(parent, dict):
            return None
    return parent


def _command_groups(commands: dict) -> list[tuple[str, ...]]:
    """Collect group paths as exact key-component tuples.

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


# ---------------------------------------------------------------------------
# Command form dialog (shared by Add and Edit)
# ---------------------------------------------------------------------------


class _CommandFormDialog(QDialog):
    """Simple form to create or edit a single command."""

    def __init__(
        self, groups: list[str | tuple[str, ...]], initial: dict | None = None, parent=None
    ):
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
        self._group_combo.setEditable(True)
        for group in groups:
            group_path = group if isinstance(group, tuple) else (group,)
            group_label = json.dumps(group_path, ensure_ascii=False)
            self._group_combo.addItem(group_label, group_path)
        current_path = initial.get("group_path")
        default_group = (
            json.dumps(groups[0], ensure_ascii=False)
            if groups and isinstance(groups[0], tuple)
            else (groups[0] if groups else "")
        )
        current_group = (
            json.dumps(current_path, ensure_ascii=False)
            if current_path
            else initial.get("group", default_group)
        )
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
        """Return normalized command fields and the selected exact group path."""
        current_group = self._group_combo.currentText().strip()
        current_index = self._group_combo.currentIndex()
        selected_path = self._group_combo.itemData(current_index) if current_index >= 0 else None
        group_path = (
            selected_path
            if selected_path and current_group == self._group_combo.itemText(current_index)
            else (current_group,)
        )
        data = {
            "group": current_group,
            "group_path": tuple(group_path),
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
        self._search_edit = QLineEdit()
        self._search_edit.setAccessibleName("Search commands")
        self._search_edit.setPlaceholderText("Search names, groups, and command text")
        self._search_edit.textChanged.connect(self._filter_tree)
        layout.insertWidget(0, self._search_edit)

        self._empty_label = QLabel("No commands match your search.")
        self._empty_label.setAccessibleName("No command search results")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

        self._details_view = QPlainTextEdit()
        self._details_view.setAccessibleName("Selected command details")
        self._details_view.setReadOnly(True)
        layout.addWidget(self._details_view)
        self._tree.currentItemChanged.connect(self._update_details)

        tab_widgets = (
            add_btn,
            edit_btn,
            del_btn,
            up_btn,
            down_btn,
            self._search_edit,
            self._tree,
            self._details_view,
        )
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
        self.setTabOrder(self._details_view, self._save_btn)
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
            group_path = (group_name,)
            group_item.setData(
                0, Qt.ItemDataRole.UserRole, {"type": "group", "group_path": group_path}
            )
            self._tree.addTopLevelItem(group_item)
            self._populate_group(group_item, group_path, group_data)
            group_item.setExpanded(True)

    def _populate_group(
        self, parent_item: QTreeWidgetItem, group_path: tuple[str, ...], data: dict
    ):
        """Append command and subgroup rows while retaining exact group ancestry.

        Args:
            parent_item: Tree row that owns this group's direct entries.
            group_path: Exact key components locating ``data`` in the configuration.
            data: Group mapping whose direct entries should be rendered.

        Returns:
            None. Rows are appended to ``parent_item``.
        """
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
                        "group_path": group_path,
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
                        "group_path": (*group_path, label),
                    },
                )
                parent_item.addChild(sub_item)
                self._populate_group(sub_item, (*group_path, label), item)

    def _filter_tree(self, query: str):
        """Filter visible rows by command name, text, or group path.

        Args:
            query: Search text; matching is case-insensitive substring matching.

        Returns:
            None. Only tree visibility, selection preview, and empty-state presentation change.
        """
        needle = query.strip().casefold()
        command_matches = 0

        def filter_group(group_item: QTreeWidgetItem, inherited_match: bool = False) -> bool:
            nonlocal command_matches
            meta = group_item.data(0, Qt.ItemDataRole.UserRole) or {}
            path = meta.get("group_path", ())
            group_match = inherited_match or needle in " / ".join(path).casefold()
            has_visible_command = False
            for index in range(group_item.childCount()):
                child = group_item.child(index)
                child_meta = child.data(0, Qt.ItemDataRole.UserRole) or {}
                if child_meta.get("type") == "command":
                    matches = (
                        group_match
                        or needle in child.text(0).casefold()
                        or needle in child.text(1).casefold()
                    )
                    child.setHidden(not matches)
                    if matches:
                        has_visible_command = True
                        command_matches += 1
                else:
                    visible = filter_group(child, group_match)
                    child.setHidden(not visible)
                    has_visible_command = has_visible_command or visible
            visible = not needle or has_visible_command
            group_item.setHidden(not visible)
            if visible and needle:
                group_item.setExpanded(True)
            return visible

        for index in range(self._tree.topLevelItemCount()):
            filter_group(self._tree.topLevelItem(index))
        self._empty_label.setVisible(bool(needle) and command_matches == 0)
        current = self._tree.currentItem()
        if current is not None and current.isHidden():
            self._tree.setCurrentItem(None)
        if command_matches == 0:
            self._details_view.clear()

    def _update_details(self, current, previous=None):
        """Render the selected command's complete configured data read-only."""
        meta = current.data(0, Qt.ItemDataRole.UserRole) if current is not None else None
        if not isinstance(meta, dict) or meta.get("type") != "command":
            self._details_view.clear()
            return
        group_path = meta.get("group_path", ())
        details = {"name": meta.get("label"), **meta.get("data", {})}
        self._details_view.setPlainText(
            f"Group path: {json.dumps(group_path, ensure_ascii=False)}\n"
            f"{json.dumps(details, ensure_ascii=False, indent=2)}"
        )

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _add_command(self):
        commands = self._services.config_manager.get_commands()
        groups = _command_groups(commands)
        dlg = _CommandFormDialog(groups, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result_data()
            group_path = d["group_path"]
            cmd_data = {k: v for k, v in d.items() if k not in ("group", "group_path", "label")}
            group = commands
            for component in group_path:
                existing = group.get(component)
                if existing is None:
                    existing = {}
                    group[component] = existing
                if not isinstance(existing, dict):
                    return
                group = existing
            group[d["label"]] = cmd_data
            self._services.config_manager.save_commands(commands)
            self._load_tree()

    def _edit_command(self):
        """Edit a selected command at its exact source and destination paths.

        Returns:
            None. Configuration changes are saved only after an accepted edit.
        """
        item = self._tree.currentItem()
        if not item:
            show_info(self, "Edit", "Select a command to edit.")
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if meta.get("type") != "command":
            show_info(self, "Edit", "Select a command (not a group) to edit.")
            return

        commands = self._services.config_manager.get_commands()
        group_path = meta["group_path"]
        label = meta["label"]
        item_data = meta.get("data", {})

        initial = {"group_path": group_path, "label": label, **item_data}
        dlg = _CommandFormDialog(_command_groups(commands), initial=initial, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.result_data()
            new_group_path = d["group_path"]
            new_label = d["label"]
            cmd_data = {k: v for k, v in d.items() if k not in ("group", "group_path", "label")}
            source = _resolve_group_path(commands, group_path)
            if source is None or label not in source:
                return

            destination = commands
            for component in new_group_path:
                existing = destination.get(component)
                if existing is None:
                    existing = {}
                    destination[component] = existing
                if not isinstance(existing, dict):
                    return
                destination = existing

            del source[label]
            destination[new_label] = cmd_data

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
            parent = _resolve_group_path(commands, meta.get("group_path", ()))
            label = meta["label"]
            if parent is not None and label in parent:
                del parent[label]
        elif meta.get("type") == "group":
            group_path = meta.get("group_path", ())
            parent = _resolve_group_path(commands, group_path[:-1])
            if parent is not None and group_path and group_path[-1] in parent:
                del parent[group_path[-1]]

        self._services.config_manager.save_commands(commands)
        self._load_tree()

    def _move_up(self):
        """Move the selected command one position up within its group."""
        self._move_item(-1)

    def _move_down(self):
        """Move the selected command one position down within its group."""
        self._move_item(1)

    def _move_item(self, direction: int):
        """Reorder the selected command among its exact parent's direct entries.

        Args:
            direction: -1 to move up or +1 to move down.

        Returns:
            None. No persistence occurs when the selection or destination is invalid.
        """
        item = self._tree.currentItem()
        if not item:
            return
        meta = item.data(0, Qt.ItemDataRole.UserRole) or {}
        if meta.get("type") != "command":
            return

        commands = self._services.config_manager.get_commands()
        group_path = meta["group_path"]
        label = meta["label"]
        group = _resolve_group_path(commands, group_path)
        if group is None:
            return
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
        if "icon" in group:
            reordered["icon"] = icon_val
        keys.insert(new_idx, keys.pop(idx))
        for k in keys:
            reordered[k] = group[k]
        group.clear()
        group.update(reordered)

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
