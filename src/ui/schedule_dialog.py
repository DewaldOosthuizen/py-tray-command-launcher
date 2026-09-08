# SPDX-License-Identifier: GPL-3.0-or-later

from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
)

from modules.schedule_creator import ScheduleCreator


class ScheduleDialog(QDialog):
    """Dialog for creating a scheduled task / cron job.

    Wraps all UI construction, day-selection toggling, and preview
    rendering so that ScheduleCreator.show_dialog() stays a thin
    orchestrator and the dialog itself can be unit-tested in isolation.
    """

    def __init__(self, commands: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Schedule")
        self.setMinimumWidth(400)
        self._commands = commands
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_schedule(self) -> dict | None:
        """Return selected command, time, and days, or None if cancelled.

        Must only be called after exec() returns QDialog.Accepted.
        """
        command_combo = self.findChild(QComboBox)
        time_edit = self.findChild(QTimeEdit)
        days_checkboxes = {
            cb.objectName().removeprefix("day_"): cb
            for cb in self.findChildren(QCheckBox)
            if cb.objectName().startswith("day_")
        }

        selected_command_text = command_combo.currentText()
        if not selected_command_text or selected_command_text not in self._command_data:
            return None

        selected_command = self._command_data[selected_command_text]
        time = time_edit.time()
        selected_days = [day for day, cb in days_checkboxes.items() if cb.isChecked()]

        if not selected_days:
            return None

        return {
            "command_info": selected_command,
            "hour": time.hour(),
            "minute": time.minute(),
            "days": selected_days,
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout()

        # -- Command selection -------------------------------------------
        command_layout = QHBoxLayout()
        command_layout.addWidget(QLabel("Command:"))
        self._command_combo = QComboBox()
        self._populate_commands()
        command_layout.addWidget(self._command_combo)
        layout.addLayout(command_layout)

        # -- Time selection ----------------------------------------------
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time:"))
        self._time_edit = QTimeEdit()
        self._time_edit.setTime(QTime.currentTime())
        self._time_edit.setDisplayFormat("HH:mm")
        time_layout.addWidget(self._time_edit)
        layout.addLayout(time_layout)

        # -- Days selection ----------------------------------------------
        days_layout = QVBoxLayout()
        days_layout.addWidget(QLabel("Days:"))

        days_grid = QGridLayout()
        self._days_checkboxes: dict[str, QCheckBox] = {}
        days = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        for i, day in enumerate(days):
            checkbox = QCheckBox(day)
            checkbox.setObjectName(f"day_{day}")
            self._days_checkboxes[day] = checkbox
            days_grid.addWidget(checkbox, i // 4, i % 4)

        days_layout.addLayout(days_grid)
        layout.addLayout(days_layout)

        # -- Select all / none -------------------------------------------
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        select_all_btn.clicked.connect(self._select_all_days)
        select_none_btn.clicked.connect(self._select_none_days)
        select_layout.addWidget(select_all_btn)
        select_layout.addWidget(select_none_btn)
        layout.addLayout(select_layout)

        # -- Human-readable preview --------------------------------------
        self._preview_label = QLabel("")
        self._preview_label.setObjectName("SchedulePreview")
        layout.addWidget(self._preview_label)

        # -- Wire live preview updates ----------------------------------
        self._time_edit.timeChanged.connect(self._update_preview)
        for cb in self._days_checkboxes.values():
            cb.stateChanged.connect(self._update_preview)

        # -- Buttons ------------------------------------------------------
        button_layout = QHBoxLayout()
        create_btn = QPushButton("Create Schedule")
        cancel_btn = QPushButton("Cancel")
        create_btn.clicked.connect(self._on_create)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(create_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self._update_preview()

    # ------------------------------------------------------------------
    # Slot helpers
    # ------------------------------------------------------------------

    def _populate_commands(self) -> None:
        """Populate the command combo from the commands list passed to __init__."""
        self._command_data: dict[str, dict] = {}
        for cmd_info in self._commands:
            display_text = f"{cmd_info['group']} → {cmd_info['label']}"
            self._command_combo.addItem(display_text)
            self._command_data[display_text] = cmd_info

    def _select_all_days(self) -> None:
        for cb in self._days_checkboxes.values():
            cb.setChecked(True)
        self._update_preview()

    def _select_none_days(self) -> None:
        for cb in self._days_checkboxes.values():
            cb.setChecked(False)
        self._update_preview()

    def _update_preview(self, *_args) -> None:
        t = self._time_edit.time()
        days = [d for d, cb in self._days_checkboxes.items() if cb.isChecked()]
        if days:
            self._preview_label.setText(ScheduleCreator._human_cron(t.minute(), t.hour(), days))
        else:
            self._preview_label.setText("Select at least one day")

    def _on_create(self) -> None:
        selected_command_text = self._command_combo.currentText()
        if not selected_command_text or selected_command_text not in self._command_data:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Error", "Please select a command.")
            return

        selected_days = [day for day, cb in self._days_checkboxes.items() if cb.isChecked()]
        if not selected_days:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Error", "Please select at least one day.")
            return

        self.accept()
