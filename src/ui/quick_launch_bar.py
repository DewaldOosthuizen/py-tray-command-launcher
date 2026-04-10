#  SPDX-License-Identifier: GPL-3.0-or-later

"""
QuickLaunchBar — a compact, frameless floating toolbar pinned to the desktop.

* Reads ``quick_launch_bar.pinned`` and ``quick_launch_bar.position`` from
  ``settings.json`` (managed by ``ConfigManager.get_settings()``).
* Drag the bar to reposition it; the new position is persisted automatically.
* Toggle visibility from the tray menu via ``toggle()``.
* Call ``refresh()`` to rebuild buttons after pin list changes.

Example entry in settings.json:

    "quick_launch_bar": {
        "visible": true,
        "position": [100, 100],
        "pinned": [
            {"group": "System", "label": "Terminal"}
        ]
    }
"""

import logging

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QToolButton,
    QWidget,
)

logger = logging.getLogger(__name__)


class QuickLaunchBar(QWidget):
    """Floating, draggable quick-launch toolbar."""

    def __init__(self, services, icon_path: str = ""):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.services = services
        self._icon_path = icon_path
        self._drag_pos: QPoint | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setObjectName("QuickLaunchBar")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(4)

        self._build_buttons()
        self._restore_position()

        settings = self.services.config_manager.get_settings()
        qlb_cfg = settings.get("quick_launch_bar", {})
        if qlb_cfg.get("visible", False):
            self.show()

    # ------------------------------------------------------------------
    # Build / refresh
    # ------------------------------------------------------------------

    def _build_buttons(self):
        """Clear and rebuild tool buttons from the pinned list."""
        # Remove existing buttons
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        settings = self.services.config_manager.get_settings()
        pinned = settings.get("quick_launch_bar", {}).get("pinned", [])
        all_cmds = {
            (c["group"], c["label"]): c
            for c in self.services.get_all_commands()
        }

        for pin in pinned:
            group = pin.get("group", "")
            label = pin.get("label", "")
            cmd = all_cmds.get((group, label))
            if not cmd:
                logger.warning("Pinned command not found: %s / %s", group, label)
                continue

            btn = QToolButton(self)
            btn.setToolTip(f"{group} → {label}")
            btn.setText(label[:12])  # truncate for compact display
            if self._icon_path:
                btn.setIcon(QIcon(self._icon_path))
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            # Capture cmd dict at closure time
            btn.clicked.connect(
                lambda _checked=False, c=cmd: self.services.execute(
                    c["label"],
                    c["command"],
                    c.get("confirm", False),
                    c.get("showOutput", False),
                    c.get("prompt"),
                )
            )
            self._layout.addWidget(btn)

        if not pinned:
            from PyQt6.QtWidgets import QLabel
            placeholder = QLabel("No pinned commands — add via Settings", self)
            placeholder.setObjectName("QLBPlaceholder")
            self._layout.addWidget(placeholder)

        self.adjustSize()

    def refresh(self):
        """Rebuild buttons from updated settings (call after pinned list changes)."""
        self._build_buttons()
        self._restore_position()

    # ------------------------------------------------------------------
    # Visibility toggle
    # ------------------------------------------------------------------

    def toggle(self):
        """Toggle bar visibility and persist in settings."""
        visible = not self.isVisible()
        if visible:
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            self.hide()
        settings = self.services.config_manager.get_settings()
        qlb_cfg = settings.setdefault("quick_launch_bar", {})
        qlb_cfg["visible"] = visible
        self.services.config_manager.save_settings(settings)

    # ------------------------------------------------------------------
    # Position persistence
    # ------------------------------------------------------------------

    def _restore_position(self):
        settings = self.services.config_manager.get_settings()
        pos = settings.get("quick_launch_bar", {}).get("position", [100, 100])
        self.move(pos[0], pos[1])

    def _save_position(self):
        settings = self.services.config_manager.get_settings()
        qlb_cfg = settings.setdefault("quick_launch_bar", {})
        qlb_cfg["position"] = [self.x(), self.y()]
        self.services.config_manager.save_settings(settings)

    # ------------------------------------------------------------------
    # Drag to move
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        # Use childAt() to detect background clicks (PyQt6 has no event.widget()).
        # Only start drag when clicking on the bar background, not on a child button.
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            self._drag_pos = None
            self._save_position()
        super().mouseReleaseEvent(event)
