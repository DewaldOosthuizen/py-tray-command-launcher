import sys
from unittest.mock import MagicMock, patch

_pyqt6 = MagicMock()
sys.modules.setdefault("PyQt6", _pyqt6)
sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6.QtWidgets)
sys.modules.setdefault("PyQt6.QtCore", _pyqt6.QtCore)
sys.modules.setdefault("PyQt6.QtGui", _pyqt6.QtGui)
sys.modules.setdefault("core.config_manager", MagicMock())

import os, sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.schedule_creator import ScheduleCreator


def test_human_cron_weekdays():
    result = ScheduleCreator._human_cron(30, 9, ["Monday","Tuesday","Wednesday","Thursday","Friday"])
    assert result == "Every weekdays at 09:30"


def test_human_cron_weekend():
    result = ScheduleCreator._human_cron(0, 8, ["Saturday", "Sunday"])
    assert result == "Every weekends at 08:00"


def test_human_cron_every_day():
    all_days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
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

    with patch("modules.schedule_creator.subprocess.run",
               side_effect=[list_result, install_result]) as mock_run, \
         patch("modules.schedule_creator.QMessageBox"):
        result = creator._create_linux_cron(cmd_info, hour=9, minute=30,
                                             selected_days=["Monday"])

    assert result is True
    assert mock_run.call_count == 2


def test_create_linux_cron_empty_crontab():
    """returncode=1 from crontab -l (no crontab) must be treated as empty, not error."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)

    cmd_info = {"label": "Test", "command": "echo hello"}

    list_result = MagicMock(returncode=1, stdout="", stderr="no crontab for user")
    install_result = MagicMock(returncode=0, stdout="", stderr="")

    with patch("modules.schedule_creator.subprocess.run",
               side_effect=[list_result, install_result]), \
         patch("modules.schedule_creator.QMessageBox"):
        result = creator._create_linux_cron(cmd_info, hour=10, minute=0,
                                             selected_days=["Tuesday"])

    assert result is True


def test_create_linux_cron_install_failure_returns_false():
    """A non-zero return from crontab install must cause _create_linux_cron to return False."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)

    cmd_info = {"label": "Fail", "command": "bad-cmd"}

    list_result = MagicMock(returncode=0, stdout="", stderr="")
    install_result = MagicMock(returncode=1, stdout="", stderr="permission denied")

    with patch("modules.schedule_creator.subprocess.run",
               side_effect=[list_result, install_result]), \
         patch("modules.schedule_creator.QMessageBox"):
        result = creator._create_linux_cron(cmd_info, hour=8, minute=0,
                                             selected_days=["Wednesday"])

    assert result is False


def test_create_schedule_dispatches_to_linux_on_non_windows():
    """create_schedule must call _create_linux_cron on non-Windows platforms."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    cmd_info = {"label": "X", "command": "x"}

    with patch.object(creator, "_create_linux_cron", return_value=True) as mock_linux, \
         patch("modules.schedule_creator.sys.platform", "linux"):
        result = creator.create_schedule(cmd_info, 9, 0, ["Monday"])

    mock_linux.assert_called_once()
    assert result is True


def test_create_schedule_dispatches_to_windows_on_win32():
    """create_schedule must call _create_windows_task when sys.platform == 'win32'."""
    svc = MagicMock()
    creator = ScheduleCreator(svc)
    cmd_info = {"label": "X", "command": "x"}

    with patch.object(creator, "_create_windows_task", return_value=True) as mock_win, \
         patch("modules.schedule_creator.sys.platform", "win32"):
        result = creator.create_schedule(cmd_info, 9, 0, ["Monday"])

    mock_win.assert_called_once()
    assert result is True
