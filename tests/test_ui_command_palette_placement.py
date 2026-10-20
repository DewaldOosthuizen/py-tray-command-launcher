"""Placement tests for the command palette (issue #169).

These tests exercise the new cursor-screen selection and geometry clamping in
``ui.command_palette`` against the REAL PyQt6 back end on the offscreen platform
plugin.  The tests therefore cannot run until the PyQt6 MagicMock stub that
``tests/conftest.py`` injects at module import time is discarded and real Qt is
re-imported, so that cleanup happens at module import time, before any test runs.
"""

import importlib
import sys
from unittest.mock import MagicMock, patch

# --- Real Qt -------------------------------------------------------------
# ``tests/conftest.py`` installs a MagicMock stub for PyQt6 at module import
# time (before any test module is collected) so that the rest of the suite can
# run headlessly.  That stub is only enough for the stub-dependent tests; the
# placement tests below need the real screen/geometry APIs, so every PyQt6 entry
# is removed from sys.modules and real Qt is re-imported *before* the palette
# module is imported.
for _name in list(sys.modules):
    if _name == "PyQt6" or _name.startswith("PyQt6."):
        sys.modules.pop(_name, None)

# The palette module may already have been imported under the stub by an earlier
# test module; drop the cached stub version so the fresh import binds to real Qt.
if "ui.command_palette" in sys.modules:
    del sys.modules["ui.command_palette"]

from PyQt6.QtGui import QGuiApplication, QCursor  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

import pytest  # noqa: E402
import ui.command_palette  # noqa: E402
importlib.reload(ui.command_palette)  # noqa: E402

palette_module = ui.command_palette

# --- QApplication --------------------------------------------------------
@pytest.fixture()
def app():
    """Return a real QApplication on the offscreen platform.

    A single QApplication lives for the session; later tests reuse it.
    """
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


# --- Helpers -------------------------------------------------------------
def _make_window(app):
    """Build a _PaletteWindow whose palette never touches command services.

    Only the placement logic is exercised, so the search population is bypassed
    by temporarily replacing the window's _populate method with a no-op.
    """
    services = MagicMock()
    services.get_all_commands.return_value = [
        {"group": "System", "label": "Terminal", "command": "gnome-terminal"},
        {"group": "System", "label": "Editor", "command": "gedit"},
        {"group": "Git", "label": "Status", "command": "git status"},
    ]
    palette = MagicMock()
    palette._services = services

    window = palette_module._PaletteWindow(palette=palette)
    # The debounce timer is irrelevant to placement; stop it so it never fires.
    window._search_timer.stop()
    return window


# --- Screen selection ----------------------------------------------------
@pytest.mark.needs_multi_display
def test_opens_on_screen_containing_cursor(app):
    """The palette opens on the display that owns the cursor, not the primary screen."""
    if len(QGuiApplication.screens()) < 2:
        pytest.skip("requires a real multi-display setup")

    window = _make_window(app)
    screens = QGuiApplication.screens()
    other = next((screen for screen in screens if screen is not QGuiApplication.primaryScreen()), None)
    assert other is not None
    QCursor.setPos(other.availableGeometry().center())

    with patch.object(window, "_populate", return_value=None):
        window.show_on_tab(palette_module._TAB_COMMANDS)

    cursor_screen = QGuiApplication.screenAt(QCursor.pos())
    assert cursor_screen is not None
    assert cursor_screen is other
    assert cursor_screen is not QGuiApplication.primaryScreen()


# --- Geometry clamping ---------------------------------------------------
@pytest.mark.needs_offscreen_screen
def test_geometry_clamped_to_selected_screen(app):
    """The window is fully contained in the selected screen's available geometry."""
    if QGuiApplication.platformName() != "offscreen":
        pytest.skip("requires QT_QPA_PLATFORM=offscreen")

    window = _make_window(app)
    with patch.object(window, "_populate", return_value=None):
        window.show_on_tab(palette_module._TAB_COMMANDS)

    geo = QGuiApplication.primaryScreen().availableGeometry()
    assert window.width() == min(520, geo.width())
    assert window.height() <= min(460, geo.height())
    assert window.pos().x() >= geo.x()
    assert window.pos().y() >= geo.y()
    assert window.pos().x() + window.width() <= geo.x() + geo.width()
    assert window.pos().y() + window.height() <= geo.y() + geo.height()


# --- Fallback ------------------------------------------------------------
@pytest.mark.needs_offscreen_screen
def test_falls_back_to_primary_screen_when_cursor_outside(app):
    """The primary screen is used when no screen owns the cursor."""
    if QGuiApplication.platformName() != "offscreen":
        pytest.skip("requires QT_QPA_PLATFORM=offscreen")

    window = _make_window(app)
    # The offscreen virtual screen is 800x800 at 0,0, so (-1000, -1000) is outside
    # every screen's geometry and screenAt() returns None.
    QCursor.setPos(-1000, -1000)

    with patch.object(window, "_populate", return_value=None):
        window.show_on_tab(palette_module._TAB_COMMANDS)

    geo = QGuiApplication.primaryScreen().availableGeometry()
    assert window.width() == min(520, geo.width())
    assert window.pos().x() >= geo.x()
    assert window.pos().y() >= geo.y()
    assert window.pos().x() + window.width() <= geo.x() + geo.width()
    assert window.pos().y() + window.height() <= geo.y() + geo.height()
