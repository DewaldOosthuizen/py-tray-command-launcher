"""Tests for backup_restore module.

Tests call the real public methods (backup_commands, restore_commands) while
patching modules.backup_restore.config_manager and Qt dialogs so that no
filesystem I/O or GUI interactions occur.
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock, call

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.backup_restore import BackupRestore


class TestBackupRestore(unittest.TestCase):
    """Test suite for BackupRestore module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.mock_config_manager = MagicMock()

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            self.backup = BackupRestore(self.mock_services)

    # ------------------------------------------------------------------
    # backup_commands
    # ------------------------------------------------------------------

    def test_backup_commands_calls_config_manager(self):
        """backup_commands should delegate to config_manager.backup_commands."""
        self.mock_config_manager.backup_commands.return_value = "/tmp/commands_backup.json"

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            with patch('modules.backup_restore.QMessageBox'):
                self.backup.backup_commands()

        self.mock_config_manager.backup_commands.assert_called_once()

    def test_backup_commands_success_shows_information(self):
        """backup_commands should show an information dialog on success."""
        self.mock_config_manager.backup_commands.return_value = "/tmp/commands_backup.json"

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            with patch('modules.backup_restore.QMessageBox') as mock_msgbox:
                self.backup.backup_commands()

        mock_msgbox.information.assert_called_once()

    def test_backup_commands_failure_shows_warning(self):
        """backup_commands should show a warning dialog when backup fails."""
        self.mock_config_manager.backup_commands.return_value = ""

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            with patch('modules.backup_restore.QMessageBox') as mock_msgbox:
                self.backup.backup_commands()

        mock_msgbox.warning.assert_called_once()

    # ------------------------------------------------------------------
    # restore_commands
    # ------------------------------------------------------------------

    def test_restore_commands_no_backups_shows_information(self):
        """restore_commands should show an info dialog when no backups exist."""
        self.mock_config_manager.list_backups.return_value = []

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            with patch('modules.backup_restore.QMessageBox') as mock_msgbox:
                self.backup.restore_commands()

        mock_msgbox.information.assert_called_once()
        self.mock_config_manager.restore_from_backup.assert_not_called()

    def test_restore_commands_calls_restore_on_confirmation(self):
        """restore_commands should call config_manager.restore_from_backup when confirmed."""
        backup_path = "/tmp/commands_20260410_100000.json"
        self.mock_config_manager.list_backups.return_value = [
            (backup_path, "2026-04-10 10:00:00")
        ]
        self.mock_config_manager.restore_from_backup.return_value = True

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            with patch('modules.backup_restore.QMessageBox') as mock_msgbox:
                with patch('modules.backup_restore.QInputDialog') as mock_dialog:
                    mock_dialog.getItem.return_value = (
                        "2026-04-10 10:00:00 - commands_20260410_100000.json", True
                    )
                    mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes
                    self.backup.restore_commands()

        self.mock_config_manager.restore_from_backup.assert_called_once_with(backup_path)

    def test_restore_commands_reloads_on_success(self):
        """restore_commands should reload commands after a successful restore."""
        backup_path = "/tmp/commands_20260410_100000.json"
        self.mock_config_manager.list_backups.return_value = [
            (backup_path, "2026-04-10 10:00:00")
        ]
        self.mock_config_manager.restore_from_backup.return_value = True

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            with patch('modules.backup_restore.QMessageBox') as mock_msgbox:
                with patch('modules.backup_restore.QInputDialog') as mock_dialog:
                    mock_dialog.getItem.return_value = (
                        "2026-04-10 10:00:00 - commands_20260410_100000.json", True
                    )
                    mock_msgbox.question.return_value = mock_msgbox.StandardButton.Yes
                    self.backup.restore_commands()

        self.mock_services.reload_commands.assert_called_once_with(rebuild_menu=True)

    def test_restore_commands_cancelled_by_user(self):
        """restore_commands should not restore when user cancels the dialog."""
        backup_path = "/tmp/commands_20260410_100000.json"
        self.mock_config_manager.list_backups.return_value = [
            (backup_path, "2026-04-10 10:00:00")
        ]

        with patch('modules.backup_restore.config_manager', self.mock_config_manager):
            with patch('modules.backup_restore.QMessageBox'):
                with patch('modules.backup_restore.QInputDialog') as mock_dialog:
                    mock_dialog.getItem.return_value = ("", False)
                    self.backup.restore_commands()

        self.mock_config_manager.restore_from_backup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
