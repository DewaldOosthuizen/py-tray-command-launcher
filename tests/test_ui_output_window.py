from unittest.mock import MagicMock

import pytest
from PyQt6.QtGui import QTextCharFormat

import ui.output_window as output_window
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


@pytest.fixture
def color_format_types(monkeypatch):
    monkeypatch.setattr(output_window, "QColor", _Color)
    monkeypatch.setattr(output_window, "QTextCharFormat", _Format)
    return _Color, _Format


def _color_name(brush):
    return brush.color().name() if brush.style() else None


def _render(text, mode, color_format_types):
    """Run ANSI parsing through the tab insertion path and return inserted formats."""
    _color, format_type = color_format_types
    tab = _OutputTab.__new__(_OutputTab)
    tab._fmt = format_type()
    tab._output_theme = output_window._OutputTheme(
        surface=_color(output_window._THEME_SURFACES[mode]),
        inherited_text=_color(output_window._THEME_TEXT[mode]),
        mode=mode,
    )
    inserted = []

    class Cursor:
        def movePosition(self, position):
            pass

        def insertText(self, value, fmt):
            if value:
                inserted.append((value, format_type(fmt)))

    cursor = Cursor()
    tab.textCursor = lambda: cursor
    tab.setTextCursor = lambda value: None
    tab.append_ansi(text)
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
def test_explicit_foreground_background_order_is_contrast_safe(
    mode, sequence, color_format_types
):
    rendered = _render(sequence, mode, color_format_types)[0][1]
    assert _ratio(_color_name(rendered.foreground()), _color_name(rendered.background())) >= 4.5


def test_sgr_foreground_background_and_full_reset_restore_theme_colors(color_format_types):
    rendered = _render(
        "\x1b[31;44mcolored\x1b[39mdefault foreground\x1b[49mdefault surface"
        "\x1b[0mreset",
        "light",
        color_format_types,
    )
    assert _color_name(rendered[1][1].foreground()) == "#4c4f69"
    assert _color_name(rendered[1][1].background()) == "#1e66f5"
    assert _color_name(rendered[2][1].foreground()) == "#4c4f69"
    assert _color_name(rendered[2][1].background()) is None
    assert _color_name(rendered[3][1].foreground()) == "#4c4f69"
    assert _color_name(rendered[3][1].background()) is None


@pytest.mark.parametrize(
    ("base", "text", "mode"),
    [("#f0f0f0", "#333333", "light"), ("#181825", "#cdd6f4", "dark")],
)
def test_system_theme_uses_application_base_text_and_luminance(
    base, text, mode, color_format_types
):
    _color, _format = color_format_types

    class Palette:
        def color(self, role):
            return {"base": _color(base), "text": _color(text)}[role]

    resolved = output_window.resolve_output_theme("system", Palette())
    assert resolved.surface.name() == base
    assert resolved.inherited_text.name() == text
    assert resolved.mode == mode

    rendered = _render("\x1b[107mtext", mode, color_format_types)[0][1]
    assert _ratio(_color_name(rendered.foreground()), _color_name(rendered.background())) >= 4.5


def test_low_contrast_native_palette_text_uses_black_or_white_fallback(color_format_types):
    _color, _format = color_format_types

    class Palette:
        def color(self, role):
            return _color("#ffffff" if role == "base" else "#fefefe")

    resolved = output_window.resolve_output_theme("system", Palette())
    rendered = _render("native text", resolved.mode, color_format_types)[0][1]
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
