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
    dialog, _, _ = _real_qt_settings_dialog()
    qtbot.addWidget(dialog)
    assert dialog is not None


def _real_qt_settings_dialog():
    """Build the dialog with real Qt widgets and isolated service mocks."""
    settings = {
        "theme": "dark",
        "hotkey": "ctrl+shift+space",
        "app_launcher_hotkey": "ctrl+alt+a",
        "history_limit": 50,
        "output_font": {"family": "monospace", "size": 10},
        "quick_launch_bar": {"visible": False, "hotkey": "ctrl+shift+b", "pinned": []},
        "logging": {"level": "WARNING"},
    }
    services = MagicMock()
    services.config_manager.get_settings.return_value = settings
    services.get_all_commands.return_value = []
    theme_manager = MagicMock()
    return SettingsDialog(services, theme_manager), services, theme_manager


@pytest.mark.skipif(
    os.environ.get("PY_TRAY_NO_STUB") != "1",
    reason="Real Qt widget tests run in their dedicated no-stub process.",
)
def test_settings_sections_and_actions_have_separate_scroll_layouts(qtbot):
    """All settings content scrolls in one viewport while actions stay outside."""
    from PyQt6.QtWidgets import QDialogButtonBox, QGroupBox, QLabel, QScrollArea

    dialog, _, _ = _real_qt_settings_dialog()
    qtbot.addWidget(dialog)

    scroll_area = dialog.findChild(QScrollArea)
    assert scroll_area is not None
    assert scroll_area.widgetResizable()
    content = scroll_area.widget()
    groups = content.findChildren(QGroupBox)
    assert [group.title() for group in groups] == [
        "Appearance",
        "Behaviour",
        "Output Window",
        "Quick-Launch Bar",
        "Pinned Commands",
        "Logging",
    ]
    help_label = next(
        label
        for label in content.findChildren(QLabel)
        if "safe scheduling constraints" in label.text()
    )
    assert help_label.parentWidget() is content
    assert all(group.parentWidget() is content for group in groups)

    buttons = dialog.findChild(QDialogButtonBox)
    assert buttons is not None
    assert buttons.parentWidget() is dialog
    outer_widgets = [
        dialog.layout().itemAt(index).widget() for index in range(dialog.layout().count())
    ]
    assert scroll_area in outer_widgets
    assert buttons in outer_widgets
    assert content not in outer_widgets


@pytest.mark.skipif(
    os.environ.get("PY_TRAY_NO_STUB") != "1",
    reason="Real Qt widget tests run in their dedicated no-stub process.",
)
def test_compact_dialog_scrolls_content_and_keeps_actions_usable(qtbot):
    """Lower settings remain reachable and both action buttons still work."""
    from PyQt6.QtCore import QPoint, QRect, Qt
    from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QGroupBox, QScrollArea

    dialog, services, theme_manager = _real_qt_settings_dialog()
    qtbot.addWidget(dialog)
    dialog.resize(500, 340)
    dialog.show()
    qtbot.wait(50)

    scroll_area = dialog.findChild(QScrollArea)
    assert scroll_area is not None
    scrollbar = scroll_area.verticalScrollBar()
    assert scrollbar.maximum() > 0
    scrollbar.setValue(scrollbar.maximum())
    qtbot.wait(10)

    content = scroll_area.widget()
    logging_group = next(
        group for group in content.findChildren(QGroupBox) if group.title() == "Logging"
    )
    visible_rect = QRect(
        logging_group.mapTo(scroll_area.viewport(), QPoint(0, 0)),
        logging_group.size(),
    )
    assert visible_rect.intersects(scroll_area.viewport().rect())

    buttons = dialog.findChild(QDialogButtonBox)
    cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
    assert buttons.isVisible()
    assert cancel_button.isVisible()
    qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)
    assert dialog.result() == QDialog.DialogCode.Rejected
    theme_manager.apply_theme.assert_called_with("dark")

    save_dialog, save_services, _ = _real_qt_settings_dialog()
    qtbot.addWidget(save_dialog)
    save_dialog.resize(500, 340)
    save_dialog.show()
    qtbot.wait(50)
    save_scroll = save_dialog.findChild(QScrollArea)
    save_scroll.verticalScrollBar().setValue(save_scroll.verticalScrollBar().maximum())
    save_buttons = save_dialog.findChild(QDialogButtonBox)
    save_button = save_buttons.button(QDialogButtonBox.StandardButton.Save)
    assert save_button.isVisible()
    qtbot.mouseClick(save_button, Qt.MouseButton.LeftButton)
    save_services.config_manager.save_settings.assert_called_once()
    assert save_dialog.result() == QDialog.DialogCode.Accepted


@pytest.mark.skipif(
    os.environ.get("PY_TRAY_NO_STUB") != "1",
    reason="Real Qt screen tests run in their dedicated no-stub process.",
)
def test_dialog_uses_cursor_selected_secondary_screen_geometry(qtbot, monkeypatch):
    """A compact cursor-selected display controls both bounds and placement."""
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication

    primary_geometry = QRect(0, 0, 1920, 1080)
    secondary_geometry = QRect(2000, 100, 500, 400)
    primary = type("Screen", (), {"availableGeometry": lambda self: primary_geometry})()
    secondary = type("Screen", (), {"availableGeometry": lambda self: secondary_geometry})()
    monkeypatch.setattr(QGuiApplication, "screenAt", staticmethod(lambda _pos: secondary))
    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: primary))

    dialog, _, _ = _real_qt_settings_dialog()
    qtbot.addWidget(dialog)

    assert dialog.maximumWidth() == 400
    assert dialog.maximumHeight() == 320
    assert dialog.minimumWidth() == 400
    assert secondary_geometry.contains(dialog.frameGeometry())


@pytest.mark.skipif(
    os.environ.get("PY_TRAY_NO_STUB") != "1",
    reason="Real Qt screen tests run in their dedicated no-stub process.",
)
def test_dialog_falls_back_to_primary_screen_or_safe_no_screen_width(qtbot, monkeypatch):
    """Cursor misses use the primary screen; no usable screen keeps a safe width."""
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication

    primary_geometry = QRect(100, 50, 1000, 800)
    primary = type("Screen", (), {"availableGeometry": lambda self: primary_geometry})()
    monkeypatch.setattr(QGuiApplication, "screenAt", staticmethod(lambda _pos: None))
    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: primary))

    dialog, _, _ = _real_qt_settings_dialog()
    qtbot.addWidget(dialog)
    assert dialog.maximumWidth() == 800
    assert primary_geometry.contains(dialog.frameGeometry())

    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: None))
    no_screen_dialog, _, _ = _real_qt_settings_dialog()
    qtbot.addWidget(no_screen_dialog)
    assert no_screen_dialog.minimumWidth() == 420


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

    if os.environ.get("PY_TRAY_NO_STUB") == "1":
        dialog._save()
        assert len(refresh_calls) == 1
    else:
        # The lighter stub signal does not dispatch the connected refresh slot.
        emit_recorder = MagicMock()
        emit_recorder.side_effect = lambda: dialog._quick_launch_bar.refresh()
        dialog._qlb_pin_manager.pins_committed.emit = emit_recorder
        dialog._save()
        emit_recorder.assert_called_once()
    assert len(refresh_calls) == 1
