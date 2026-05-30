import sys
from unittest.mock import MagicMock, patch
import pytest

# PyQt6 stub is injected by conftest.py before this file is collected.
from ui.command_palette import CommandPalette, _PaletteWindow


def test_command_palette_instantiates(mock_services):
    palette = CommandPalette(services=mock_services)
    assert palette is not None


def test_palette_window_instantiates(mock_services, qtbot):
    # Patch _HotkeyTrigger so each CommandPalette() call gets a fresh mock
    # and does not exhaust a shared side_effect iterator.
    with patch("ui.command_palette._HotkeyTrigger", return_value=MagicMock()):
        palette = CommandPalette(services=mock_services)
        window = _PaletteWindow(palette=palette)
        qtbot.addWidget(window)
        assert window is not None
