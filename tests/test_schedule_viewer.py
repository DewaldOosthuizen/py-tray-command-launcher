# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ScheduleViewer edit flow (issue #82)."""

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
    """mock show_dialog returns False; assert _delete_linux_cron_job IS called,
    _reinstall_cron_job IS called, and 'Edit Cancelled' message is shown."""
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
        patch.object(viewer, "_reinstall_cron_job") as mock_reinstall,
        patch.object(viewer, "refresh_dialog") as mock_refresh,
        patch("modules.schedule_viewer.QMessageBox") as mock_msgbox_cls,
        patch("modules.schedule_creator.ScheduleCreator", return_value=mock_creator),
    ):
        # IMPORTANT: question.return_value must be the SAME object as
        # mock_msgbox_cls.StandardButton.Yes for the comparison in the code
        # (reply != QMessageBox.StandardButton.Yes) to work correctly.
        mock_msgbox_cls.question.return_value = mock_msgbox_cls.StandardButton.Yes

        viewer.edit_schedule(schedule, parent_dialog)

    # Deletion happens before creation
    mock_delete.assert_called_once_with(schedule)
    # Reinstall happens because creation was rejected
    mock_reinstall.assert_called_once_with(schedule)
    # Refresh is called after successful reinstall
    mock_refresh.assert_called_once_with(parent_dialog)
    # Info message about cancelled edit
    mock_msgbox_cls.information.assert_called_once()


def test_edit_schedule_refreshes_on_create_accepted():
    """mock show_dialog returns True; assert _delete_linux_cron_job IS called,
    refresh_dialog IS called, and _reinstall_cron_job is NOT called."""
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
        patch.object(viewer, "_reinstall_cron_job") as mock_reinstall,
        patch.object(viewer, "refresh_dialog") as mock_refresh,
        patch("modules.schedule_viewer.QMessageBox") as mock_msgbox_cls,
        patch("modules.schedule_creator.ScheduleCreator", return_value=mock_creator),
    ):
        # IMPORTANT: question.return_value must be the SAME object as
        # mock_msgbox_cls.StandardButton.Yes for the comparison in the code
        # (reply != QMessageBox.StandardButton.Yes) to work correctly.
        mock_msgbox_cls.question.return_value = mock_msgbox_cls.StandardButton.Yes

        viewer.edit_schedule(schedule, parent_dialog)

    # Deletion happens before creation
    mock_delete.assert_called_once_with(schedule)
    # No reinstall because creation succeeded
    mock_reinstall.assert_not_called()
    # Refresh is called after successful creation
    mock_refresh.assert_called_once_with(parent_dialog)
    # No info message about cancelled edit
    mock_msgbox_cls.information.assert_not_called()
