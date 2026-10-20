"""Placement tests for the command palette (issue #169).

These tests exercise the new cursor-screen selection and geometry clamping in
``ui.command_palette`` against the REAL PyQt6 back end.  The real-Qt environment
is scoped to these tests through the :func:`placements` fixture, which rebuilds
real Qt and the affected modules for each test and restores the PyQt6 stub
afterwards, so every other (stub-dependent) test keeps seeing the stub.
"""

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# The real-Qt environment is set up *inside* the :func:`placements` fixture, so
# nothing in this module manipulates sys.modules at module import time.


@pytest.fixture()
def placements():
    """Provide real Qt plus a real _PaletteWindow bound to a MagicMock palette.

    Yields a SimpleNamespace with: window, palette, app (QApplication instance),
    QGuiApplication, QCursor and _TAB_COMMANDS.  The PyQt6 stub and the affected
    modules are restored when the fixture tears down, so every other
    (stub-dependent) test keeps seeing the stub.
    """
    # Save the (stub) state.
    stub = sys.modules.get("PyQt6")
    stub_palette = sys.modules.get("ui.command_palette")
    stub_output = sys.modules.get("ui.output_window")

    # Switch to real Qt and re-import the palette (and output window) modules so
    # their cached PyQt6 references bind to the real back end.
    for _name in list(sys.modules):
        if _name == "PyQt6" or _name.startswith("PyQt6."):
            sys.modules.pop(_name, None)
    if "ui.command_palette" in sys.modules:
        del sys.modules["ui.command_palette"]
    if "ui.output_window" in sys.modules:
        del sys.modules["ui.output_window"]
    from PyQt6.QtGui import QGuiApplication, QCursor  # noqa: F401
    from PyQt6.QtWidgets import QApplication  # noqa: F401
    import ui.command_palette  # noqa: E402
    importlib.reload(ui.command_palette)
    real_palette = ui.command_palette
    import ui.output_window  # noqa: E402

    # Create a real QApplication *before* constructing the window so the
    # offscreen platform's QWidget constructor does not abort.
    application = QApplication.instance()
    if application is None:
        application = QApplication([])

    # Build the _PaletteWindow bound to a MagicMock palette that never touches
    # the command/search services.
    from ui.command_palette import _PaletteWindow, _TAB_COMMANDS
    from unittest.mock import MagicMock

    services = MagicMock()
    services.get_all_commands.return_value = [
        {"group": "System", "label": "Terminal", "command": "gnome-terminal"},
        {"group": "System", "label": "Editor", "command": "gedit"},
        {"group": "Git", "label": "Status", "command": "git status"},
    ]
    palette = MagicMock()
    palette._services = services
    window = real_palette._PaletteWindow(palette=palette)
    # Prevent the debounce timer from firing during placement checks.
    window._search_timer.stop()

    result = SimpleNamespace(
        window=window,
        palette=palette,
        app=application,
        QGuiApplication=QGuiApplication,
        QCursor=QCursor,
        tab_commands=_TAB_COMMANDS,
    )

    yield result

    # Restore the stub so all subsequent tests see the stub again.
    if stub is not None:
        sys.modules["PyQt6"] = stub
        sys.modules["PyQt6.QtCore"] = stub.QtCore
        sys.modules["PyQt6.QtWidgets"] = stub.QtWidgets
        sys.modules["PyQt6.QtGui"] = stub.QtGui
    if stub_palette is not None:
        sys.modules["ui.command_palette"] = stub_palette
    if stub_output is not None:
        sys.modules["ui.output_window"] = stub_output


# --- Helpers -------------------------------------------------------------
def _make_window(placements):
    """Build a _PaletteWindow backed by a MagicMock palette (placement only)."""
    return placements.window


def _move_cursor_to(placements, screen):
    """Move the global cursor to ``screen``'s centre."""
    placements.QCursor.setPos(screen.availableGeometry().center())


# --- Screen selection ----------------------------------------------------
@pytest.mark.needs_multi_display
def test_opens_on_screen_containing_cursor(placements):
    """The palette opens on the display that owns the cursor, not the primary screen."""
    QGuiApplication = placements.QGuiApplication
    if len(QGuiApplication.screens()) < 2:
        pytest.skip("requires a real multi-display setup")

    window = _make_window(placements)
    screens = QGuiApplication.screens()
    other = next((s for s in screens if s is not QGuiApplication.primaryScreen()), None)
    assert other is not None
    _move_cursor_to(placements, other)

    with patch.object(window, "_populate", return_value=None):
        window.show_on_tab(placements.tab_commands)

    cursor_screen = QGuiApplication.screenAt(QCursor.pos())
    assert cursor_screen is not None
    assert cursor_screen is other
    assert cursor_screen is not QGuiApplication.primaryScreen()


# --- Geometry clamping ---------------------------------------------------
@pytest.mark.needs_offscreen_screen
def test_geometry_clamped_to_selected_screen(placements):
    """The window is fully contained in the selected screen's available geometry."""
    QGuiApplication = placements.QGuiApplication
    if QGuiApplication.platformName() != "offscreen":
        pytest.skip("requires QT_QPA_PLATFORM=offscreen")

    window = _make_window(placements)
    with patch.object(window, "_populate", return_value=None):
        window.show_on_tab(placements.tab_commands)

    geo = QGuiApplication.primaryScreen().availableGeometry()
    assert window.width() == min(520, geo.width())
    assert window.height() <= min(460, geo.height())
    assert window.pos().x() >= geo.x()
    assert window.pos().y() >= geo.y()
    assert window.pos().x() + window.width() <= geo.x() + geo.width()
    assert window.pos().y() + window.height() <= geo.y() + geo.height()


# --- Fallback ------------------------------------------------------------
@pytest.mark.needs_offscreen_screen
def test_falls_back_to_primary_screen_when_cursor_outside(placements):
    """The primary screen is used when no screen owns the cursor."""
    QGuiApplication = placements.QGuiApplication
    if QGuiApplication.platformName() != "offscreen":
        pytest.skip("requires QT_QPA_PLATFORM=offscreen")

    window = _make_window(placements)
    # The offscreen virtual screen is 800x800 at 0,0, so (-1000, -1000) is outside
    # every screen's geometry and screenAt() returns None.
    placements.QCursor.setPos(-1000, -1000)

    with patch.object(window, "_populate", return_value=None):
        window.show_on_tab(placements.tab_commands)

    geo = QGuiApplication.primaryScreen().availableGeometry()
    assert window.width() == min(520, geo.width())
    assert window.pos().x() >= geo.x()
    assert window.pos().y() >= geo.y()
    assert window.pos().x() + window.width() <= geo.x() + geo.width()
    assert window.pos().y() + window.height() <= geo.y() + geo.height()
