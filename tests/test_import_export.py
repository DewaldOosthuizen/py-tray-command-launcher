import sys
from unittest.mock import MagicMock, patch

_pyqt6 = MagicMock()
sys.modules.setdefault("PyQt6", _pyqt6)
sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6.QtWidgets)
sys.modules.setdefault("PyQt6.QtCore", _pyqt6.QtCore)
sys.modules.setdefault("PyQt6.QtGui", _pyqt6.QtGui)

_cm_mock = MagicMock()
sys.modules["core.config_manager"] = _cm_mock

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.import_export import ImportExport
import pytest


def _make_ie():
    svc = MagicMock()
    return ImportExport(svc)


def test_export_calls_config_manager(tmp_path):
    """export_command_group must delegate to config_manager.export_command_group."""
    ie = _make_ie()
    out_file = str(tmp_path / "out.json")

    _cm_mock.config_manager.get_commands.return_value = {"Dev": {}}
    _cm_mock.config_manager.export_command_group.return_value = True

    with patch("modules.import_export.QInputDialog") as mock_input, \
         patch("modules.import_export.QFileDialog") as mock_fd, \
         patch("modules.import_export.QMessageBox"):
        mock_input.getItem.return_value = ("Dev", True)
        mock_fd.getSaveFileName.return_value = (out_file, "")
        ie.export_command_group()

    _cm_mock.config_manager.export_command_group.assert_called_once_with("Dev", out_file)


def test_export_no_groups_shows_warning():
    """export_command_group must show a warning when there are no groups."""
    ie = _make_ie()
    _cm_mock.config_manager.get_commands.return_value = {}

    with patch("modules.import_export.QMessageBox") as mock_mb:
        ie.export_command_group()

    mock_mb.warning.assert_called_once()


def test_import_calls_config_manager(tmp_path):
    """import_command_group must delegate to config_manager.import_command_group (bool return)."""
    ie = _make_ie()
    in_file = str(tmp_path / "in.json")

    # config_manager.import_command_group returns bool — NOT a tuple
    _cm_mock.config_manager.import_command_group.return_value = True
    _cm_mock.config_manager.get_command_paths.return_value = {
        "active_commands_file": in_file,
        "config_dir": str(tmp_path),
    }

    with patch("modules.import_export.QFileDialog") as mock_fd, \
         patch("modules.import_export.QMessageBox") as mock_mb:
        mock_fd.getOpenFileName.return_value = (in_file, "")
        mock_mb.question.return_value = mock_mb.StandardButton.No
        ie.import_command_group()

    _cm_mock.config_manager.import_command_group.assert_called_once()


def test_import_invalid_json_propagates():
    """import_command_group has NO internal try/except — a ValueError from
    config_manager propagates uncaught. Tests must assert propagation, not
    suppression, to match the actual contract in import_export.py.
    """
    ie = _make_ie()
    _cm_mock.config_manager.import_command_group.side_effect = ValueError("bad JSON")
    _cm_mock.config_manager.get_command_paths.return_value = {
        "active_commands_file": "/tmp/x.json",
        "config_dir": "/tmp",
    }

    with patch("modules.import_export.QFileDialog") as mock_fd, \
         patch("modules.import_export.QMessageBox") as mock_mb:
        mock_fd.getOpenFileName.return_value = ("/tmp/x.json", "")
        mock_mb.question.return_value = mock_mb.StandardButton.No

        with pytest.raises(ValueError, match="bad JSON"):
            ie.import_command_group()


def test_import_aborted_when_no_file_selected():
    """import_command_group must do nothing when the user cancels the file dialog."""
    ie = _make_ie()
    _cm_mock.config_manager.import_command_group.reset_mock()

    with patch("modules.import_export.QFileDialog") as mock_fd:
        mock_fd.getOpenFileName.return_value = ("", "")
        ie.import_command_group()

    _cm_mock.config_manager.import_command_group.assert_not_called()
