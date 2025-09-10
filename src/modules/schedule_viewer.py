import os
import sys
import subprocess
import tempfile
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea,
    QWidget,
    QTextEdit,
    QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class ScheduleViewer:
    """Handles viewing, editing, and deleting scheduled tasks/cron jobs."""

    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app

    def show_dialog(self):
        """Show a dialog to view and manage scheduled tasks."""
        dialog = QDialog()
        dialog.setWindowTitle("View Schedules")
        dialog.setMinimumSize(800, 600)
        layout = QVBoxLayout()

        # Title
        title_label = QLabel("Scheduled Tasks")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Get scheduled tasks
        schedules = self.get_schedules()

        if not schedules:
            # No schedules found
            no_schedules_widget = QWidget()
            no_schedules_layout = QVBoxLayout(no_schedules_widget)
            
            no_schedules_label = QLabel("No scheduled tasks found.")
            no_schedules_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_schedules_layout.addWidget(no_schedules_label)
            
            help_label = QLabel(
                "To create a new scheduled task, use the 'Create Schedule' option in the Tools menu."
            )
            help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            help_label.setStyleSheet("color: gray; font-style: italic;")
            no_schedules_layout.addWidget(help_label)
            
            layout.addWidget(no_schedules_widget)
        else:
            # Create table to display schedules
            table = QTableWidget()
            table.setRowCount(len(schedules))
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Task Name", "Command", "Schedule", "Status", "Actions"])
            
            # Configure table
            header = table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

            # Populate table
            for row, schedule in enumerate(schedules):
                # Task name
                table.setItem(row, 0, QTableWidgetItem(schedule.get("name", "Unknown")))
                
                # Command (truncated if too long)
                command = schedule.get("command", "")
                if len(command) > 50:
                    command = command[:47] + "..."
                table.setItem(row, 1, QTableWidgetItem(command))
                
                # Schedule
                schedule_text = schedule.get("schedule", "")
                table.setItem(row, 2, QTableWidgetItem(schedule_text))
                
                # Status
                table.setItem(row, 3, QTableWidgetItem(schedule.get("status", "Active")))
                
                # Actions
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(5, 5, 5, 5)
                
                # Delete button
                delete_btn = QPushButton("Delete")
                delete_btn.clicked.connect(
                    lambda checked=False, sched=schedule: self.delete_schedule(sched, dialog)
                )
                actions_layout.addWidget(delete_btn)
                
                table.setCellWidget(row, 4, actions_widget)

            layout.addWidget(table)

        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(lambda: self.refresh_dialog(dialog))
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec()

    def get_schedules(self):
        """Get all scheduled tasks created by py-tray-command-launcher."""
        try:
            if sys.platform == "win32":
                return self._get_windows_tasks()
            else:
                return self._get_linux_cron_jobs()
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to get schedules: {str(e)}")
            return []

    def _get_windows_tasks(self):
        """Get Windows scheduled tasks created by py-tray-command-launcher."""
        schedules = []
        try:
            # List all tasks with PyTrayLauncher prefix
            result = subprocess.run(
                ["schtasks", "/query", "/fo", "csv", "/v"],
                capture_output=True,
                text=True,
                check=True
            )
            
            lines = result.stdout.split('\n')
            if len(lines) > 1:  # Skip header
                for line in lines[1:]:
                    if line.strip() and "PyTrayLauncher_" in line:
                        parts = line.split(',')
                        if len(parts) >= 8:
                            task_name = parts[0].strip('"')
                            status = parts[2].strip('"')
                            schedule = parts[7].strip('"')
                            
                            # Get task details
                            try:
                                detail_result = subprocess.run(
                                    ["schtasks", "/query", "/tn", task_name, "/fo", "list", "/v"],
                                    capture_output=True,
                                    text=True,
                                    check=True
                                )
                                
                                # Parse command from detailed output
                                command = ""
                                for detail_line in detail_result.stdout.split('\n'):
                                    if "Task To Run:" in detail_line:
                                        command = detail_line.split("Task To Run:", 1)[1].strip()
                                        break
                                
                                schedules.append({
                                    "name": task_name,
                                    "command": command,
                                    "schedule": schedule,
                                    "status": status,
                                    "type": "windows_task"
                                })
                            except subprocess.CalledProcessError:
                                # Skip tasks we can't get details for
                                continue
                                
        except subprocess.CalledProcessError as e:
            # No tasks found or error occurred
            pass
            
        return schedules

    def _get_linux_cron_jobs(self):
        """Get Linux cron jobs created by py-tray-command-launcher."""
        schedules = []
        try:
            # Get current root crontab
            result = subprocess.run(
                ["sudo", "crontab", "-l"],
                capture_output=True,
                text=True,
                check=True
            )
            
            lines = result.stdout.split('\n')
            current_schedule = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("# py-tray-command-launcher:"):
                    # This is a comment line with task name
                    task_name = line.replace("# py-tray-command-launcher:", "").strip()
                    current_schedule = {"name": task_name, "type": "cron_job"}
                elif current_schedule and line and not line.startswith("#"):
                    # This should be the cron entry for the previous comment
                    parts = line.split()
                    if len(parts) >= 6:
                        minute = parts[0]
                        hour = parts[1]
                        day_month = parts[2]
                        month = parts[3]
                        day_week = parts[4]
                        command = " ".join(parts[5:])
                        
                        # Format schedule display
                        schedule_text = f"{hour}:{minute:0>2s}"
                        if day_week != "*":
                            days = self._convert_cron_days_to_text(day_week)
                            schedule_text += f" on {days}"
                        else:
                            schedule_text += " daily"
                            
                        current_schedule.update({
                            "command": command,
                            "schedule": schedule_text,
                            "status": "Active",
                            "cron_line": line
                        })
                        
                        schedules.append(current_schedule)
                    current_schedule = None
                else:
                    current_schedule = None
                    
        except subprocess.CalledProcessError:
            # No crontab found or error occurred - this is normal if no cron jobs exist
            pass
        except Exception as e:
            # For other errors, we might want to show a warning but not fail completely
            print(f"Warning: Error reading crontab: {str(e)}")
            
        return schedules

    def _convert_cron_days_to_text(self, day_week):
        """Convert cron day numbers to readable text."""
        day_map = {
            "0": "Sunday", "1": "Monday", "2": "Tuesday", "3": "Wednesday",
            "4": "Thursday", "5": "Friday", "6": "Saturday", "7": "Sunday"
        }
        
        if "," in day_week:
            days = day_week.split(",")
            day_names = [day_map.get(day.strip(), day.strip()) for day in days]
            return ", ".join(day_names)
        else:
            return day_map.get(day_week, day_week)

    def delete_schedule(self, schedule, parent_dialog):
        """Delete a scheduled task."""
        task_name = schedule.get("name", "Unknown")
        
        # Confirm deletion
        reply = QMessageBox.question(
            parent_dialog,
            "Confirm Deletion",
            f"Are you sure you want to delete the scheduled task '{task_name}'?\n\n"
            f"Command: {schedule.get('command', 'Unknown')}\n"
            f"Schedule: {schedule.get('schedule', 'Unknown')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if schedule.get("type") == "windows_task":
                    self._delete_windows_task(schedule)
                else:
                    self._delete_linux_cron_job(schedule)
                    
                QMessageBox.information(
                    parent_dialog,
                    "Success",
                    f"Scheduled task '{task_name}' deleted successfully."
                )
                
                # Refresh the dialog
                self.refresh_dialog(parent_dialog)
                
            except Exception as e:
                QMessageBox.critical(
                    parent_dialog,
                    "Error",
                    f"Failed to delete scheduled task: {str(e)}"
                )

    def _delete_windows_task(self, schedule):
        """Delete a Windows scheduled task."""
        task_name = schedule.get("name")
        result = subprocess.run(
            ["schtasks", "/delete", "/tn", task_name, "/f"],
            capture_output=True,
            text=True,
            check=True
        )

    def _delete_linux_cron_job(self, schedule):
        """Delete a Linux cron job."""
        try:
            # Get current root crontab
            result = subprocess.run(
                ["sudo", "crontab", "-l"],
                capture_output=True,
                text=True,
                check=True
            )
            current_crontab = result.stdout
        except subprocess.CalledProcessError:
            current_crontab = ""
        
        # Remove the schedule from crontab
        lines = current_crontab.split('\n')
        new_lines = []
        skip_next = False
        
        for line in lines:
            if skip_next and line.strip() == schedule.get("cron_line", ""):
                # Skip this line (the actual cron entry)
                skip_next = False
                continue
            elif line.strip() == f"# py-tray-command-launcher: {schedule.get('name')}":
                # Skip the comment line and mark to skip next line
                skip_next = True
                continue
            else:
                new_lines.append(line)
        
        # Write the new crontab
        new_crontab = '\n'.join(new_lines)
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.cron') as f:
            f.write(new_crontab)
            temp_file = f.name
        
        try:
            subprocess.run(
                ["sudo", "crontab", temp_file],
                capture_output=True,
                text=True,
                check=True
            )
        finally:
            os.unlink(temp_file)

    def refresh_dialog(self, dialog):
        """Refresh the schedule dialog by closing and reopening it."""
        dialog.accept()
        self.show_dialog()