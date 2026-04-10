#  SPDX-License-Identifier: GPL-3.0-or-later

"""
CommandPalette — spotlight-style popup overlay for quick command access.

* Frameless ``Qt.Popup`` window — disappears on focus loss.
* Reuses the same rapidfuzz scoring used in CommandSearch.
* Hotkey registration is handled by ``TrayApp`` via ``keyboard`` library so
  that the callback runs on the Qt main thread through a ``QTimer``.

Public API
----------
``CommandPalette(services)``
    Instantiate once and reuse across show calls.

``palette.show_palette()``
    Show (or raise) the palette centred on the primary screen.
"""

import logging

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


_PYNPUT_WRAP = {
    'ctrl', 'shift', 'alt', 'altgr', 'cmd', 'win', 'super', 'meta',
    'space', 'enter', 'return', 'tab', 'esc', 'escape',
    'backspace', 'delete', 'insert', 'home', 'end',
    'page_up', 'page_down', 'up', 'down', 'left', 'right',
    'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
}


def _to_pynput_str(hotkey: str) -> str:
    """Convert 'ctrl+shift+space' to '<ctrl>+<shift>+<space>' for pynput."""
    parts = []
    for k in hotkey.lower().split('+'):
        k = k.strip()
        parts.append(f'<{k}>' if (k in _PYNPUT_WRAP or len(k) > 1) else k)
    return '+'.join(parts)


class _HotkeyTrigger(QObject):
    """Thread-safe bridge: emit triggered from any thread into the Qt main loop."""
    triggered = pyqtSignal()


try:
    from rapidfuzz import fuzz as _fuzz
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False


def _score(query: str, text: str) -> float:
    if _FUZZY_AVAILABLE:
        return _fuzz.WRatio(query, text)
    return 100.0 if query.lower() in text.lower() else 0.0


class _PaletteWindow(QWidget):
    """Internal frameless popup window."""

    def __init__(self, palette: "CommandPalette"):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._palette = palette
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumWidth(520)
        self.setMaximumHeight(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Frame gives a visible border independent of QSS
        frame = QFrame(self)
        frame.setObjectName("PaletteFrame")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header row
        header = QHBoxLayout()
        icon_label = QLabel("⌘")
        icon_label.setObjectName("PaletteIcon")
        self._search = QLineEdit()
        self._search.setPlaceholderText("Run a command…")
        self._search.setObjectName("PaletteSearch")
        self._search.setClearButtonEnabled(True)
        header.addWidget(icon_label)
        header.addWidget(self._search)
        layout.addLayout(header)

        # Results list
        self._list = QListWidget()
        self._list.setObjectName("PaletteList")
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._list)

        # Footer hint
        footer = QLabel("↑↓ navigate   ↵ execute   Esc close")
        footer.setObjectName("PaletteFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        outer.addWidget(frame)

        self._search.textChanged.connect(self._populate)
        self._list.itemActivated.connect(self._execute)

        self._search.installEventFilter(self)

    # ------------------------------------------------------------------
    # Population / search
    # ------------------------------------------------------------------

    def _populate(self, query: str):
        self._list.clear()
        all_cmds = self._palette._services.get_all_commands()

        if not query.strip():
            scored = [(100, cmd) for cmd in all_cmds]
        else:
            scored = []
            for cmd in all_cmds:
                text = f"{cmd['group']} {cmd['label']}"
                s = _score(query, text)
                if s > 30 or query.lower() in text.lower():
                    scored.append((s, cmd))
            scored.sort(key=lambda x: x[0], reverse=True)

        for _s, cmd in scored:
            item = QListWidgetItem(f"{cmd['label']}  —  {cmd['group']}")
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._list.addItem(item)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute(self, item: QListWidgetItem = None):
        if item is None:
            item = self._list.currentItem()
        if not item:
            return
        cmd_info = item.data(Qt.ItemDataRole.UserRole)
        if not cmd_info:
            return
        self.hide()
        self._palette._services.execute(
            cmd_info["label"],
            cmd_info["command"],
            cmd_info.get("confirm", False),
            cmd_info.get("showOutput", False),
            cmd_info.get("prompt"),
        )

    # ------------------------------------------------------------------
    # Keyboard navigation
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if obj is self._search and isinstance(event, QKeyEvent):
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._execute()
                return True
            elif key == Qt.Key.Key_Down:
                row = self._list.currentRow()
                if row < self._list.count() - 1:
                    self._list.setCurrentRow(row + 1)
                return True
            elif key == Qt.Key.Key_Up:
                row = self._list.currentRow()
                if row > 0:
                    self._list.setCurrentRow(row - 1)
                return True
            elif key == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def show_centered(self):
        """Show the palette centred on the primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.adjustSize()
            x = geo.center().x() - self.width() // 2
            y = geo.top() + geo.height() // 4
            self.move(x, y)
        self._search.clear()
        self._populate("")
        self.show()
        self.raise_()
        self.activateWindow()
        self._search.setFocus()


class CommandPalette:
    """Manages the global command palette overlay and hotkey registration."""

    def __init__(self, services):
        self._services = services
        self._window: _PaletteWindow | None = None
        self._hotkey_listener = None
        self._trigger = _HotkeyTrigger()
        self._trigger.triggered.connect(self.show_palette, Qt.ConnectionType.QueuedConnection)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_palette(self):
        """Show (or raise) the palette — safe to call from any thread via signal."""
        if self._window is None:
            self._window = _PaletteWindow(self)
        self._window.show_centered()

    def register_hotkey(self, hotkey: str) -> bool:
        """Register a global hotkey that triggers ``show_palette``.

        Uses pynput's GlobalHotKeys (no root required on X11/Linux).
        Returns ``True`` on success; degrades gracefully on Wayland or
        when pynput is unavailable.
        """
        self.unregister_hotkey()
        if not hotkey:
            return False
        try:
            from pynput import keyboard as _kb
            pynput_key = _to_pynput_str(hotkey)
            self._hotkey_listener = _kb.GlobalHotKeys(
                {pynput_key: self._trigger.triggered.emit}
            )
            self._hotkey_listener.start()
            logger.info("Command Palette hotkey registered: %s (%s)", hotkey, pynput_key)
            return True
        except ImportError:
            logger.warning("pynput not available — palette hotkey disabled")
        except Exception as exc:
            logger.warning("Failed to register palette hotkey '%s': %s", hotkey, exc)
        return False

    def unregister_hotkey(self):
        """Remove the registered global hotkey if any."""
        if self._hotkey_listener is None:
            return
        try:
            self._hotkey_listener.stop()
        except Exception:
            pass
        self._hotkey_listener = None
