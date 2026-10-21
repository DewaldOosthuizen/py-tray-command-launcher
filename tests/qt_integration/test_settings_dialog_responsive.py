# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-Qt regression tests for the Settings dialog's display behavior."""

import os

import pytest
from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QGroupBox, QScrollArea

from ui.settings_dialog import SettingsDialog

pytestmark = pytest.mark.skipif(
    os.environ.get("PY_TRAY_NO_STUB") != "1",
    reason="These tests must run in an isolated process with real Qt widgets.",
)


def _build_dialog(qtbot):
    """Construct the production SettingsDialog with complete test settings."""
    from unittest.mock import MagicMock

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
    dialog = SettingsDialog(services, MagicMock())
    qtbot.addWidget(dialog)
    return dialog


def test_settings_sections_scroll_while_actions_remain_fixed(qtbot):
    """Settings content scrolls independently from its Save/Cancel action area."""
    dialog = _build_dialog(qtbot)
    dialog.resize(500, 340)
    dialog.show()
    qtbot.wait(50)

    scroll_area = dialog.findChild(QScrollArea)
    buttons = dialog.findChild(QDialogButtonBox)
    assert scroll_area is not None
    assert buttons is not None
    assert scroll_area.widgetResizable()
    assert scroll_area.parentWidget() is dialog
    assert buttons.parentWidget() is dialog
    assert scroll_area.verticalScrollBar().maximum() > 0

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

    scroll_area.verticalScrollBar().setValue(scroll_area.verticalScrollBar().maximum())
    qtbot.wait(10)
    logging_group = next(group for group in groups if group.title() == "Logging")
    visible_rect = QRect(
        logging_group.mapTo(scroll_area.viewport(), QPoint(0, 0)),
        logging_group.size(),
    )
    assert visible_rect.intersects(scroll_area.viewport().rect())
    assert buttons.isVisible()
    assert buttons.button(QDialogButtonBox.StandardButton.Save).isVisible()
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).isVisible()


def test_settings_size_and_placement_use_cursor_display(qtbot, monkeypatch):
    """The cursor display's available geometry bounds and centres the dialog."""
    display_geometry = QRect(2000, 100, 500, 400)
    screen = type("Screen", (), {"availableGeometry": lambda self: display_geometry})()
    monkeypatch.setattr(QGuiApplication, "screenAt", staticmethod(lambda _pos: screen))
    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: None))

    dialog = _build_dialog(qtbot)

    assert dialog.maximumWidth() == 400
    assert dialog.maximumHeight() == 320
    assert dialog.minimumWidth() == 400
    assert display_geometry.contains(dialog.frameGeometry())


def test_settings_uses_primary_display_when_cursor_has_no_screen(qtbot, monkeypatch):
    """A cursor miss falls back to the primary display for size and placement."""
    display_geometry = QRect(100, 50, 1000, 800)
    screen = type("Screen", (), {"availableGeometry": lambda self: display_geometry})()
    monkeypatch.setattr(QGuiApplication, "screenAt", staticmethod(lambda _pos: None))
    monkeypatch.setattr(QApplication, "primaryScreen", staticmethod(lambda: screen))

    dialog = _build_dialog(qtbot)

    assert dialog.maximumWidth() == 800
    assert dialog.maximumHeight() == 640
    assert display_geometry.contains(dialog.frameGeometry())
