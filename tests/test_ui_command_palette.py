import sys
from unittest.mock import MagicMock
import pytest

# PyQt6 stub is injected by conftest.py before this file is collected.
from ui.command_palette import CommandPalette, _PaletteWindow


def test_command_palette_instantiates(mock_services):
    palette = CommandPalette(services=mock_services)
    assert palette is not None


def test_palette_window_instantiates(mock_services, qtbot):
    palette = CommandPalette(services=mock_services)
    window = _PaletteWindow(palette=palette)
    qtbot.addWidget(window)
    assert window is not None
