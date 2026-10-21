import re
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PyQt6.QtGui import QFont, QTextCharFormat

import core.theme_manager as theme_manager_module
import ui.output_window as output_window
from core.theme_manager import ThemeManager
from ui.output_window import RichOutputWindow, _OutputTab, _parse_sgr


def test_rich_output_window_instantiates(qtbot):
    mock_services = MagicMock()
    window = RichOutputWindow(services=mock_services)
    qtbot.addWidget(window)
    assert window is not None


def test_parse_sgr_reset():
    """SGR code 0 resets the format."""
    fmt = QTextCharFormat()
    result = _parse_sgr([0], fmt)
    assert result is not None


def test_parse_sgr_text_styles():
    """SGR codes for bold, italic, underline, and their reset variants."""
    fmt = QTextCharFormat()
    result = _parse_sgr([1, 3, 4, 22, 23, 24], fmt)
    assert result is not None


def test_parse_sgr_colors():
    """SGR codes for foreground/background colours and their clear codes."""
    fmt = QTextCharFormat()
    result = _parse_sgr([31, 41, 39, 49, 90, 100], fmt)
    assert result is not None


def test_output_tab_instantiates(qtbot):
    """_OutputTab can be created with a stub QFont."""
    from PyQt6.QtGui import QFont

    font = QFont()
    tab = _OutputTab(font)
    qtbot.addWidget(tab)
    assert tab is not None


def test_open_process_tab(qtbot):
    """open_process_tab creates a new tab and returns an _OutputTab."""
    mock_services = MagicMock()
    window = RichOutputWindow(services=mock_services)
    qtbot.addWidget(window)
    tab = window.open_process_tab("Test Process")
    assert tab is not None


def test_append_output(qtbot):
    """append_output forwards text with ANSI sequences to the tab."""
    mock_services = MagicMock()
    window = RichOutputWindow(services=mock_services)
    qtbot.addWidget(window)
    tab = window.open_process_tab("Test")
    window.append_output(tab, "Hello \x1b[1mBold\x1b[0m World")


def test_show_output(qtbot):
    """show_output class-method creates a standalone window."""
    mock_services = MagicMock()
    win = RichOutputWindow.show_output("title", "some output", services=mock_services)
    qtbot.addWidget(win)
    assert win is not None


class _Color:
    """Small QColor stand-in for deterministic tests under the Qt stub fixture."""

    def __init__(self, value):
        if isinstance(value, _Color):
            self.rgb = value.rgb
        else:
            value = value.lstrip("#")
            self.rgb = tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))

    def red(self):
        return self.rgb[0]

    def green(self):
        return self.rgb[1]

    def blue(self):
        return self.rgb[2]

    def name(self):
        return "#" + "".join(f"{value:02x}" for value in self.rgb)


class _Brush:
    def __init__(self, color=None):
        self._color = color

    def color(self):
        return self._color

    def style(self):
        return bool(self._color)


class _Format:
    """QTextCharFormat stand-in that retains colors and user properties."""

    def __init__(self, other=None):
        self._foreground = _Brush()
        self._background = _Brush()
        self._properties = {}
        if isinstance(other, _Format):
            self._foreground = other._foreground
            self._background = other._background
            self._properties = dict(other._properties)

    def setForeground(self, color):
        self._foreground = _Brush(color)

    def foreground(self):
        return self._foreground

    def clearForeground(self):
        self._foreground = _Brush()

    def setBackground(self, color):
        self._background = _Brush(color)

    def background(self):
        return self._background

    def clearBackground(self):
        self._background = _Brush()

    def setProperty(self, key, value):
        self._properties[key] = value

    def property(self, key):
        return self._properties.get(key)

    def setFontWeight(self, value):
        pass

    def setFontItalic(self, value):
        pass

    def setFontUnderline(self, value):
        pass


@pytest.fixture(autouse=True)
def color_format_types(monkeypatch):
    monkeypatch.setattr(output_window, "QColor", _Color)
    monkeypatch.setattr(output_window, "QTextCharFormat", _Format)
    monkeypatch.setattr(
        output_window,
        "QPalette",
        type(
            "PaletteRoles", (), {"ColorRole": type("Roles", (), {"Base": "base", "Text": "text"})}
        ),
    )

    class SystemPalette:
        def color(self, role):
            return _Color("#e6e9ef" if role == "base" else "#4c4f69")

    class Application:
        @staticmethod
        def palette():
            return SystemPalette()

    monkeypatch.setattr(output_window, "QApplication", Application)
    return _Color, _Format


def _color_name(brush):
    return brush.color().name() if brush.style() else None


def _render(text, mode, color_format_types, theme=None):
    """Run ANSI parsing through the tab insertion path and return inserted formats."""
    _color, format_type = color_format_types
    tab = _OutputTab.__new__(_OutputTab)
    tab._fmt = format_type()
    tab._output_theme = theme or output_window._OutputTheme(
        surface=_color(output_window._THEME_SURFACES[mode]),
        inherited_text=_color(output_window._THEME_TEXT[mode]),
        mode=mode,
    )
    tab._fmt.setProperty(
        output_window._REQUESTED_FOREGROUND_PROPERTY, tab._output_theme.inherited_text
    )
    output_window._apply_effective_foreground(tab._fmt, tab._output_theme)
    # Retention/batching state required by the non-batched insertion path.
    tab._max_output_chars = 1_000_000
    tab._batch_enabled = False
    tab._batch_chunk_count = 200
    tab._batch_delay_ms = 50
    tab._scroll_to_bottom = False
    tab._pending = []
    tab._pending_chars = 0
    tab._insert_history = deque()
    tab._document_length = 0
    inserted = []

    class Cursor:
        def movePosition(self, position):
            pass

        def insertText(self, value, fmt):
            if value:
                inserted.append((value, format_type(fmt)))

        def beginEditBlock(self):
            pass

        def endEditBlock(self):
            pass

        def remove(self, *args, **kwargs):
            pass

    cursor = Cursor()
    tab.textCursor = lambda: cursor
    tab.setTextCursor = lambda value: None
    tab.append_ansi(text, batch=False)
    return inserted


def _ratio(foreground, background):
    return output_window.contrast_ratio(_Color(foreground), _Color(background))


@pytest.mark.parametrize(
    ("mode", "foreground", "expected"),
    [
        ("light", 31, "#d20f39"),
        ("light", 97, "#4c4f69"),
        ("light", 90, "#5c5f77"),
        ("dark", 31, "#f38ba8"),
        ("dark", 97, "#ffffff"),
        ("dark", 90, "#585b70"),
    ],
)
def test_theme_ansi_foreground_palettes(mode, foreground, expected):
    assert output_window._ANSI_PALETTES[mode][foreground] == expected


@pytest.mark.parametrize(
    ("mode", "background", "expected"),
    [
        ("light", 41, "#d20f39"),
        ("light", 107, "#4c4f69"),
        ("dark", 41, "#f38ba8"),
        ("dark", 47, "#cdd6f4"),
        ("dark", 107, "#ffffff"),
    ],
)
def test_theme_ansi_background_palettes(mode, background, expected):
    assert output_window._ANSI_PALETTES[mode][background] == expected


@pytest.mark.parametrize(
    ("mode", "surface", "inherited"),
    [
        ("light", "#e6e9ef", "#4c4f69"),
        ("dark", "#181825", "#cdd6f4"),
    ],
)
def test_explicit_theme_uses_qtextedit_surface_and_text(mode, surface, inherited):
    resolved = output_window.resolve_output_theme(mode, None)
    assert resolved.surface.name() == surface
    assert resolved.inherited_text.name() == inherited
    assert resolved.mode == mode


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_window_uses_theme_manager_current_theme(mode):
    window = RichOutputWindow(services=MagicMock(), theme_manager=MagicMock(current_theme=mode))
    assert window._output_theme.mode == mode


@pytest.mark.parametrize(
    ("mode", "sequence", "expected_background"),
    [
        ("light", "\x1b[107mtext", "#4c4f69"),
        ("dark", "\x1b[47mtext", "#cdd6f4"),
    ],
)
def test_background_only_sgr_uses_contrast_safe_rendered_foreground(
    mode, sequence, expected_background, color_format_types
):
    rendered = _render(sequence, mode, color_format_types)[0][1]
    foreground = _color_name(rendered.foreground())
    background = _color_name(rendered.background())
    assert background == expected_background
    assert _ratio(foreground, background) >= 4.5


@pytest.mark.parametrize(
    ("mode", "sequence"),
    [
        ("light", "\x1b[31;44mred on blue"),
        ("light", "\x1b[44;31mred on blue"),
        ("dark", "\x1b[91;104mbright red on bright blue"),
        ("dark", "\x1b[104;91mbright red on bright blue"),
    ],
)
def test_explicit_foreground_background_order_is_contrast_safe(mode, sequence, color_format_types):
    rendered = _render(sequence, mode, color_format_types)[0][1]
    assert _ratio(_color_name(rendered.foreground()), _color_name(rendered.background())) >= 4.5


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_all_ansi_foreground_background_pairs_remain_legible(mode, color_format_types):
    foreground_codes = sorted(output_window._ANSI_FOREGROUND_CODES)
    background_codes = sorted(output_window._ANSI_BACKGROUND_CODES)
    for foreground_code in foreground_codes:
        for background_code in background_codes:
            rendered = _render(
                f"\x1b[{foreground_code};{background_code}mtext",
                mode,
                color_format_types,
            )[0][1]
            background = _color_name(rendered.background())
            assert background == output_window._ANSI_PALETTES[mode][background_code]
            assert _ratio(_color_name(rendered.foreground()), background) >= 4.5


def test_sgr_foreground_background_and_full_reset_restore_theme_colors(color_format_types):
    rendered = _render(
        "\x1b[31;44mcolored\x1b[39mdefault foreground\x1b[49mdefault surface\x1b[0mreset",
        "light",
        color_format_types,
    )
    assert (
        _ratio(_color_name(rendered[1][1].foreground()), _color_name(rendered[1][1].background()))
        >= 4.5
    )
    assert _color_name(rendered[1][1].background()) == "#1e66f5"
    assert _color_name(rendered[2][1].foreground()) == "#4c4f69"
    assert _color_name(rendered[2][1].background()) is None
    assert _color_name(rendered[3][1].foreground()) == "#4c4f69"
    assert _color_name(rendered[3][1].background()) is None


def test_trimmed_content_contrast_and_format_preserved(color_format_types):
    """ANSI formatting survives cap trimming: retained tail stays legible."""
    max_chars = 120
    _color, format_type = color_format_types

    tab = _OutputTab.__new__(_OutputTab)
    tab._fmt = format_type()
    tab._output_theme = output_window._OutputTheme(
        surface=_color(output_window._THEME_SURFACES["dark"]),
        inherited_text=_color(output_window._THEME_TEXT["dark"]),
        mode="dark",
    )
    tab._fmt.setProperty(
        output_window._REQUESTED_FOREGROUND_PROPERTY, tab._output_theme.inherited_text
    )
    output_window._apply_effective_foreground(tab._fmt, tab._output_theme)
    tab._max_output_chars = max_chars
    tab._batch_enabled = False
    tab._batch_chunk_count = 200
    tab._batch_delay_ms = 50
    tab._scroll_to_bottom = False
    tab._pending = []
    tab._pending_chars = 0
    tab._insert_history = deque()
    tab._document_length = 0

    class Cursor:
        def movePosition(self, position):
            pass

        def insertText(self, value, fmt):
            if value:
                tab._inserted.append((value, format_type(fmt)))

        def beginEditBlock(self):
            pass

        def endEditBlock(self):
            pass

        def remove(self, *args, **kwargs):
            pass

    tab._inserted = []
    cursor = Cursor()
    tab.textCursor = lambda: cursor
    tab.setTextCursor = lambda value: None
    tab.append_ansi("\x1b[31;44m" + "x" * (max_chars + 60) + "\x1b[91;104mtail\x1b[0m", batch=False)

    assert tab._inserted, "expected inserted content"
    _, tail_fmt = tab._inserted[-1]
    background = tail_fmt.background().color().name() if tail_fmt.background().style() else None
    foreground = tail_fmt.foreground().color().name() if tail_fmt.foreground().style() else None
    assert background == output_window._ANSI_PALETTES["dark"][104]
    assert _ratio(foreground, background) >= 4.5


@pytest.mark.parametrize(
    ("base", "text", "mode"),
    [("#f0f0f0", "#333333", "light"), ("#181825", "#cdd6f4", "dark")],
)
def test_system_theme_uses_application_base_text_and_luminance(
    base, text, mode, color_format_types
):
    _color, _format = color_format_types
    requested_roles = []

    class Palette:
        def color(self, role):
            requested_roles.append(role)
            return {"base": _color(base), "text": _color(text)}[role]

    resolved = output_window.resolve_output_theme("system", Palette())
    assert resolved.surface.name() == base
    assert resolved.inherited_text.name() == text
    assert resolved.mode == mode
    assert requested_roles == ["base", "text"]

    for background_code in sorted(output_window._ANSI_BACKGROUND_CODES):
        rendered = _render(f"\x1b[{background_code}mtext", mode, color_format_types, resolved)[0][1]
        background = _color_name(rendered.background())
        assert background == output_window._ANSI_PALETTES[mode][background_code]
        assert _ratio(_color_name(rendered.foreground()), background) >= 4.5


def test_low_contrast_native_palette_text_uses_black_or_white_fallback(color_format_types):
    _color, _format = color_format_types

    class Palette:
        def color(self, role):
            return _color("#ffffff" if role == "base" else "#fefefe")

    resolved = output_window.resolve_output_theme("system", Palette())
    rendered = _render("native text", resolved.mode, color_format_types, resolved)[0][1]
    foreground = _color_name(rendered.foreground())
    assert foreground in {"#000000", "#ffffff"}
    assert _ratio(foreground, "#ffffff") >= 4.5


def test_standalone_window_uses_system_palette_without_theme_manager(
    monkeypatch, color_format_types
):
    _color, _format = color_format_types

    class Palette:
        def color(self, role):
            return _color("#181825" if role == "base" else "#cdd6f4")

    class Application:
        @staticmethod
        def palette():
            return Palette()

    monkeypatch.setattr(output_window, "QApplication", Application)
    window = RichOutputWindow(services=MagicMock())
    assert window._output_theme.surface.name() == "#181825"
    assert window._output_theme.inherited_text.name() == "#cdd6f4"
    assert window._output_theme.mode == "dark"


def test_open_window_keeps_rendered_contrast_when_application_theme_changes(
    monkeypatch, color_format_types
):
    """An open output tab keeps its captured surface when global QSS changes."""
    color_type, format_type = color_format_types

    class Application:
        stylesheet = ""

        @classmethod
        def instance(cls):
            return cls

        @classmethod
        def palette(cls):
            return type(
                "Palette",
                (),
                {
                    "color": lambda _self, role: color_type(
                        "#e6e9ef" if role == "base" else "#4c4f69"
                    )
                },
            )()

        @classmethod
        def setStyleSheet(cls, stylesheet):
            cls.stylesheet = stylesheet

    monkeypatch.setattr(output_window, "QApplication", Application)
    monkeypatch.setattr(theme_manager_module, "QApplication", Application)
    widget_stylesheets = {}
    monkeypatch.setattr(
        _OutputTab,
        "setStyleSheet",
        lambda tab, stylesheet: widget_stylesheets.__setitem__(tab, stylesheet),
        raising=False,
    )

    theme_manager = ThemeManager(str(Path(__file__).resolve().parents[1]))
    theme_manager.apply_theme("light")
    window = RichOutputWindow(services=MagicMock(), theme_manager=theme_manager)
    tab = window.open_process_tab("Theme transition")
    inserted = []

    class Cursor:
        def movePosition(self, _position):
            pass

        def insertText(self, text, fmt):
            inserted.append((text, format_type(fmt)))

        def beginEditBlock(self):
            pass

        def endEditBlock(self):
            pass

        def remove(self, *args, **kwargs):
            pass

    cursor = Cursor()
    tab.textCursor = lambda: cursor
    window.append_output(tab, "inherited foreground")
    # The live path batches output; flush so the document sees the text.
    tab.flush()

    theme_manager.apply_theme("dark")
    effective_stylesheet = widget_stylesheets.get(tab, Application.stylesheet)
    text_edit = re.search(r"QTextEdit,\s*QPlainTextEdit\s*\{([^}]*)\}", effective_stylesheet)
    declarations = text_edit.group(1) if text_edit else effective_stylesheet
    surface_match = re.search(r"background-color:\s*(#[0-9a-fA-F]{6})", declarations)
    assert surface_match is not None
    actual_surface = color_type(surface_match.group(1))
    rendered_foreground = inserted[0][1].foreground().color()

    assert actual_surface.name() == "#e6e9ef"
    assert output_window.contrast_ratio(rendered_foreground, actual_surface) >= 4.5


# ---------------------------------------------------------------------------
# Issue #170: bounded retained output and batched high-volume updates
# ---------------------------------------------------------------------------


def _new_tab(qtbot, **kwargs):
    """Create a real ``_OutputTab`` for retention/batching tests."""
    font = QFont()
    tab = _OutputTab(font, **kwargs)
    qtbot.addWidget(tab)
    return tab


def test_window_applies_output_history_settings_to_tabs(qtbot):
    """``output_history`` settings flow into every tab opened by the window."""

    class FakeConfigManager:
        def get_settings(self):
            return {
                "output_font": {"family": "monospace", "size": 10},
                "output_history": {
                    "max_output_chars": 1234,
                    "batch_enabled": False,
                    "batch_chunk_count": 7,
                    "batch_delay_ms": 15,
                },
            }

    class FakeServices:
        config_manager = FakeConfigManager()

    window = RichOutputWindow(services=FakeServices())
    qtbot.addWidget(window)

    assert window._max_output_chars == 1234
    assert window._batch_enabled is False
    assert window._batch_chunk_count == 7
    assert window._batch_delay_ms == 15

    tab = window.open_process_tab("Configured")
    assert tab._max_output_chars == 1234
    assert tab._batch_enabled is False
    assert tab._batch_chunk_count == 7
    assert tab._batch_delay_ms == 15


def test_output_tab_bounds_retained_output_and_keeps_tail(qtbot):
    """Emitting more than the cap drops the oldest content and keeps the tail."""
    tab = _new_tab(qtbot, batch_enabled=False, max_output_chars=200, scroll_to_bottom=False)
    chunk = "X" * 100
    for _ in range(3):
        tab.append_ansi(chunk)

    assert tab._document_length == 200
    assert sum(length - consumed for length, consumed in tab._insert_history) == 200
    # The most recent chunk is retained untouched (its content is the tail).
    assert tab._insert_history[-1] == (100, 0)


def test_output_tab_trims_partial_oldest_insert_at_cap_boundary(qtbot):
    """A cap boundary inside the oldest insert keeps the tail slice intact."""
    tab = _new_tab(qtbot, batch_enabled=False, max_output_chars=150, scroll_to_bottom=False)
    tab.append_ansi("A" * 100)
    tab.append_ansi("B" * 100)

    assert tab._document_length == 150
    # The oldest insert is partially consumed; the newest insert is untouched.
    assert tab._insert_history[0] == (100, 50)
    assert tab._insert_history[-1] == (100, 0)


def test_output_tab_batches_and_flushes_by_chunk_count(qtbot):
    """Chunks are coalesced and flushed once the chunk count is reached."""
    tab = _new_tab(
        qtbot, batch_enabled=True, batch_chunk_count=3, batch_delay_ms=1000, scroll_to_bottom=False
    )
    tab.append_ansi("a")
    tab.append_ansi("b")
    assert tab._pending == ["a", "b"]
    assert tab._pending_chars == 2
    assert tab._document_length == 0

    tab.append_ansi("c")  # reaches the chunk count -> immediate flush
    assert tab._pending == []
    assert tab._pending_chars == 0
    assert tab._document_length == 3
    assert len(tab._insert_history) == 1

    # Chunks below the count stay pending until flushed explicitly.
    tab.append_ansi("d")
    tab.append_ansi("e")
    assert tab._pending == ["d", "e"]
    assert tab._document_length == 3
    tab.flush()
    assert tab._pending == []
    assert tab._document_length == 5


def test_output_tab_flush_hook_drains_batched_chunks(qtbot):
    """The flush hook drains buffered chunks (what the single-shot timer does).

    The timer is a stub in the test environment, so we verify the flush
    behaviour directly rather than introspecting the timer object's mock
    internals, which differ across test-collection order.
    """
    tab = _new_tab(
        qtbot, batch_enabled=True, batch_chunk_count=1000, batch_delay_ms=25, scroll_to_bottom=False
    )
    tab.append_ansi("x")
    tab.append_ansi("y")
    assert tab._pending == ["x", "y"]
    assert tab._document_length == 0

    tab.flush()  # simulates a single-shot timer firing
    assert tab._pending == []
    assert tab._document_length == 2


def test_output_tab_preserves_ansi_formatting_across_batch_flush(qtbot):
    """SGR state set in one chunk still applies to the next chunk in the batch."""
    tab = _new_tab(
        qtbot, batch_enabled=True, batch_chunk_count=2, batch_delay_ms=1000, scroll_to_bottom=False
    )
    tab.append_ansi("\x1b[31m")  # SGR foreground red
    tab.append_ansi("red text")
    tab.flush()

    requested = tab._fmt.property(output_window._REQUESTED_FOREGROUND_PROPERTY)
    assert requested.name() == output_window._ANSI_PALETTES[tab._output_theme.mode][31]


def test_show_output_bypasses_batch_queue(qtbot):
    """The legacy bulk path inserts immediately instead of queueing."""
    from unittest.mock import patch

    mock_services = MagicMock()
    captured = {}
    original_open = RichOutputWindow.open_process_tab

    def _capture(self, title):
        tab = original_open(self, title)
        captured["tab"] = tab
        return tab

    with patch.object(RichOutputWindow, "open_process_tab", _capture):
        win = RichOutputWindow.show_output("title", "bulk output", services=mock_services)
    qtbot.addWidget(win)

    tab = captured["tab"]
    assert tab is not None
    assert tab._pending == []
    assert tab._document_length <= tab._max_output_chars
    assert len(tab._insert_history) == 1


def test_clear_output_resets_retention_and_pending_batch_state(qtbot):
    """Clearing a tab discards both visible output and queued retention state."""
    tab = _new_tab(qtbot, batch_enabled=True, batch_chunk_count=1000)
    tab.append_ansi("buffered output")
    assert tab._pending == ["buffered output"]

    tab.clear_output()
    tab.flush()

    assert tab._pending == []
    assert tab._pending_chars == 0
    assert tab._insert_history == deque()
    assert tab._document_length == 0


def test_existing_tab_flush_respects_current_auto_scroll_preference(qtbot):
    """Turning auto-scroll off affects tabs that were already open."""
    window = RichOutputWindow(services=MagicMock())
    qtbot.addWidget(window)
    tab = window.open_process_tab("Existing tab")
    scroll_bar = MagicMock()
    scroll_bar.maximum.return_value = 10
    tab.verticalScrollBar = lambda: scroll_bar

    window._toggle_auto_scroll(False)
    tab.append_ansi("output")
    tab.flush()

    scroll_bar.setValue.assert_not_called()


def test_flush_inserts_pending_chunks_as_one_document_batch(qtbot):
    """A pending stream is parsed and inserted in one document update."""
    tab = _new_tab(qtbot, batch_enabled=True, batch_chunk_count=1000)
    tab.append_ansi("first ")
    tab.append_ansi("second")

    tab.flush()

    assert len(tab._insert_history) == 1
    assert tab._insert_history[0] == (12, 0)


def test_real_pyqt_cursor_prunes_document_head_with_supported_selection_api(
    qtbot, monkeypatch
):
    """Head trimming uses QTextCursor selection APIs available in real PyQt6."""
    if not isinstance(output_window.QTextCursor, type):
        pytest.skip("requires the real PyQt6 classes")

    monkeypatch.undo()
    from PyQt6.QtGui import QFont as RealQFont

    tab = _OutputTab(RealQFont(), max_output_chars=5, batch_enabled=False)
    qtbot.addWidget(tab)
    tab.append_ansi("abcdef")

    assert tab.toPlainText() == "bcdef"
    assert tab._document_length == 5


def test_real_pyqt_retained_ansi_format_survives_head_trimming(qtbot, monkeypatch):
    """The retained ANSI tail keeps its contrast-safe foreground/background."""
    if not isinstance(output_window.QTextCursor, type):
        pytest.skip("requires the real PyQt6 classes")

    monkeypatch.undo()
    from PyQt6.QtGui import QFont as RealQFont

    theme = output_window.resolve_output_theme("dark", output_window.QApplication.palette())
    tab = _OutputTab(
        RealQFont(), output_theme=theme, max_output_chars=4, batch_enabled=False
    )
    qtbot.addWidget(tab)
    tab.append_ansi("old")
    tab.append_ansi("\x1b[31;44mtail")

    cursor = tab.textCursor()
    cursor.setPosition(0)
    retained_format = cursor.charFormat()
    foreground = retained_format.foreground().color()
    background = retained_format.background().color()

    assert tab.toPlainText() == "tail"
    assert background.name() == output_window._ANSI_PALETTES["dark"][44]
    assert output_window.contrast_ratio(foreground, background) >= 4.5
