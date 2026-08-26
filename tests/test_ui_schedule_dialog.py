# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys
from unittest.mock import MagicMock, patch

# Use the PyQt6 stub from conftest.py if available, otherwise create a simple one
if "PyQt6" not in sys.modules:
    _pyqt6 = MagicMock()
    sys.modules.setdefault("PyQt6", _pyqt6)
    sys.modules.setdefault("PyQt6.QtWidgets", _pyqt6.QtWidgets)
    sys.modules.setdefault("PyQt6.QtCore", _pyqt6.QtCore)
    sys.modules.setdefault("PyQt6.QtGui", _pyqt6.QtGui)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestScheduleDialog:
    """Tests for ScheduleDialog — the new standalone QDialog extracted from
    ScheduleCreator.show_dialog().

    These tests instantiate the real ScheduleDialog class (with mocked Qt
    widgets) so they exercise the actual dialog wiring, select-all/none
    toggles, and get_schedule() contract.
    """

    _commands = [
        {"group": "System", "label": "Backup", "command": "/usr/bin/backup.sh"},
        {"group": "Dev", "label": "Run Server", "command": "python server.py"},
    ]

    _days = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]

    def _make_dialog(self):
        """Build a ScheduleDialog with controllable mocked Qt widgets.

        Patch widget constructors, then override findChild/findChildren
        so get_schedule()'s widget lookups return the right mock per call.
        """
        with (
            patch("ui.schedule_dialog.QDialog"),
            patch("ui.schedule_dialog.QComboBox") as combo_cls,
            patch("ui.schedule_dialog.QTimeEdit") as time_cls,
            patch("ui.schedule_dialog.QCheckBox") as cb_cls,
            patch("ui.schedule_dialog.QLabel") as label_cls,
            patch("ui.schedule_dialog.QPushButton"),
            patch("ui.schedule_dialog.QVBoxLayout"),
            patch("ui.schedule_dialog.QHBoxLayout"),
            patch("ui.schedule_dialog.QGridLayout"),
        ):
            combo = MagicMock()
            combo.addItem = MagicMock()
            combo_cls.return_value = combo

            time_edit = MagicMock()
            time_edit.time.return_value.minute.return_value = 30
            time_edit.time.return_value.hour.return_value = 9
            time_cls.return_value = time_edit

            mock_cbs = {}
            for day in self._days:
                cb = MagicMock()
                cb.isChecked.return_value = False
                cb.objectName = MagicMock(return_value=f"day_{day}")
                cb.setChecked = MagicMock()
                mock_cbs[day] = cb

            def _cb_factory(label_text):
                return mock_cbs[label_text]

            cb_cls.side_effect = _cb_factory

            preview_label = MagicMock()
            label_cls.return_value = preview_label

            from ui.schedule_dialog import ScheduleDialog

            dialog = ScheduleDialog(self._commands)

            # get_schedule() calls findChild twice: QComboBox then QTimeEdit.
            # Dispatch by call order so the mocks are stable even after the
            # patch context exits (the mocks are stored on the dialog).
            _call_idx = [0]

            def _find_child(kind):
                idx = _call_idx[0]
                _call_idx[0] += 1
                if idx == 0:
                    return combo
                if idx == 1:
                    return time_edit
                return None

            dialog.findChild = MagicMock(side_effect=_find_child)
            dialog.findChildren = MagicMock(return_value=list(mock_cbs.values()))
            dialog._command_combo = combo
            dialog._time_edit = time_edit
            dialog._days_checkboxes = mock_cbs
            dialog._preview_label = preview_label
            return dialog

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_dialog_populates_command_combo(self):
        """ScheduleDialog adds one combo entry per command."""
        with (
            patch("ui.schedule_dialog.QDialog"),
            patch("ui.schedule_dialog.QComboBox") as combo_cls,
            patch("ui.schedule_dialog.QTimeEdit") as time_cls,
            patch("ui.schedule_dialog.QCheckBox"),
            patch("ui.schedule_dialog.QLabel"),
            patch("ui.schedule_dialog.QPushButton"),
            patch("ui.schedule_dialog.QVBoxLayout"),
            patch("ui.schedule_dialog.QHBoxLayout"),
            patch("ui.schedule_dialog.QGridLayout"),
        ):
            combo = MagicMock()
            combo.addItem = MagicMock()
            combo_cls.return_value = combo

            # QTimeEdit must be mocked so _update_preview() doesn't hit
            # a bare MagicMock with f-string formatting.
            time_edit = MagicMock()
            time_edit.time.return_value.minute.return_value = 30
            time_edit.time.return_value.hour.return_value = 9
            time_cls.return_value = time_edit

            from ui.schedule_dialog import ScheduleDialog

            ScheduleDialog(self._commands)
            assert combo.addItem.call_count == len(self._commands)

    # ------------------------------------------------------------------
    # Day toggles
    # ------------------------------------------------------------------

    def test_select_all_checks_every_day(self):
        """_select_all_days calls setChecked(True) on every checkbox."""
        dialog = self._make_dialog()
        dialog._select_all_days()
        for cb in dialog._days_checkboxes.values():
            cb.setChecked.assert_called_with(True)

    def test_select_none_unchecks_every_day(self):
        """_select_none_days calls setChecked(False) on every checkbox."""
        dialog = self._make_dialog()
        dialog._select_none_days()
        for cb in dialog._days_checkboxes.values():
            cb.setChecked.assert_called_with(False)

    # ------------------------------------------------------------------
    # get_schedule()
    # ------------------------------------------------------------------

    def test_get_schedule_returns_dict_when_valid(self):
        """get_schedule() returns command, hour, minute, days for a valid selection."""
        dialog = self._make_dialog()
        dialog._command_combo.currentText.return_value = "System → Backup"
        dialog._days_checkboxes["Monday"].isChecked.return_value = True
        dialog._days_checkboxes["Wednesday"].isChecked.return_value = True

        schedule = dialog.get_schedule()
        assert schedule is not None
        assert schedule["command_info"] == {
            "group": "System", "label": "Backup", "command": "/usr/bin/backup.sh"
        }
        assert schedule["hour"] == 9
        assert schedule["minute"] == 30
        assert schedule["days"] == ["Monday", "Wednesday"]

    def test_get_schedule_returns_none_when_no_command(self):
        """get_schedule() returns None when no command is selected."""
        dialog = self._make_dialog()
        dialog._command_combo.currentText.return_value = ""
        dialog._days_checkboxes["Monday"].isChecked.return_value = True
        assert dialog.get_schedule() is None

    def test_get_schedule_returns_none_when_no_days(self):
        """get_schedule() returns None when no days are selected."""
        dialog = self._make_dialog()
        dialog._command_combo.currentText.return_value = "System → Backup"
        assert dialog.get_schedule() is None

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def test_update_preview_sets_human_cron_text(self):
        """_update_preview writes a human-readable cron description.

        The preview label is also set once during _setup_ui (no days selected
        yet), so we check the LAST call rather than call count == 1.
        """
        dialog = self._make_dialog()
        dialog._days_checkboxes["Monday"].isChecked.return_value = True
        dialog._days_checkboxes["Wednesday"].isChecked.return_value = True
        dialog._update_preview()
        dialog._preview_label.setText.assert_called()
        call_text = dialog._preview_label.setText.call_args[0][0]
        assert "Mon" in call_text
        assert "Wed" in call_text
        assert "09:30" in call_text
