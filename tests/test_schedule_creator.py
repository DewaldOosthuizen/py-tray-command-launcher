# SPDX-License-Identifier: GPL-3.0-or-later

import sys
from unittest.mock import MagicMock, patch

# Use the PyQt6 stub from conftest.py if available, otherwise create a simple one
if "PyQt6" not in sys.modules:
    _pyqt6 = MagicMock()
    sys.modules.setdefault("PyQt6", _pyqt6)
    sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6.QtWidgets)
    sys.modules.setdefault("PyQt6.QtCore", _pyqt6.QtCore)
    sys.modules.setdefault("PyQt6.QtGui", _pyqt6.QtGui)
    sys.modules.setdefault("core.config_manager", MagicMock())
    _pyqt6.QtWidgets.QDialog.DialogCode = MagicMock()
    _pyqt6.QtWidgets.QDialog.DialogCode.Accepted = 1
    _pyqt6.QtWidgets.QDialog.DialogCode.Rejected = 0

import os
import sys as _sys

_sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.schedule_creator import QDialog, ScheduleCreator


def test_human_cron_weekdays():
    result = ScheduleCreator._human_cron(
        30, 9, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    )
    assert result == "Every weekdays at 09:30"


def test_human_cron_weekend():
    result = ScheduleCreator._human_cron(0, 8, ["Saturday", "Sunday"])
    assert result == "Every weekends at 08:00"


def test_human_cron_every_day():
    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    result = ScheduleCreator._human_cron(15, 12, all_days)
    assert result == "Every every day at 12:15"


def test_human_cron_single_day():
    result = ScheduleCreator._human_cron(45, 7, ["Friday"])
    assert "Fri" in result and "07:45" in result


def test_create_linux_cron_installs_entry():
    """_create_linux_cron must write a valid cron entry without errors."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)

    cmd_info = {"label": "Backup", "command": "/usr/bin/backup.sh"}

    list_result = MagicMock(returncode=0, stdout="# existing\n", stderr="")
    install_result = MagicMock(returncode=0, stdout="", stderr="")
    verify_result = MagicMock(
        returncode=0, stdout="# existing\n30 9 * * 1 /usr/bin/backup.sh\n", stderr=""
    )

    with (
        patch(
            "modules.schedule_creator.subprocess.run",
            side_effect=[list_result, install_result, verify_result],
        ) as mock_run,
        patch("modules.schedule_creator.QMessageBox"),
    ):
        result = creator._create_linux_cron(cmd_info, hour=9, minute=30, selected_days=["Monday"])

    assert result is True
    assert mock_run.call_count == 3  # crontab -l + crontab install + crontab -l verification


def test_create_linux_cron_empty_crontab():
    """returncode=1 from crontab -l (no crontab) must be treated as empty, not error."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)

    cmd_info = {"label": "Test", "command": "echo hello"}

    list_result = MagicMock(returncode=1, stdout="", stderr="no crontab for user")
    install_result = MagicMock(returncode=0, stdout="", stderr="")
    verify_result = MagicMock(returncode=0, stdout="0 10 * * 2 echo hello\n", stderr="")

    with (
        patch(
            "modules.schedule_creator.subprocess.run",
            side_effect=[list_result, install_result, verify_result],
        ),
        patch("modules.schedule_creator.QMessageBox"),
    ):
        result = creator._create_linux_cron(cmd_info, hour=10, minute=0, selected_days=["Tuesday"])

    assert result is True


def test_create_linux_cron_install_failure_returns_false():
    """A non-zero return from crontab install must cause _create_linux_cron to return False."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)

    cmd_info = {"label": "Fail", "command": "bad-cmd"}

    list_result = MagicMock(returncode=0, stdout="", stderr="")
    install_result = MagicMock(returncode=1, stdout="", stderr="permission denied")

    with (
        patch("modules.schedule_creator.subprocess.run", side_effect=[list_result, install_result]),
        patch("modules.schedule_creator.QMessageBox"),
    ):
        result = creator._create_linux_cron(cmd_info, hour=8, minute=0, selected_days=["Wednesday"])

    assert result is False


def test_create_schedule_dispatches_to_linux_on_non_windows():
    """create_schedule must call _create_linux_cron on non-Windows platforms."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    cmd_info = {"label": "X", "command": "x"}

    with (
        patch.object(creator, "_create_linux_cron", return_value=True) as mock_linux,
        patch("modules.schedule_creator.sys.platform", "linux"),
    ):
        result = creator.create_schedule(cmd_info, 9, 0, ["Monday"])

    mock_linux.assert_called_once()
    assert result is True


def test_create_schedule_dispatches_to_windows_on_win32():
    """create_schedule must call _create_windows_task when sys.platform == 'win32'."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    cmd_info = {"label": "X", "command": "x"}

    with (
        patch.object(creator, "_create_windows_task", return_value=True) as mock_win,
        patch("modules.schedule_creator.sys.platform", "win32"),
    ):
        result = creator.create_schedule(cmd_info, 9, 0, ["Monday"])

    mock_win.assert_called_once()
    assert result is True


# === NEW TESTS FOR ISSUE #82 ===


def test_validate_cron_expression_valid():
    """Valid cron expressions return True."""
    assert ScheduleCreator._validate_cron_expression("30 9 * * 1 /usr/bin/backup.sh") is True
    assert ScheduleCreator._validate_cron_expression("0 0 * * 0,6 /home/user/script.sh") is True
    assert ScheduleCreator._validate_cron_expression("* * * * * /bin/true") is True
    assert ScheduleCreator._validate_cron_expression("0 23 * * 0-7 /some/command") is True


def test_validate_cron_expression_invalid_minute():
    """minute > 59 returns False (defense-in-depth; UI already constrains this)."""
    assert ScheduleCreator._validate_cron_expression("60 9 * * 1 /cmd") is False
    assert ScheduleCreator._validate_cron_expression("99 0 * * * /cmd") is False


def test_validate_cron_expression_invalid_hour():
    """hour > 23 returns False (defense-in-depth; UI already constrains this)."""
    assert ScheduleCreator._validate_cron_expression("0 24 * * 1 /cmd") is False
    assert ScheduleCreator._validate_cron_expression("30 99 * * * /cmd") is False


def test_validate_cron_expression_invalid_day_of_week():
    """day-of-week with value 8+ or non-numeric returns False."""
    assert ScheduleCreator._validate_cron_expression("0 9 * * 8 /cmd") is False
    assert ScheduleCreator._validate_cron_expression("0 9 * * 0,1,8 /cmd") is False
    assert ScheduleCreator._validate_cron_expression("0 9 * * abc /cmd") is False


def test_validate_cron_expression_empty_command():
    """Expression with no command portion returns False."""
    assert ScheduleCreator._validate_cron_expression("0 9 * * *") is False
    assert ScheduleCreator._validate_cron_expression("0 9 * * * ") is False


def test_validate_cron_expression_newline_in_command():
    """Expression with embedded newline returns False."""
    assert ScheduleCreator._validate_cron_expression("0 9 * * * /cmd\nbad") is False


def test_validate_cron_expression_too_few_fields():
    """Expression with fewer than 6 fields returns False."""
    # Fewer than 6 fields = invalid
    assert ScheduleCreator._validate_cron_expression("0 9 * *") is False  # 4 fields
    assert ScheduleCreator._validate_cron_expression("0 9") is False  # 2 fields
    assert ScheduleCreator._validate_cron_expression("") is False  # empty
    # 5 fields is still too few (need minute hour * * day_of_week command)
    assert ScheduleCreator._validate_cron_expression("0 9 * * 1") is False  # 5 fields, no command
    # 6+ fields: 6 is min, more is OK (command can have spaces)
    assert ScheduleCreator._validate_cron_expression("0 9 * * 1 /cmd with spaces") is True


def test_create_linux_cron_validation_failure_does_not_write():
    """Mock _validate_cron_expression to return False; assert no crontab write, QMessageBox.critical called, returns False."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    cmd_info = {"label": "Test", "command": "/bin/true"}

    with (
        patch.object(creator, "_validate_cron_expression", return_value=False),
        patch("modules.schedule_creator.subprocess.run") as mock_run,
        patch("modules.schedule_creator.QMessageBox") as mock_msgbox,
    ):
        result = creator._create_linux_cron(cmd_info, hour=9, minute=30, selected_days=["Monday"])

    assert result is False
    mock_run.assert_not_called()
    mock_msgbox.critical.assert_called_once()
    # Check that the error message mentions the rejected expression
    call_args = mock_msgbox.critical.call_args
    assert "Invalid cron expression" in call_args[0][2] or "rejected" in call_args[0][2].lower()


def test_create_linux_cron_validation_success():
    """Mock _validate_cron_expression to return True; assert existing write path executes and returns True."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    cmd_info = {"label": "Test", "command": "/bin/true"}

    list_result = MagicMock(returncode=0, stdout="", stderr="")
    install_result = MagicMock(returncode=0, stdout="", stderr="")
    verify_result = MagicMock(returncode=0, stdout="30 9 * * 1 /bin/true\n", stderr="")

    with (
        patch.object(creator, "_validate_cron_expression", return_value=True),
        patch(
            "modules.schedule_creator.subprocess.run",
            side_effect=[list_result, install_result, verify_result],
        ) as mock_run,
        patch("modules.schedule_creator.QMessageBox"),
    ):
        result = creator._create_linux_cron(cmd_info, hour=9, minute=30, selected_days=["Monday"])

    assert result is True
    assert mock_run.call_count >= 3  # crontab -l + crontab install + crontab -l verification


def test_create_linux_cron_post_install_verification_fails():
    """Mock install to succeed but mock crontab -l to not contain entry; assert error dialog shown and returns False."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    cmd_info = {"label": "Test", "command": "/bin/true"}

    list_result = MagicMock(returncode=0, stdout="", stderr="")
    install_result = MagicMock(returncode=0, stdout="", stderr="")
    # The post-install verification does crontab -l and the entry is NOT found
    verify_result = MagicMock(returncode=0, stdout="old entry only\n", stderr="")

    with (
        patch.object(creator, "_validate_cron_expression", return_value=True),
        patch(
            "modules.schedule_creator.subprocess.run",
            side_effect=[list_result, install_result, verify_result],
        ),
        patch("modules.schedule_creator.QMessageBox") as mock_msgbox,
    ):
        result = creator._create_linux_cron(cmd_info, hour=9, minute=30, selected_days=["Monday"])

    assert result is False
    mock_msgbox.critical.assert_called_once()
    # Should mention that the entry was not found
    call_args = mock_msgbox.critical.call_args
    assert "not found" in call_args[0][2].lower() or "verification" in call_args[0][2].lower()


def test_show_dialog_returns_false_on_command_load_failure():
    """show_dialog returns False when command loading fails."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    svc.get_all_commands.side_effect = RuntimeError("load failed")

    with patch("modules.schedule_creator.QMessageBox"):
        result = creator.show_dialog()

    assert result is False


def test_show_dialog_returns_false_on_cancel():
    """show_dialog returns False when user cancels the dialog."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    svc.get_all_commands.return_value = [
        {"group": "Test", "label": "MyCmd", "command": "/bin/true"}
    ]

    with (
        patch("modules.schedule_creator.ScheduleDialog") as mock_dialog_cls,
        patch("modules.schedule_creator.QMessageBox"),
    ):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
        mock_dialog_cls.return_value = mock_dialog
        result = creator.show_dialog()

    assert result is False


def test_show_dialog_returns_true_on_accept():
    """show_dialog returns True when user successfully creates a schedule."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    svc.get_all_commands.return_value = [
        {"group": "Test", "label": "MyCmd", "command": "/bin/true"}
    ]

    with (
        patch("modules.schedule_creator.ScheduleDialog") as mock_dialog_cls,
        patch("modules.schedule_creator.QMessageBox"),
        patch.object(creator, "create_schedule", return_value=True),
    ):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
        mock_dialog.get_schedule.return_value = {
            "command_info": {"group": "Test", "label": "MyCmd", "command": "/bin/true"},
            "hour": 9,
            "minute": 0,
            "days": ["Monday"],
        }
        mock_dialog_cls.return_value = mock_dialog
        result = creator.show_dialog()

    assert result is True
