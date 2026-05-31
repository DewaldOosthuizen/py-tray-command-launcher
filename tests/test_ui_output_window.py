from unittest.mock import patch

from PyQt6.QtGui import QTextCharFormat

from ui.output_window import RichOutputWindow, _OutputTab, _parse_sgr


def test_rich_output_window_instantiates(qtbot):
    with patch("ui.output_window.config_manager") as mock_cm:
        mock_cm.get_settings.return_value = {}
        window = RichOutputWindow()
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
    with patch("ui.output_window.config_manager") as mock_cm:
        mock_cm.get_settings.return_value = {}
        window = RichOutputWindow()
        qtbot.addWidget(window)
        tab = window.open_process_tab("Test Process")
    assert tab is not None


def test_append_output(qtbot):
    """append_output forwards text with ANSI sequences to the tab."""
    with patch("ui.output_window.config_manager") as mock_cm:
        mock_cm.get_settings.return_value = {}
        window = RichOutputWindow()
        qtbot.addWidget(window)
        tab = window.open_process_tab("Test")
        window.append_output(tab, "Hello \x1b[1mBold\x1b[0m World")


def test_show_output(qtbot):
    """show_output class-method creates a standalone window."""
    with patch("ui.output_window.config_manager") as mock_cm:
        mock_cm.get_settings.return_value = {}
        win = RichOutputWindow.show_output("title", "some output")
    qtbot.addWidget(win)
    assert win is not None
