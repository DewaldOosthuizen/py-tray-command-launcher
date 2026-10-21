# SPDX-License-Identifier: GPL-3.0-or-later
"""Regression coverage for shared dialog sizing and explicit theme states."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ui.dialog_conventions import configure_dialog_layout, responsive_dialog_size


class _Geometry:
    def width(self):
        return 800

    def height(self):
        return 600


class _Screen:
    def availableGeometry(self):
        return _Geometry()


def test_dialog_layout_uses_shared_spacing_and_margins():
    layout = MagicMock()

    configure_dialog_layout(layout)

    layout.setContentsMargins.assert_called_once_with(12, 12, 12, 12)
    layout.setSpacing.assert_called_once_with(12)


def test_responsive_dialog_size_respects_available_screen(monkeypatch):
    dialog = MagicMock()
    monkeypatch.setattr(
        "ui.dialog_conventions.QApplication.primaryScreen",
        MagicMock(return_value=_Screen()),
    )

    responsive_dialog_size(dialog, preferred=(900, 650), minimum=(700, 500))

    dialog.setMinimumSize.assert_called_once_with(700, 500)
    dialog.resize.assert_called_once_with(776, 576)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_explicit_themes_style_palette_and_dialog_states(theme):
    stylesheet = (
        Path(__file__).resolve().parents[1] / "resources" / "themes" / f"{theme}.qss"
    ).read_text(encoding="utf-8")

    for selector in (
        "QFrame#PaletteFrame",
        "QPushButton#PaletteTabActive",
        "QPushButton:focus",
        "QPushButton:default",
        "QPushButton:disabled",
        "QListWidget::item:selected",
        "QListWidget::item:focus",
    ):
        assert selector in stylesheet
