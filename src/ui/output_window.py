# SPDX-License-Identifier: GPL-3.0-or-later

"""
RichOutputWindow — tabbed, ANSI-aware command output display.

One tab is opened per running process.  Each tab contains a read-only
QTextEdit that renders SGR ANSI colour/style sequences using
QTextCharFormat so no external library is required.

Toolbar actions:
  • Auto-scroll toggle  — keep the view scrolled to the bottom
  • Copy                — copy the active tab's plain text to clipboard
  • Clear               — clear the active tab's content
  • Font                — open QFontDialog to change the display font
"""

import logging
import re

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QAction
from PyQt6.QtWidgets import (
    QApplication,
    QFontDialog,
    QMainWindow,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QWidget,
)

from core.config_manager import config_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SGR ANSI escape-code parser
# ---------------------------------------------------------------------------
# We only handle the most common subset: SGR (Select Graphic Rendition).
# Unknown and OSC sequences are stripped silently.
_ANSI_ESC_RE = re.compile(r"\x1B\[([0-9;]*)m|\x1B[^m]*m?|\x1B[@-Z\\-_]|\x1B\[[^@-~]*[@-~]")

_ANSI_COLORS_FG = {
    30: "#4c4f69",   # black  (uses theme fg light/dark neutrals)
    31: "#d20f39",   # red
    32: "#40a02b",   # green
    33: "#df8e1d",   # yellow
    34: "#1e66f5",   # blue
    35: "#ea76cb",   # magenta
    36: "#04a5e5",   # cyan
    37: "#cdd6f4",   # white
    90: "#585b70",   # bright black
    91: "#f38ba8",   # bright red
    92: "#a6e3a1",   # bright green
    93: "#f9e2af",   # bright yellow
    94: "#89b4fa",   # bright blue
    95: "#f5c2e7",   # bright magenta
    96: "#89dceb",   # bright cyan
    97: "#ffffff",   # bright white
}

_ANSI_COLORS_BG = {k + 10: v for k, v in _ANSI_COLORS_FG.items()}


def _parse_sgr(codes: list[int], fmt: QTextCharFormat) -> QTextCharFormat:
    """Apply a list of SGR codes to *fmt* and return the updated format."""
    i = 0
    while i < len(codes):
        code = codes[i]
        if code == 0:
            fmt = QTextCharFormat()
        elif code == 1:
            fmt.setFontWeight(QFont.Weight.Bold)
        elif code == 3:
            fmt.setFontItalic(True)
        elif code == 4:
            fmt.setFontUnderline(True)
        elif code == 22:
            fmt.setFontWeight(QFont.Weight.Normal)
        elif code == 23:
            fmt.setFontItalic(False)
        elif code == 24:
            fmt.setFontUnderline(False)
        elif code in _ANSI_COLORS_FG:
            fmt.setForeground(QColor(_ANSI_COLORS_FG[code]))
        elif code in _ANSI_COLORS_BG:
            fmt.setBackground(QColor(_ANSI_COLORS_BG[code]))
        elif code == 39:
            fmt.clearForeground()
        elif code == 49:
            fmt.clearBackground()
        i += 1
    return fmt


# ---------------------------------------------------------------------------
# Per-tab output widget
# ---------------------------------------------------------------------------

class _OutputTab(QTextEdit):
    """A single read-only output tab with ANSI rendering support."""

    def __init__(self, font: QFont, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(font)
        self._fmt = QTextCharFormat()

    def append_ansi(self, text: str) -> None:
        """Append *text* which may contain ANSI SGR sequences."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        last_end = 0
        for match in _ANSI_ESC_RE.finditer(text):
            # Flush plain text up to the escape sequence
            plain = text[last_end:match.start()]
            if plain:
                cursor.insertText(plain, self._fmt)

            sgr_match = re.fullmatch(r"\x1B\[([0-9;]*)m", match.group(0))
            if sgr_match:
                raw = sgr_match.group(1)
                codes = [int(c) for c in raw.split(";") if c] if raw else [0]
                self._fmt = _parse_sgr(codes, self._fmt)

            last_end = match.end()

        # Flush any remaining plain text
        tail = text[last_end:]
        if tail:
            cursor.insertText(tail, self._fmt)

        self.setTextCursor(cursor)


# ---------------------------------------------------------------------------
# RichOutputWindow
# ---------------------------------------------------------------------------

class RichOutputWindow(QMainWindow):
    """Tabbed, ANSI-aware output window."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Command Output")
        self.setGeometry(100, 100, 900, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Resolve display font from settings
        settings = config_manager.get_settings()
        font_cfg = settings.get("output_font", {})
        family = font_cfg.get("family", "monospace") if isinstance(font_cfg, dict) else "monospace"
        size = font_cfg.get("size", 10) if isinstance(font_cfg, dict) else 10
        self._font = QFont(family, size)

        self._auto_scroll = True

        # Toolbar
        toolbar = QToolBar("Output Tools", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self._scroll_action = QAction("Auto-scroll: ON", self)
        self._scroll_action.setCheckable(True)
        self._scroll_action.setChecked(True)
        self._scroll_action.toggled.connect(self._toggle_auto_scroll)
        toolbar.addAction(self._scroll_action)

        toolbar.addSeparator()

        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self._copy_tab)
        toolbar.addAction(copy_action)

        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self._clear_tab)
        toolbar.addAction(clear_action)

        toolbar.addSeparator()

        font_action = QAction("Font…", self)
        font_action.triggered.connect(self._change_font)
        toolbar.addAction(font_action)

        # Tab widget
        self._tabs = QTabWidget(self)
        self._tabs.setTabsClosable(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        self.setCentralWidget(self._tabs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open_process_tab(self, title: str) -> "_OutputTab":
        """Open a new tab for *title* and return the output widget."""
        tab = _OutputTab(self._font, self)
        tab.verticalScrollBar().rangeChanged.connect(
            lambda _min, _max, t=tab: self._maybe_scroll(t)
        )
        idx = self._tabs.addTab(tab, title)
        self._tabs.setCurrentIndex(idx)
        self.show()
        self.raise_()
        return tab

    def append_output(self, tab: "_OutputTab", text: str) -> None:
        """Append *text* to *tab* and optionally scroll to the bottom."""
        tab.append_ansi(text)
        if self._auto_scroll:
            tab.verticalScrollBar().setValue(tab.verticalScrollBar().maximum())

    # ------------------------------------------------------------------
    # Legacy compatibility shim
    # Used by show_command_output in TrayApp when process output arrives
    # all-at-once after the process finishes.
    # ------------------------------------------------------------------

    @classmethod
    def show_output(cls, title: str, output: str, parent: QWidget | None = None) -> "RichOutputWindow":
        """Create a stand-alone window showing *output* for *title*."""
        win = cls(parent)
        tab = win.open_process_tab(title)
        win.append_output(tab, output)
        return win

    # ------------------------------------------------------------------
    # Toolbar handlers
    # ------------------------------------------------------------------

    def _toggle_auto_scroll(self, checked: bool) -> None:
        self._auto_scroll = checked
        self._scroll_action.setText(f"Auto-scroll: {'ON' if checked else 'OFF'}")

    def _copy_tab(self) -> None:
        tab = self._current_tab()
        if tab:
            QApplication.clipboard().setText(tab.toPlainText())

    def _clear_tab(self) -> None:
        tab = self._current_tab()
        if tab:
            tab.clear()

    def _change_font(self) -> None:
        ok, font = QFontDialog.getFont(self._font, self)
        if ok:
            self._font = font
            for i in range(self._tabs.count()):
                w = self._tabs.widget(i)
                if isinstance(w, _OutputTab):
                    w.setFont(font)
            # Persist font choice
            try:
                settings = config_manager.get_settings()
                settings["output_font"] = {"family": font.family(), "size": font.pointSize()}
                config_manager.save_settings(settings)
            except Exception as exc:
                logger.warning("Failed to persist output font: %s", exc)

    def _close_tab(self, index: int) -> None:
        self._tabs.removeTab(index)
        if self._tabs.count() == 0:
            self.close()

    def _current_tab(self) -> "_OutputTab | None":
        w = self._tabs.currentWidget()
        return w if isinstance(w, _OutputTab) else None

    def _maybe_scroll(self, tab: "_OutputTab") -> None:
        if self._auto_scroll:
            tab.verticalScrollBar().setValue(tab.verticalScrollBar().maximum())
