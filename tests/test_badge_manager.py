# SPDX-License-Identifier: GPL-3.0-or-later
"""Unit tests for core.badge_manager.BadgeManager."""

from unittest.mock import MagicMock, patch

from core.badge_manager import BadgeManager


def test_update_badge_zero_count_sets_plain_icon_no_painter():
    tray_icon = MagicMock()
    manager = BadgeManager(tray_icon, "icon.png")
    with (
        patch("core.badge_manager.QPixmap") as qpix,
        patch("core.badge_manager.QPainter") as qpainter,
        patch("core.badge_manager.QIcon") as qicon,
    ):
        qpix.return_value.isNull.return_value = False
        manager.update_badge(0)
    qpainter.assert_not_called()
    tray_icon.setIcon.assert_called_once_with(qicon.return_value)


def test_update_badge_null_pixmap_is_noop():
    tray_icon = MagicMock()
    manager = BadgeManager(tray_icon, "icon.png")
    with patch("core.badge_manager.QPixmap") as qpix:
        qpix.return_value.isNull.return_value = True
        manager.update_badge(3)
    tray_icon.setIcon.assert_not_called()


def test_update_badge_positive_count_draws_painter_and_sets_icon():
    tray_icon = MagicMock()
    manager = BadgeManager(tray_icon, "icon.png")
    with (
        patch("core.badge_manager.QPixmap") as qpix,
        patch("core.badge_manager.QPainter") as qpainter,
        patch("core.badge_manager.QIcon") as qicon,
    ):
        base = qpix.return_value
        base.isNull.return_value = False
        base.width.return_value = 32
        base.height.return_value = 32
        manager.update_badge(2)
    qpainter.assert_called_once_with(base)
    painter_instance = qpainter.return_value
    assert painter_instance.drawEllipse.called
    assert painter_instance.drawText.called
    painter_instance.end.assert_called_once()
    tray_icon.setIcon.assert_called_once_with(qicon.return_value)
