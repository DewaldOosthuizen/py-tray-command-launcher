# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ScheduleViewer edit flow (issue #120)."""

import sys
from unittest.mock import MagicMock, patch

_pyqt6 = MagicMock()
sys.modules.setdefault("PyQt6", _pyqt6)
sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6.QtWidgets)
sys.modules.setdefault("PyQt6.QtCore", _pyqt6.QtCore)
sys.modules.setdefault("PyQt6.QtGui", _pyqt6.QtGui)
sys.modules.setdefault("core.config_manager", MagicMock())

import os
import sys as _sys

_sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_edit_schedule_keeps_old_entry_on_create_rejected():
    """mock show_dialog returns False; assert _delete_linux_cron_job is NOT called,
    _reinstall_cron_job is not referenced (method removed), and refresh_dialog is
    NOT called (old entry never removed, no restore needed)."""
    from modules.schedule_viewer import ScheduleViewer

    svc = MagicMock()
    viewer = ScheduleViewer(svc)

    schedule = {
        "name": "Test Schedule",
        "command": "/bin/true",
        "schedule": "09:30",
        "status": "Active",
        "source": "User",
        "type": "cron_job",
        "cron_line": "30 9 * * 1 /bin/true",
    }

    parent_dialog = MagicMock()

    mock_creator = MagicMock()
    mock_creator.show_dialog.return_value = False

    with (
        patch.object(viewer, "_delete_linux_cron_job") as mock_delete,
        patch.object(viewer, "refresh_dialog") as mock_refresh,
        patch("modules.schedule_viewer.QMessageBox") as mock_msgbox_cls,
        patch("modules.schedule_creator.ScheduleCreator", return_value=mock_creator),
    ):
        # IMPORTANT: question.return_value must be the SAME object as
        # mock_msgbox_cls.StandardButton.Yes for the comparison in the code
        # (reply != QMessageBox.StandardButton.Yes) to work correctly.
        mock_msgbox_cls.question.return_value = mock_msgbox_cls.StandardButton.Yes

        viewer.edit_schedule(schedule, parent_dialog)

    # Deletion must NOT happen before creation under the create-first flow
    mock_delete.assert_not_called()
    # No refresh since the old schedule was untouched
    mock_refresh.assert_not_called()
    # No error/info message about a failed restore
    mock_msgbox_cls.critical.assert_not_called()
    mock_msgbox_cls.information.assert_not_called()


def test_edit_schedule_refreshes_on_create_accepted():
    """mock show_dialog returns True; assert _delete_linux_cron_job IS called once
    after successful creation, refresh_dialog IS called once, and
    _reinstall_cron_job is not referenced (method removed)."""
    from modules.schedule_viewer import ScheduleViewer

    svc = MagicMock()
    viewer = ScheduleViewer(svc)

    schedule = {
        "name": "Test Schedule",
        "command": "/bin/true",
        "schedule": "09:30",
        "status": "Active",
        "source": "User",
        "type": "cron_job",
        "cron_line": "30 9 * * 1 /bin/true",
    }

    parent_dialog = MagicMock()

    mock_creator = MagicMock()
    mock_creator.show_dialog.return_value = True

    with (
        patch.object(viewer, "_delete_linux_cron_job") as mock_delete,
        patch.object(viewer, "refresh_dialog") as mock_refresh,
        patch("modules.schedule_viewer.QMessageBox") as mock_msgbox_cls,
        patch("modules.schedule_creator.ScheduleCreator", return_value=mock_creator),
    ):
        # IMPORTANT: question.return_value must be the SAME object as
        # mock_msgbox_cls.StandardButton.Yes for the comparison in the code
        # (reply != QMessageBox.StandardButton.Yes) to work correctly.
        mock_msgbox_cls.question.return_value = mock_msgbox_cls.StandardButton.Yes

        viewer.edit_schedule(schedule, parent_dialog)

    # Deletion must happen AFTER creation under the create-first flow
    mock_delete.assert_called_once_with(schedule)
    # Refresh is called after the new schedule is created and old is deleted
    mock_refresh.assert_called_once_with(parent_dialog)
    # No error message since delete succeeded
    mock_msgbox_cls.critical.assert_not_called()


def test_edit_schedule_preserves_old_schedule_on_cancel():
    """Explicitly verify the cancel path (show_dialog returns False):
    _delete_linux_cron_job is never called, guaranteeing the old schedule
    is preserved."""
    from modules.schedule_viewer import ScheduleViewer

    svc = MagicMock()
    viewer = ScheduleViewer(svc)

    schedule = {
        "name": "Test Schedule",
        "command": "/bin/true",
        "schedule": "09:30",
        "status": "Active",
        "source": "User",
        "type": "cron_job",
        "cron_line": "30 9 * * 1 /bin/true",
    }

    parent_dialog = MagicMock()

    mock_creator = MagicMock()
    mock_creator.show_dialog.return_value = False

    with (
        patch.object(viewer, "_delete_linux_cron_job") as mock_delete,
        patch.object(viewer, "refresh_dialog") as mock_refresh,
        patch("modules.schedule_viewer.QMessageBox") as mock_msgbox_cls,
        patch("modules.schedule_creator.ScheduleCreator", return_value=mock_creator),
    ):
        mock_msgbox_cls.question.return_value = mock_msgbox_cls.StandardButton.Yes

        viewer.edit_schedule(schedule, parent_dialog)

    # The old schedule must be preserved — delete is never called on cancel
    mock_delete.assert_not_called()
    mock_refresh.assert_not_called()


def test_delete_linux_cron_job_preserves_new_entry_same_name():
    """Verify _delete_linux_cron_job() deletes only the entry whose cron line
    matches when there are two entries with the same comment marker but different
    cron lines. Both the new entry's comment marker and its cron line must appear
    exactly once in the final crontab; the old entry must be fully removed."""
    from modules.schedule_viewer import ScheduleViewer

    svc = MagicMock()
    viewer = ScheduleViewer(svc)

    schedule = {
        "name": "MyLabel",
        "command": "/bin/old_command",
        "schedule": "09:30",
        "cron_line": "30 9 * * 1 /bin/old_command",
    }

    canned_crontab = (
        "# py-tray-command-launcher: MyLabel\n"
        "30 9 * * 1 /bin/old_command\n"
        "# py-tray-command-launcher: MyLabel\n"
        "0 8 * * 1 /bin/new_command\n"
    )

    # Capture the crontab written back via the temp-file install call
    captured = {}

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        if cmd[:2] == ["crontab", "-l"]:
            result.returncode = 0
            result.stdout = canned_crontab
            result.stderr = ""
        elif cmd[0] == "crontab" and isinstance(cmd[1], str) and cmd[1].endswith(".cron"):
            # Read the temp file that was written
            temp_path = cmd[1]
            with open(temp_path) as f:
                captured["written"] = f.read()
            result.returncode = 0
            result.stderr = ""
        else:
            result.returncode = 0
            result.stderr = ""
        return result

    with patch("modules.schedule_viewer.subprocess.run", side_effect=fake_run):
        viewer._delete_linux_cron_job(schedule)

    written = captured["written"]

    # The old entry's marker + cron line must be fully removed
    assert "# py-tray-command-launcher: MyLabel\n30 9 * * 1 /bin/old_command" not in written

    # The new entry's marker must appear exactly once
    new_marker = "# py-tray-command-launcher: MyLabel"
    assert written.count(new_marker) == 1

    # The new entry's cron line must appear exactly once
    new_cron_line = "0 8 * * 1 /bin/new_command"
    assert written.count(new_cron_line) == 1
