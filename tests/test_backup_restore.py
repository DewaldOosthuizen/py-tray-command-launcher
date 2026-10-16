# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for backup_restore module.

Tests call the real public methods (backup_commands, restore_commands) while
patching modules.backup_restore.config_manager and Qt dialogs so that no
filesystem I/O or GUI interactions occur.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.backup_restore import BackupRestore  # noqa: E402


class TestBackupRestore(unittest.TestCase):
    """Test suite for BackupRestore module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_services.config_manager = self.mock_config_manager

        self.backup = BackupRestore(self.mock_services)

    # ------------------------------------------------------------------
    # backup_commands
    # ------------------------------------------------------------------

    def test_backup_commands_calls_config_manager(self):
        """backup_commands should delegate to config_manager.backup_commands."""
        self.mock_config_manager.backup_commands.return_value = "/tmp/commands_backup.json"
        self.backup.backup_commands()

        self.mock_config_manager.backup_commands.assert_called_once()

    def test_backup_commands_success_shows_information(self):
        """backup_commands should show an information dialog on success."""
        self.mock_config_manager.backup_commands.return_value = "/tmp/commands_backup.json"

        with patch("modules.backup_restore.QMessageBox") as mock_msgbox:
            self.backup.backup_commands()

        mock_msgbox.information.assert_called_once()

    def test_backup_commands_failure_shows_warning(self):
        """backup_commands should show a warning dialog when backup fails."""
        self.mock_config_manager.backup_commands.return_value = ""

        with patch("modules.backup_restore.QMessageBox") as mock_msgbox:
            self.backup.backup_commands()

        mock_msgbox.warning.assert_called_once()

    # ------------------------------------------------------------------
    # restore_commands
    # ------------------------------------------------------------------

    def test_restore_commands_no_backups_shows_information(self):
        """restore_commands should show an info dialog when no backups exist."""
        self.mock_config_manager.list_backups.return_value = []

        with patch("modules.backup_restore.QMessageBox") as mock_msgbox:
            self.backup.restore_commands()

        mock_msgbox.information.assert_called_once()
        self.mock_config_manager.restore_from_backup.assert_not_called()

    def test_restore_commands_calls_restore_on_confirmation(self):
        """restore_commands should call config_manager.restore_from_backup when confirmed."""
        backup_path = "/tmp/commands_20260410_100000.json"
        self.mock_config_manager.list_backups.return_value = [(backup_path, "2026-04-10 10:00:00")]
        self.mock_config_manager.restore_from_backup.return_value = True

        with patch("modules.backup_restore.QMessageBox") as mock_msgbox:
            with patch("modules.backup_restore.QInputDialog") as mock_dialog:
                mock_dialog.getItem.return_value = (
                    "2026-04-10 10:00:00 - commands_20260410_100000.json",
                    True,
                )
                mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes
                self.backup.restore_commands()

        self.mock_config_manager.restore_from_backup.assert_called_once_with(backup_path)

    def test_restore_commands_reloads_on_success(self):
        """restore_commands should reload commands after a successful restore."""
        backup_path = "/tmp/commands_20260410_100000.json"
        self.mock_config_manager.list_backups.return_value = [(backup_path, "2026-04-10 10:00:00")]
        self.mock_config_manager.restore_from_backup.return_value = True

        with patch("modules.backup_restore.QMessageBox") as mock_msgbox:
            with patch("modules.backup_restore.QInputDialog") as mock_dialog:
                mock_dialog.getItem.return_value = (
                    "2026-04-10 10:00:00 - commands_20260410_100000.json",
                    True,
                )
                mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes
                self.backup.restore_commands()

        self.mock_services.reload_commands.assert_called_once_with(rebuild_menu=True)

    def test_restore_commands_cancelled_by_user(self):
        """restore_commands should not restore when user cancels the dialog."""
        backup_path = "/tmp/commands_20260410_100000.json"
        self.mock_config_manager.list_backups.return_value = [(backup_path, "2026-04-10 10:00:00")]

        with patch("modules.backup_restore.QMessageBox"):
            with patch("modules.backup_restore.QInputDialog") as mock_dialog:
                mock_dialog.getItem.return_value = ("", False)
                self.backup.restore_commands()

        self.mock_config_manager.restore_from_backup.assert_not_called()


# ------------------------------------------------------------------
# ConfigManager backup/restore/import/export edge cases (pytest style)
# ------------------------------------------------------------------
import json as _json
import os as _os
import shutil as _shutil
from unittest.mock import patch as _patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from core.config_manager import ConfigManager, ConfigurationError  # noqa: E402


def _bare_mgr(tmp_path):
    mgr = ConfigManager.__new__(ConfigManager)
    mgr._initialized = False
    mgr._commands_cache = None
    mgr._history_cache = None
    mgr._favorites_cache = None
    mgr._settings_cache = None
    mgr._is_windows = False
    mgr._commands_override = None
    mgr.config_dir = tmp_path
    mgr.backup_dir = tmp_path / "backups"
    mgr.backup_dir.mkdir(exist_ok=True)
    mgr.commands_file = tmp_path / "commands.json"
    mgr.win_commands_file = tmp_path / "win-commands.json"
    mgr.history_file = tmp_path / "history.json"
    mgr.favorites_file = tmp_path / "favorites.json"
    mgr.settings_file = tmp_path / "settings.json"
    mgr.defaults_dir = tmp_path / "defaults"
    return mgr


def test_backup_commands_missing_source(tmp_path):
    mgr = _bare_mgr(tmp_path)
    assert mgr.backup_commands() == ""


def test_backup_commands_success(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text(_json.dumps({"G": {"x": {"command": "echo"}}}), encoding="utf-8")
    path = mgr.backup_commands()
    assert path != ""
    assert _os.path.exists(path)


def test_backup_commands_oserror(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text("{}", encoding="utf-8")
    with _patch("shutil.copy2", side_effect=OSError("disk")):
        assert mgr.backup_commands() == ""


def test_list_backups_missing_dir(tmp_path):
    mgr = _bare_mgr(tmp_path)
    _shutil.rmtree(mgr.backup_dir)
    assert mgr.list_backups() == []


def test_list_backups_oserror(tmp_path):
    mgr = _bare_mgr(tmp_path)
    with _patch("os.listdir", side_effect=OSError("boom")):
        assert mgr.list_backups() == []


def test_list_backups_sort_and_format(tmp_path):
    mgr = _bare_mgr(tmp_path)
    f1 = mgr.backup_dir / "commands_20260101_120000.json"
    f2 = mgr.backup_dir / "commands_20260202_130000.json"
    f1.write_text("{}", encoding="utf-8")
    f2.write_text("{}", encoding="utf-8")
    res = mgr.list_backups()
    assert len(res) == 2
    assert res[0][1] > res[1][1]


def test_restore_from_backup_success(tmp_path):
    mgr = _bare_mgr(tmp_path)
    src = tmp_path / "b.json"
    src.write_text(_json.dumps({"Restore": {"c": {"command": "ls"}}}), encoding="utf-8")
    mgr.commands_file.write_text(_json.dumps({"Orig": {}}), encoding="utf-8")
    assert mgr.restore_from_backup(str(src)) is True
    assert mgr._commands_cache is None
    assert "Restore" in _json.loads(mgr.commands_file.read_text())


def test_restore_from_backup_oserror(tmp_path):
    mgr = _bare_mgr(tmp_path)
    target_content = _json.dumps({"Orig": {}})
    mgr.commands_file.write_text(target_content, encoding="utf-8")
    with _patch("shutil.copy2", side_effect=OSError("boom")):
        assert mgr.restore_from_backup("/nope.json") is False
    assert mgr.commands_file.read_text() == target_content


def test_restore_creates_safety_backup(tmp_path):
    mgr = _bare_mgr(tmp_path)
    src = tmp_path / "b.json"
    src.write_text("{}", encoding="utf-8")
    mgr.commands_file.write_text("{}", encoding="utf-8")
    with _patch.object(mgr, "backup_commands", wraps=mgr.backup_commands) as mock_bk:
        mgr.restore_from_backup(str(src))
        mock_bk.assert_called_once()


def test_import_rejects_non_dict(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text(_json.dumps({"G": {}}), encoding="utf-8")
    bad = tmp_path / "imp.json"
    bad.write_text(_json.dumps([1, 2]), encoding="utf-8")
    assert mgr.import_command_group(str(bad)) is False


def test_import_rejects_corrupt_json(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text(_json.dumps({"G": {}}), encoding="utf-8")
    bad = tmp_path / "imp.json"
    bad.write_text("{bad", encoding="utf-8")
    assert mgr.import_command_group(str(bad)) is False


def test_import_conflict_no_overwrite(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text(_json.dumps({"G": {}}), encoding="utf-8")
    imp = tmp_path / "imp.json"
    imp.write_text(_json.dumps({"G": {"new": {"command": "x"}}}), encoding="utf-8")
    assert mgr.import_command_group(str(imp), overwrite=False) is False


def test_import_overwrite_success(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text(_json.dumps({"G": {}}), encoding="utf-8")
    imp = tmp_path / "imp.json"
    imp.write_text(_json.dumps({"H": {"new": {"command": "x"}}}), encoding="utf-8")
    assert mgr.import_command_group(str(imp), overwrite=True) is True
    data = _json.loads(mgr.commands_file.read_text())
    assert "H" in data


def test_export_unknown_group(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text(_json.dumps({"G": {}}), encoding="utf-8")
    out = tmp_path / "out.json"
    assert mgr.export_command_group("Nope", str(out)) is False


def test_export_writes_atomically(tmp_path):
    mgr = _bare_mgr(tmp_path)
    mgr.commands_file.write_text(_json.dumps({"G": {"x": {"command": "echo"}}}), encoding="utf-8")
    out = tmp_path / "out.json"
    assert mgr.export_command_group("G", str(out)) is True
    assert out.exists()
    assert _json.loads(out.read_text()) == {"G": {"x": {"command": "echo"}}}


if __name__ == "__main__":
    unittest.main()
