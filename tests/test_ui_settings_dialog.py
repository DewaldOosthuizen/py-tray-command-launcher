import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ui.settings_dialog import SettingsDialog


@pytest.mark.skipif(
    os.environ.get("PY_TRAY_NO_STUB") == "1",
    reason="The dedicated probe is already running with real Qt widgets.",
)
def test_settings_dialog_responsive_real_qt_regressions():
    """Run #163 display regressions in an isolated process using real Qt."""
    project_root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PY_TRAY_NO_STUB"] = "1"
    environment["QT_QPA_PLATFORM"] = "offscreen"
    test_file = project_root / "tests" / "qt_integration" / "test_settings_dialog_responsive.py"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-cov", str(test_file)],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def _make_services_with_settings(settings):
    """Return a MagicMock app services whose config manager returns *settings*."""
    mock_services = MagicMock()
    mock_services.get_all_commands.return_value = [
        {
            "group": "System",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": False,
            "showOutput": False,
        },
        {
            "group": "System",
            "label": "Editor",
            "command": "gedit",
            "confirm": False,
            "showOutput": False,
        },
        {
            "group": "Git",
            "label": "Status",
            "command": "git status",
            "confirm": True,
            "showOutput": True,
        },
    ]
    mock_services.config_manager = MagicMock()
    mock_services.config_manager.get_settings.return_value = settings
    mock_services.config_manager.save_settings = MagicMock()
    return mock_services


def test_settings_dialog_instantiates(qtbot):
    mock_services = MagicMock()
    theme_manager = MagicMock()
    dialog = SettingsDialog(mock_services, theme_manager=theme_manager)
    qtbot.addWidget(dialog)
    assert dialog is not None


def test_settings_dialog_pinned_commands_group_box(qtbot):
    """The Pinned Commands group box is built and populated from the model."""
    settings = {
        "quick_launch_bar": {
            "visible": True,
            "hotkey": "ctrl+shift+b",
            "pinned": [
                {
                    "group": "System",
                    "label": "Terminal",
                    "command": "gnome-terminal",
                    "confirm": False,
                    "showOutput": False,
                },
            ],
        }
    }
    mock_services = MagicMock()
    # The available list is populated from services: the three known commands.
    mock_services.get_all_commands.return_value = [
        {
            "group": "System",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": False,
            "showOutput": False,
        },
        {
            "group": "System",
            "label": "Editor",
            "command": "gedit",
            "confirm": False,
            "showOutput": False,
        },
        {
            "group": "Git",
            "label": "Status",
            "command": "git status",
            "confirm": True,
            "showOutput": True,
        },
    ]
    mock_services.config_manager = MagicMock()
    mock_services.config_manager.get_settings.return_value = settings
    mock_services.config_manager.save_settings = MagicMock()
    theme_manager = MagicMock()

    dialog = SettingsDialog(
        mock_services,
        theme_manager=theme_manager,
        quick_launch_bar=None,
    )
    qtbot.addWidget(dialog)

    pin_manager = dialog._qlb_pin_manager
    assert pin_manager is not None
    # _settings is the same dict the dialog will persist (no refresh).
    assert dialog._settings is settings
    # Model is loaded from settings on construction.
    assert len(pin_manager._pinned_items) == 1
    assert pin_manager._pinned_items[0]["label"] == "Terminal"
    # Available list is populated from services.
    assert len(pin_manager._available_items) == 3


def test_settings_dialog_pinned_commands_add_remove_move(qtbot):
    """Add >>, Remove, Move Up and Move Down act on the model dicts in order."""
    settings = {"quick_launch_bar": {"visible": True, "hotkey": "ctrl+shift+b", "pinned": []}}
    mock_services = _make_services_with_settings(settings)
    theme_manager = MagicMock()

    dialog = SettingsDialog(
        mock_services,
        theme_manager=theme_manager,
        quick_launch_bar=None,
    )
    qtbot.addWidget(dialog)

    pm = dialog._qlb_pin_manager
    assert pm._pinned_items == []
    assert len(pm._available_items) == 3

    # Add the Terminal command (row 0 of the available list).
    item = MagicMock()
    item.data.return_value = pm._available_items[0]
    pm._available_list.currentItem = MagicMock(return_value=item)
    pm._add()
    assert [p["label"] for p in pm._pinned_items] == ["Terminal"]
    assert [c["label"] for c in pm._available_items] == ["Editor", "Status"]

    # Add the Editor command (row 0 of the now-shortened available list).
    item = MagicMock()
    item.data.return_value = pm._available_items[0]
    pm._available_list.currentItem = MagicMock(return_value=item)
    pm._add()
    assert [p["label"] for p in pm._pinned_items] == ["Terminal", "Editor"]
    assert [c["label"] for c in pm._available_items] == ["Status"]

    # Move the Editor entry up one position.
    pm._pinned_list.currentRow = MagicMock(return_value=1)
    pm._move_up()
    assert [p["label"] for p in pm._pinned_items] == ["Editor", "Terminal"]

    # Remove the Editor entry.
    item = MagicMock()
    item.data.return_value = pm._pinned_items[0]
    pm._pinned_list.currentItem = MagicMock(return_value=item)
    pm._remove()
    assert [p["label"] for p in pm._pinned_items] == ["Terminal"]


def test_settings_dialog_save_persists_normalized_pins_and_drops_stale(qtbot):
    """save() issues exactly one save_settings() call whose dict carries the
    normalised, resolved pins (a stale pin is dropped)."""
    settings = {
        "quick_launch_bar": {
            "visible": True,
            "hotkey": "ctrl+shift+b",
            "pinned": [
                {
                    "group": "System",
                    "label": "Terminal",
                    "command": "gnome-terminal",
                    "confirm": False,
                    "showOutput": False,
                },
                {
                    "group": "Unknown",
                    "label": "Ghost",
                    "command": "ghost",
                    "confirm": False,
                    "showOutput": False,
                },
            ],
        }
    }
    mock_services = _make_services_with_settings(settings)
    theme_manager = MagicMock()

    dialog = SettingsDialog(
        mock_services,
        theme_manager=theme_manager,
        quick_launch_bar=None,
    )
    qtbot.addWidget(dialog)

    # The Ghost command no longer resolves: it must be dropped by commit().
    mock_services.get_all_commands.return_value = [
        {
            "group": "System",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": False,
            "showOutput": False,
        },
    ]

    dialog._save()

    assert mock_services.config_manager.save_settings.call_count == 1
    saved = mock_services.config_manager.save_settings.call_args[0][0]
    assert saved["quick_launch_bar"]["pinned"] == [
        {
            "group": "System",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": False,
            "showOutput": False,
        },
    ]


def test_settings_dialog_bar_refreshed_via_signal_when_bar_injected(qtbot):
    """With a bar injected, save() refreshes the visible bar through the pins
    committed signal."""
    settings = {"quick_launch_bar": {"visible": True, "hotkey": "ctrl+shift+b", "pinned": []}}
    mock_services = _make_services_with_settings(settings)
    theme_manager = MagicMock()
    refresh_calls = []

    class _Bar:
        def refresh(self):
            refresh_calls.append(True)

    dialog = SettingsDialog(
        mock_services,
        theme_manager=theme_manager,
        quick_launch_bar=_Bar(),
    )
    qtbot.addWidget(dialog)

    # The pin manager is wired to the injected bar during construction. The
    # harness's lighter stub does not dispatch pyqtSignal, so redirect the
    # signal's emit onto a recorder so the bar is refreshed by save().
    emit_recorder = MagicMock()

    def record():
        return dialog._quick_launch_bar.refresh()

    emit_recorder.side_effect = record
    dialog._qlb_pin_manager.pins_committed.emit = emit_recorder
    dialog._save()

    emit_recorder.assert_called_once()
    assert len(refresh_calls) == 1
