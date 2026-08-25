# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import subprocess
import sys
import tempfile

from PyQt6.QtWidgets import QDialog, QMessageBox

from ui.schedule_dialog import ScheduleDialog

logger = logging.getLogger(__name__)


class ScheduleCreator:
    """Handles the creation of scheduled tasks/cron jobs for commands."""

    def __init__(self, services):
        """Initialize with an AppServices instance."""
        self.services = services

    def show_dialog(self) -> bool:
        """Show a dialog to create a scheduled task."""
        try:
            commands = self.services.get_all_commands()
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to load commands: {str(e)}")
            return False
        dialog = ScheduleDialog(commands)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            schedule = dialog.get_schedule()
            if schedule is not None:
                return self.create_schedule(
                    schedule["command_info"],
                    schedule["hour"],
                    schedule["minute"],
                    schedule["days"],
                )
        return False

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
        command = command_info["command"]

        # Convert days to Windows format
        windows_days = {
            "Monday": "MON",
            "Tuesday": "TUE",
            "Wednesday": "WED",
            "Thursday": "THU",
            "Friday": "FRI",
            "Saturday": "SAT",
            "Sunday": "SUN",
        }

        days_string = ",".join([windows_days[day] for day in selected_days])
        time_string = f"{hour:02d}:{minute:02d}"

        # Create the schtasks command
        schtasks_cmd = [
            "schtasks",
            "/create",
            "/tn",
            task_name,
            "/tr",
            command,
            "/sc",
            "weekly",
            "/d",
            days_string,
            "/st",
            time_string,
            "/f",  # Force overwrite if exists
        ]

        try:
            subprocess.run(schtasks_cmd, capture_output=True, text=True, check=True)
            logger.info(
                "Windows scheduled task '%s' created for command: %s at %s on %s",
                task_name,
                command,
                time_string,
                days_string,
            )
            QMessageBox.information(
                None,
                "Success",
                f"Windows scheduled task '{task_name}' created successfully!\n\n"
                f"Command: {command}\n"
                f"Time: {time_string}\n"
                f"Days: {', '.join(selected_days)}",
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error("Failed to create Windows scheduled task '%s': %s", task_name, e.stderr)
            QMessageBox.critical(
                None, "Error", f"Failed to create Windows scheduled task:\n{e.stderr}"
            )
            return False

    def _create_linux_cron(self, command_info, hour, minute, selected_days):
        """Create a Linux cron job in the current user's crontab (never uses pkexec/sudo)."""
        command = command_info["command"]

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

        # Validate the cron expression before any subprocess call
        if not self._validate_cron_expression(cron_entry):
            logger.error("Rejected invalid cron expression: %s", cron_entry)
            QMessageBox.critical(
                None,
                "Error",
                f"Invalid cron expression:\n{cron_entry}\n\n"
                "The generated schedule could not be validated. Please try again.",
            )
            return False

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
                    command_info["label"],
                    cron_entry,
                )

                # Post-install verification: confirm the entry is present in the installed crontab
                verify = subprocess.run(
                    ["crontab", "-l"],
                    capture_output=True,
                    text=True,
                )
                if verify.returncode != 0 or cron_entry not in verify.stdout:
                    logger.error(
                        "Post-install verification failed: cron entry not found in crontab after install. "
                        "Entry: %s, crontab output: %s",
                        cron_entry,
                        verify.stdout,
                    )
                    QMessageBox.critical(
                        None,
                        "Error",
                        "Cron job installation may have failed.\n\n"
                        "The entry was not found in your crontab after installation.\n"
                        "Please check your cron configuration manually.",
                    )
                    return False
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
                command_info.get("label", "?"),
                str(e),
            )
            QMessageBox.critical(
                None,
                "Error",
                f"Failed to create cron job:\n{e}\n\n"
                "Make sure the cron service is installed and running.",
            )
            return False

    @staticmethod
    def _validate_cron_expression(cron_entry: str) -> bool:
        """Validate a cron expression string against structural rules.

        Checks:
        - Non-empty, no embedded newlines
        - At least 6 whitespace-separated fields: minute hour * * day_of_week command
        - minute is '*' or an integer 0-59
        - hour is '*' or an integer 0-23
        - day_of_week is '*' or a comma-separated list of integers 0-7
        - command portion is non-empty after stripping

        Note: minute 0-59 and hour 0-23 are defense-in-depth. QTimeEdit with
        display format "HH:mm" already constrains these at the UI level.
        The validator retains them because the static method is independently
        callable and the tests for invalid minute/hour verify the range checks.
        """
        if not cron_entry or "\n" in cron_entry:
            return False

        parts = cron_entry.split()
        if len(parts) < 6:
            return False

        # Validate minute: '*' or integer 0-59
        minute_str = parts[0]
        if minute_str != "*":
            try:
                minute = int(minute_str)
                if minute < 0 or minute > 59:
                    return False
            except ValueError:
                return False

        # Validate hour: '*' or integer 0-23
        hour_str = parts[1]
        if hour_str != "*":
            try:
                hour = int(hour_str)
                if hour < 0 or hour > 23:
                    return False
            except ValueError:
                return False

        # Fields 2 and 3 must be '*'
        if parts[2] != "*" or parts[3] != "*":
            return False

        # Validate day_of_week (field 4): '*' or comma-separated list of values 0-7
        # Each value can be a single integer or a range (e.g., "0-7")
        day_of_week = parts[4]
        if day_of_week == "*":
            pass  # OK
        else:
            for token in day_of_week.split(","):
                token = token.strip()
                # Handle ranges like "0-7"
                if "-" in token:
                    range_parts = token.split("-")
                    if len(range_parts) != 2:
                        return False
                    try:
                        low = int(range_parts[0])
                        high = int(range_parts[1])
                        if low < 0 or low > 7 or high < 0 or high > 7:
                            return False
                    except ValueError:
                        return False
                else:
                    try:
                        day_val = int(token)
                        if day_val < 0 or day_val > 7:
                            return False
                    except ValueError:
                        return False

        # Command portion must be non-empty
        command = " ".join(parts[5:]).strip()
        if not command:
            return False

        return True

    @staticmethod
    def _human_cron(minute: int, hour: int, days: list) -> str:
        """Return a human-readable schedule description."""
        day_map = {
            "Monday": "Mon",
            "Tuesday": "Tue",
            "Wednesday": "Wed",
            "Thursday": "Thu",
            "Friday": "Fri",
            "Saturday": "Sat",
            "Sunday": "Sun",
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
