# SPDX-License-Identifier: GPL-3.0-or-later
"""BadgeManager — renders a running-process-count badge onto the tray icon."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


class BadgeManager:
    """Renders a running-process-count badge onto the tray icon."""

    def __init__(self, tray_icon, icon_file: str):
        self._tray_icon = tray_icon
        self._icon_file = icon_file

    def update_badge(self, count: int) -> None:
        """Repaint the tray icon with a badge showing the running process count."""
        base = QPixmap(self._icon_file)
        if base.isNull():
            return

        if count == 0:
            self._tray_icon.setIcon(QIcon(base))
            return

        badge_size = max(base.width() // 3, 12)
        painter = QPainter(base)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bx = base.width() - badge_size - 1
        by = base.height() - badge_size - 1
        painter.setBrush(QColor("#e64553"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(bx, by, badge_size, badge_size)

        font = QFont()
        font.setPixelSize(max(badge_size - 4, 8))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(bx, by, badge_size, badge_size, Qt.AlignmentFlag.AlignCenter, str(count))
        painter.end()

        self._tray_icon.setIcon(QIcon(base))
