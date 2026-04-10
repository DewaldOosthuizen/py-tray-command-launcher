#  SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import sys
import subprocess
import tempfile

logger = logging.getLogger(__name__)
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTimeEdit,
    QPushButton,
    QMessageBox,
    QCheckBox,
    QGridLayout,
)
from PyQt6.QtCore import QTime
from core.config_manager import config_manager, ConfigurationError


class ScheduleCreator:
    """Handles the creation of scheduled tasks/cron jobs for commands."""

    def __init__(self, services):
        """Initialize with an AppServices instance."""
        self.services = services

    def show_dialog(self):
        """Show a dialog to create a scheduled task."""
        dialog = QDialog()
        dialog.setWindowTitle("Create Schedule")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout()

        # Command selection
        command_layout = QHBoxLayout()
        command_layout.addWidget(QLabel("Command:"))
        command_combo = QComboBox()

        # Populate with all available commands
        try:
            all_commands = self.services.get_all_commands()
            self.command_data = {}
            for cmd_info in all_commands:
                display_text = f"{cmd_info['group']} → {cmd_info['label']}"
                command_combo.addItem(display_text)
                self.command_data[display_text] = cmd_info
        except Exception as e:
            QMessageBox.critical(dialog, "Error", f"Failed to load commands: {str(e)}")
            return

        command_layout.addWidget(command_combo)
        layout.addLayout(command_layout)

        # Time selection
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time:"))
        time_edit = QTimeEdit()
        time_edit.setTime(QTime.currentTime())
        time_edit.setDisplayFormat("HH:mm")
        time_layout.addWidget(time_edit)
        layout.addLayout(time_layout)

        # Days selection
        days_layout = QVBoxLayout()
        days_layout.addWidget(QLabel("Days:"))

        days_grid = QGridLayout()
        days_checkboxes = {}
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for i, day in enumerate(days):
            checkbox = QCheckBox(day)
            days_checkboxes[day] = checkbox
            days_grid.addWidget(checkbox, i // 4, i % 4)

        days_layout.addLayout(days_grid)
        layout.addLayout(days_layout)

        # Select all/none buttons
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")

        def select_all():
            for checkbox in days_checkboxes.values():
                checkbox.setChecked(True)

        def select_none():
            for checkbox in days_checkboxes.values():
                checkbox.setChecked(False)

        select_all_btn.clicked.connect(select_all)
        select_none_btn.clicked.connect(select_none)
        select_layout.addWidget(select_all_btn)
        select_layout.addWidget(select_none_btn)
        layout.addLayout(select_layout)

        # Human-readable preview label
        preview_label = QLabel("")
        preview_label.setObjectName("SchedulePreview")
        layout.addWidget(preview_label)

        def _update_preview():
            t = time_edit.time()
            days = [d for d, cb in days_checkboxes.items() if cb.isChecked()]
            if days:
                preview_label.setText(ScheduleCreator._human_cron(t.minute(), t.hour(), days))
            else:
                preview_label.setText("Select at least one day")

        time_edit.timeChanged.connect(lambda _: _update_preview())
        for cb in days_checkboxes.values():
            cb.stateChanged.connect(lambda _: _update_preview())

        # Buttons
        button_layout = QHBoxLayout()
        create_btn = QPushButton("Create Schedule")
        cancel_btn = QPushButton("Cancel")

        def on_create():
            # Get selected command
            selected_command_text = command_combo.currentText()
            if not selected_command_text or selected_command_text not in self.command_data:
                QMessageBox.warning(dialog, "Error", "Please select a command.")
                return

            selected_command = self.command_data[selected_command_text]

            # Get selected time
            time = time_edit.time()
            hour = time.hour()
            minute = time.minute()

            # Get selected days
            selected_days = []
            for day, checkbox in days_checkboxes.items():
                if checkbox.isChecked():
                    selected_days.append(day)

            if not selected_days:
                QMessageBox.warning(dialog, "Error", "Please select at least one day.")
                return

            # Create the schedule
            success = self.create_schedule(selected_command, hour, minute, selected_days)
            if success:
                dialog.accept()

        def on_cancel():
            dialog.reject()

        create_btn.clicked.connect(on_create)
        cancel_btn.clicked.connect(on_cancel)
        button_layout.addWidget(create_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec()

    def create_schedule(self, command_info, hour, minute, selected_days):
        """Create a scheduled task based on the platform."""
        try:
            if sys.platform == "win32":
                return self._create_windows_task(command_info, hour, minute, selected_days)
            else:
                return self._create_linux_cron(command_info, hour, minute, selected_days)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to create schedule: {str(e)}")
            return False

    def _create_windows_task(self, command_info, hour, minute, selected_days):
        task_name = f"PyTrayLauncher_{command_info['label'].replace(' ', '_')}"
        command = command_info['command']

        # Convert days to Windows format
        windows_days = {
            "Monday": "MON",
            "Tuesday": "TUE", 
            "Wednesday": "WED",
            "Thursday": "THU",
            "Friday": "FRI",
            "Saturday": "SAT",
            "Sunday": "SUN"
        }

        days_string = ",".join([windows_days[day] for day in selected_days])
        time_string = f"{hour:02d}:{minute:02d}"

        # Create the schtasks command
        schtasks_cmd = [
            "schtasks",
            "/create",
            "/tn", task_name,
            "/tr", command,
            "/sc", "weekly",
            "/d", days_string,
            "/st", time_string,
            "/f"  # Force overwrite if exists
        ]

        try:
            result = subprocess.run(schtasks_cmd, capture_output=True, text=True, check=True)
            logger.info(
                "Windows scheduled task '%s' created for command: %s at %s on %s",
                task_name, command, time_string, days_string,
            )
            QMessageBox.information(
                None,
                "Success",
                f"Windows scheduled task '{task_name}' created successfully!\n\n"
                f"Command: {command}\n"
                f"Time: {time_string}\n"
                f"Days: {', '.join(selected_days)}"
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(
                "Failed to create Windows scheduled task '%s': %s", task_name, e.stderr
            )
            QMessageBox.critical(
                None,
                "Error",
                f"Failed to create Windows scheduled task:\n{e.stderr}"
            )
            return False

    def _create_linux_cron(self, command_info, hour, minute, selected_days):
        """Create a Linux cron job in the current user's crontab (never uses pkexec/sudo)."""
        command = command_info['command']

        # Convert days to cron format (0=Sunday, 1=Monday, etc.)
        cron_days = {
            "Sunday": "0",
            "Monday": "1",
            "Tuesday": "2",
            "Wednesday": "3",
            "Thursday": "4",
            "Friday": "5",
            "Saturday": "6",
        }

        days_string = ",".join([cron_days[day] for day in selected_days])
        cron_entry = f"{minute} {hour} * * {days_string} {command}"
        human_desc = self._human_cron(minute, hour, selected_days)

        try:
            # Read current user crontab; an exit code of 1 means "no crontab for user" which is OK
            logger.debug("Reading current user crontab")
            result = subprocess.run(
                ["crontab", "-l"],
                capture_output=True,
                text=True,
            )
            # exit code 1 with "no crontab" message is acceptable; exit code > 1 is a real error
            if result.returncode > 1:
                raise RuntimeError(result.stderr.strip() or "crontab -l failed")
            current_crontab = result.stdout if result.returncode == 0 else ""
            logger.debug("Current crontab read (%d lines)", current_crontab.count("\n"))

            comment = f"# py-tray-command-launcher: {command_info['label']}"
            new_crontab = current_crontab.rstrip("\n") + "\n" + comment + "\n" + cron_entry + "\n"

            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".cron") as f:
                f.write(new_crontab)
                temp_file = f.name

            try:
                install = subprocess.run(
                    ["crontab", temp_file],
                    capture_output=True,
                    text=True,
                )
                if install.returncode != 0:
                    raise RuntimeError(install.stderr.strip() or "crontab install failed")
                logger.info(
                    "Cron job installed for '%s': %s",
                    command_info['label'], cron_entry,
                )
            finally:
                os.unlink(temp_file)

            QMessageBox.information(
                None,
                "Schedule Created",
                f"Cron job created in your user crontab:\n\n"
                f"Command : {command}\n"
                f"Schedule: {human_desc}\n"
                f"Cron    : {cron_entry}",
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to create cron job for '%s': %s",
                command_info.get('label', '?'), str(e),
            )
            QMessageBox.critical(
                None,
                "Error",
                f"Failed to create cron job:\n{e}\n\n"
                "Make sure the cron service is installed and running.",
            )
            return False

    @staticmethod
    def _human_cron(minute: int, hour: int, days: list) -> str:
        """Return a human-readable schedule description."""
        day_map = {
            "Monday": "Mon", "Tuesday": "Tue", "Wednesday": "Wed",
            "Thursday": "Thu", "Friday": "Fri", "Saturday": "Sat", "Sunday": "Sun",
        }
        weekdays = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
        weekend = {"Saturday", "Sunday"}
        day_set = set(days)
        if day_set == weekdays:
            day_str = "weekdays"
        elif day_set == weekend:
            day_str = "weekends"
        elif day_set == weekdays | weekend:
            day_str = "every day"
        else:
            day_str = ", ".join(day_map.get(d, d) for d in days)
        return f"Every {day_str} at {hour:02d}:{minute:02d}"
