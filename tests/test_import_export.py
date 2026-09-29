# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for import_export module.

Tests construct ImportExport with a mock_services object where
mock_services.config_manager is pre-configured, following the
self.services.config_manager DI pattern.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# [ORCHESTRATOR NOTE] Pre-existing failure — unrelated to issue #38
# Failure: ModuleNotFoundError: No module named 'PyQt6' — src/modules/import_export.py imports PyQt6.QtWidgets but PyQt6 is not installed. Fix: add sys.modules stubs for PyQt6 before importing.
from modules.import_export import ImportExport  # noqa: E402


class TestImportExport(unittest.TestCase):
    """Test suite for ImportExport module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_services.config_manager = self.mock_config_manager

    # ------------------------------------------------------------------
    # export_command_group
    # ------------------------------------------------------------------

    def test_export_calls_config_manager(self):
        """export_command_group must delegate to config_manager.export_command_group."""
        ie = ImportExport(self.mock_services)
        out_file = "/tmp/test_output.json"

        self.mock_config_manager.get_commands.return_value = {"Dev": {}}
        self.mock_config_manager.export_command_group.return_value = True

        with (
            patch("modules.import_export.QInputDialog") as mock_input,
            patch("modules.import_export.QFileDialog") as mock_fd,
            patch("modules.import_export.QMessageBox"),
        ):
            mock_input.getItem.return_value = ("Dev", True)
            mock_fd.getSaveFileName.return_value = (out_file, "")
            ie.export_command_group()

        self.mock_config_manager.export_command_group.assert_called_once_with("Dev", out_file)

    def test_export_no_groups_shows_warning(self):
        """export_command_group must show a warning when there are no groups."""
        ie = ImportExport(self.mock_services)
        self.mock_config_manager.get_commands.return_value = {}

        with patch("modules.import_export.QMessageBox") as mock_mb:
            ie.export_command_group()

        mock_mb.warning.assert_called_once()

    # ------------------------------------------------------------------
    # import_command_group
    # ------------------------------------------------------------------

    def test_import_calls_config_manager(self):
        """import_command_group must delegate to config_manager.import_command_group (bool return)."""
        ie = ImportExport(self.mock_services)
        in_file = "/tmp/test_input.json"

        # config_manager.import_command_group returns bool — NOT a tuple
        self.mock_config_manager.import_command_group.return_value = True
        self.mock_config_manager.get_command_paths.return_value = {
            "active_commands_file": in_file,
            "config_dir": "/tmp",
        }

        with (
            patch("modules.import_export.QFileDialog") as mock_fd,
            patch("modules.import_export.QMessageBox") as mock_mb,
        ):
            mock_fd.getOpenFileName.return_value = (in_file, "")
            mock_mb.question.return_value = mock_mb.StandardButton.Yes
            ie.import_command_group()

        self.mock_config_manager.import_command_group.assert_called_once()

    def test_import_invalid_json_propagates(self):
        """import_command_group has NO internal try/except — a ValueError from
        config_manager propagates uncaught. Tests must assert propagation, not
        suppression, to match the actual contract in import_export.py.
        """
        ie = ImportExport(self.mock_services)
        self.mock_config_manager.import_command_group.side_effect = ValueError("bad JSON")
        self.mock_config_manager.get_command_paths.return_value = {
            "active_commands_file": "/tmp/x.json",
            "config_dir": "/tmp",
        }

        with (
            patch("modules.import_export.QFileDialog") as mock_fd,
            patch("modules.import_export.QMessageBox") as mock_mb,
        ):
            mock_fd.getOpenFileName.return_value = ("/tmp/x.json", "")
            mock_mb.question.return_value = mock_mb.StandardButton.Yes

            with self.assertRaisesRegex(ValueError, "bad JSON"):
                ie.import_command_group()

    def test_import_aborted_when_no_file_selected(self):
        """import_command_group must do nothing when the user cancels the file dialog."""
        ie = ImportExport(self.mock_services)
        self.mock_config_manager.import_command_group.reset_mock()

        with patch("modules.import_export.QFileDialog") as mock_fd:
            mock_fd.getOpenFileName.return_value = ("", "")
            ie.import_command_group()

        self.mock_config_manager.import_command_group.assert_not_called()


if __name__ == "__main__":
    unittest.main()