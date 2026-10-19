# SPDX-License-Identifier: GPL-3.0-or-later
# Canonical location for OutputWindow / RichOutputWindow — the legacy copy at
# src/core/output_window.py was removed; always import from ui.output_window.

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
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QFont, QPalette, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QFontDialog,
    QMainWindow,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QWidget,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SGR ANSI escape-code parser
# ---------------------------------------------------------------------------
# We only handle the most common subset: SGR (Select Graphic Rendition).
# Unknown and OSC sequences are stripped silently.
_ANSI_ESC_RE = re.compile(r"\x1B\[([0-9;]*)m|\x1B[^m]*m?|\x1B[@-Z\\-_]|\x1B\[[^@-~]*[@-~]")

_LIGHT_ANSI_COLORS = {
    30: "#4c4f69",
    31: "#d20f39",
    32: "#40a02b",
    33: "#df8e1d",
    34: "#1e66f5",
    35: "#ea76cb",
    36: "#04a5e5",
    37: "#5c5f77",
    90: "#5c5f77",
    91: "#d20f39",
    92: "#40a02b",
    93: "#df8e1d",
    94: "#1e66f5",
    95: "#ea76cb",
    96: "#04a5e5",
    97: "#4c4f69",
}

_DARK_ANSI_COLORS = {
    30: "#585b70",
    31: "#f38ba8",
    32: "#a6e3a1",
    33: "#f9e2af",
    34: "#89b4fa",
    35: "#f5c2e7",
    36: "#89dceb",
    37: "#cdd6f4",
    90: "#585b70",
    91: "#f38ba8",
    92: "#a6e3a1",
    93: "#f9e2af",
    94: "#89b4fa",
    95: "#f5c2e7",
    96: "#89dceb",
    97: "#ffffff",
}

_ANSI_PALETTES = {
    "light": {
        **_LIGHT_ANSI_COLORS,
        **{code + 10: color for code, color in _LIGHT_ANSI_COLORS.items()},
    },
    "dark": {
        **_DARK_ANSI_COLORS,
        **{code + 10: color for code, color in _DARK_ANSI_COLORS.items()},
    },
}

_THEME_SURFACES = {"light": "#e6e9ef", "dark": "#181825"}
_THEME_TEXT = {"light": "#4c4f69", "dark": "#cdd6f4"}
_ANSI_FOREGROUND_CODES = frozenset(_LIGHT_ANSI_COLORS)
_ANSI_BACKGROUND_CODES = frozenset(code + 10 for code in _ANSI_FOREGROUND_CODES)
_ANSI_COLOR_CODES = _ANSI_FOREGROUND_CODES | _ANSI_BACKGROUND_CODES
_REQUESTED_FOREGROUND_PROPERTY = 0x100001
_CONTRAST_THRESHOLD = 4.5


@dataclass(frozen=True)
class _OutputTheme:
    """Resolved surface, inherited text color, and ANSI palette variant."""

    surface: QColor
    inherited_text: QColor
    mode: str


def _relative_luminance(color: QColor) -> float:
    """Return WCAG relative luminance for a color's sRGB channels."""

    def linearize(channel: int) -> float:
        value = channel / 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (
        linearize(channel) for channel in (color.red(), color.green(), color.blue())
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(first: QColor, second: QColor) -> float:
    """Return the WCAG contrast ratio between two colors, from 1 to 21.

    Args:
        first: Foreground or background color.
        second: The other color in the pair.

    Returns:
        The contrast ratio, where 1 is no contrast and 21 is maximum contrast.
    """
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter, darker = sorted((first_luminance, second_luminance), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def resolve_output_theme(theme: str, palette) -> _OutputTheme:
    """Resolve output colors from an explicit theme or the active Qt palette.

    Args:
        theme: ``"light"``, ``"dark"``, or ``"system"``.
        palette: The active ``QApplication`` palette used for system mode.

    Returns:
        A construction-time output theme containing the surface, inherited
        text color, and the corresponding ANSI palette variant.

    Raises:
        AttributeError: If system mode receives an object without ``color(role)``.
    """
    normalized_theme = (theme or "system").lower().strip()
    if normalized_theme in _THEME_SURFACES:
        return _OutputTheme(
            QColor(_THEME_SURFACES[normalized_theme]),
            QColor(_THEME_TEXT[normalized_theme]),
            normalized_theme,
        )

    surface = QColor(palette.color(QPalette.ColorRole.Base))
    inherited_text = QColor(palette.color(QPalette.ColorRole.Text))
    mode = "light" if _relative_luminance(surface) > 0.5 else "dark"
    return _OutputTheme(surface, inherited_text, mode)


def _apply_effective_foreground(fmt: QTextCharFormat, theme: _OutputTheme) -> None:
    """Set the readable foreground without changing the requested ANSI background.

    Args:
        fmt: The format whose requested foreground is stored in a user property.
        theme: The output surface and inherited text used when no ANSI color applies.

    Returns:
        None. The format is updated in place.
    """
    requested = fmt.property(_REQUESTED_FOREGROUND_PROPERTY)
    if not requested:
        requested = theme.inherited_text
        fmt.setProperty(_REQUESTED_FOREGROUND_PROPERTY, requested)

    background_brush = fmt.background()
    background = background_brush.color() if background_brush.style() else theme.surface
    effective = requested
    if contrast_ratio(requested, background) < _CONTRAST_THRESHOLD:
        black = QColor("#000000")
        white = QColor("#ffffff")
        effective = max((black, white), key=lambda color: contrast_ratio(color, background))
    fmt.setForeground(effective)


def _parse_sgr(
    codes: list[int], fmt: QTextCharFormat, theme: _OutputTheme | None = None
) -> QTextCharFormat:
    """Apply SGR codes and recalculate readable foreground for each color change.

    Args:
        codes: SGR integer codes to apply in stream order.
        fmt: The current character format, including requested color intent.
        theme: Optional resolved theme; omitted only for legacy direct parser calls.

    Returns:
        The updated text format.
    """
    i = 0
    palette = _ANSI_PALETTES[theme.mode] if theme else _ANSI_PALETTES["dark"]
    while i < len(codes):
        code = codes[i]
        if code == 0:
            fmt = QTextCharFormat()
            if theme:
                fmt.setProperty(_REQUESTED_FOREGROUND_PROPERTY, theme.inherited_text)
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
        elif code in _ANSI_FOREGROUND_CODES:
            color = QColor(palette[code])
            if theme:
                fmt.setProperty(_REQUESTED_FOREGROUND_PROPERTY, color)
            else:
                fmt.setForeground(color)
        elif code in _ANSI_BACKGROUND_CODES:
            fmt.setBackground(QColor(palette[code]))
        elif code == 39:
            if theme:
                fmt.setProperty(_REQUESTED_FOREGROUND_PROPERTY, theme.inherited_text)
            else:
                fmt.clearForeground()
        elif code == 49:
            fmt.clearBackground()
        if theme and (code in _ANSI_COLOR_CODES or code in {0, 39, 49}):
            _apply_effective_foreground(fmt, theme)
        i += 1
    return fmt


# ---------------------------------------------------------------------------
# Per-tab output widget
# ---------------------------------------------------------------------------


class _OutputTab(QTextEdit):
    """A single read-only output tab with ANSI rendering support."""

    def __init__(
        self,
        font: QFont,
        parent: QWidget | None = None,
        output_theme: _OutputTheme | None = None,
    ):
        """Create a read-only tab using the window's construction-time theme.

        Args:
            font: Font used for command output.
            parent: Optional owning widget.
            output_theme: Resolved colors shared by tabs in the parent window.
        """
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(font)
        self._output_theme = output_theme or resolve_output_theme("system", QApplication.palette())
        self._fmt = QTextCharFormat()
        self._fmt.setProperty(_REQUESTED_FOREGROUND_PROPERTY, self._output_theme.inherited_text)
        _apply_effective_foreground(self._fmt, self._output_theme)

    def append_ansi(self, text: str) -> None:
        """Append text with SGR styles and contrast-safe per-run foregrounds.

        Args:
            text: Output text that may contain ANSI escape sequences.

        Returns:
            None.
        """
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        last_end = 0
        for match in _ANSI_ESC_RE.finditer(text):
            # Flush plain text up to the escape sequence
            plain = text[last_end : match.start()]
            if plain:
                cursor.insertText(plain, self._fmt)

            sgr_match = re.fullmatch(r"\x1B\[([0-9;]*)m", match.group(0))
            if sgr_match:
                raw = sgr_match.group(1)
                codes = [int(c) for c in raw.split(";") if c] if raw else [0]
                self._fmt = _parse_sgr(codes, self._fmt, self._output_theme)

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

    def __init__(self, parent=None, services=None, theme_manager=None):
        """Initialize an output window with an immutable theme rendering context.

        Args:
            parent: Optional parent widget.
            services: Application services used to load and persist font settings.
            theme_manager: Active theme manager, or ``None`` for system palette mode.

        Returns:
            None.

        Raises:
            AttributeError: If required application services are not provided.
        """
        super().__init__(parent)
        self.services = services
        theme = theme_manager.current_theme if theme_manager else "system"
        self._output_theme = resolve_output_theme(theme, QApplication.palette())
        self.setWindowTitle("Command Output")
        self.setGeometry(100, 100, 900, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Resolve display font from settings
        settings = self.services.config_manager.get_settings()
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
        """Create and display a tab for one running process.

        Args:
            title: Tab label shown to the user.

        Returns:
            The newly created output widget.

        Raises:
            RuntimeError: If Qt cannot create or attach the tab widget.
        """
        tab = _OutputTab(self._font, self, self._output_theme)
        tab.verticalScrollBar().rangeChanged.connect(
            lambda _min, _max, t=tab: self._maybe_scroll(t)
        )
        idx = self._tabs.addTab(tab, title)
        self._tabs.setCurrentIndex(idx)
        self.show()
        self.raise_()
        return tab

    def append_output(self, tab: "_OutputTab", text: str) -> None:
        """Append command output and scroll when auto-scroll is enabled.

        Args:
            tab: Output tab receiving the text.
            text: Command output, optionally containing ANSI SGR sequences.

        Returns:
            None.
        """
        tab.append_ansi(text)
        if self._auto_scroll:
            tab.verticalScrollBar().setValue(tab.verticalScrollBar().maximum())

    # ------------------------------------------------------------------
    # Legacy compatibility shim
    # Used by show_command_output in TrayApp when process output arrives
    # all-at-once after the process finishes.
    # ------------------------------------------------------------------

    @classmethod
    def show_output(
        cls,
        title: str,
        output: str,
        parent: QWidget | None = None,
        services=None,
        theme_manager=None,
    ) -> "RichOutputWindow":
        """Create a stand-alone themed window and display one output stream.

        Args:
            title: Process label for the output tab.
            output: Complete output text to render.
            parent: Optional parent widget.
            services: Application services used for window preferences.
            theme_manager: Optional theme manager; absent means system palette mode.

        Returns:
            The shown output window.
        """
        win = cls(parent, services, theme_manager)
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
                settings = self.services.config_manager.get_settings()
                settings["output_font"] = {"family": font.family(), "size": font.pointSize()}
                self.services.config_manager.save_settings(settings)
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
