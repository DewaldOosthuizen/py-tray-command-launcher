"""Keyboard navigation tests for the command palette (issue #198).

These tests exercise the REAL PyQt6 back end and verify that Tab moves focus
between the Commands and Apps tab buttons as configured by setTabOrder,
while _PaletteWindow.eventFilter only handles Return/Enter, Up, Down, and
Escape.  The palette footer hint and the user documentation describe the same
workflow: Tab = focus movement between the tab buttons, Up/Down = list
navigation, Return/Enter = launch, Escape = close.
"""

import importlib
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def keyboard(qtbot):
    """Provide real Qt plus a real _PaletteWindow bound to a MagicMock palette.

    Yields a SimpleNamespace with: window, palette, app (QApplication
    instance), QGuiApplication, QCursor, Qt and tab_commands.  The PyQt6 stub
    and the affected modules are restored when the fixture tears down, so every
    other (stub-dependent) test keeps seeing the stub.
    """
    # Headless CI may not provide a display server. Select Qt's offscreen
    # backend before importing real Qt so QApplication construction is safe.
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    # Save the (stub) state.
    stub = sys.modules.get("PyQt6")
    stub_palette = sys.modules.get("ui.command_palette")
    stub_output = sys.modules.get("ui.output_window")
    print(
        "PYTEST PROBE: PyQt6 in sys.modules =",
        "PyQt6" in sys.modules,
        "| type =",
        type(sys.modules.get("PyQt6")).__name__,
    )

    # Switch to real Qt and re-import the palette (and output window) modules so
    # their cached PyQt6 references bind to the real back end.  PyQt6.QtTest is
    # intentionally left untouched so that the pytest-qt qtbot helper keeps a
    # working reference to QTest (it resolves QtTest at call time).
    for _name in list(sys.modules):
        if _name == "PyQt6" or (_name.startswith("PyQt6.") and _name != "PyQt6.QtTest"):
            sys.modules.pop(_name, None)
    if "ui.command_palette" in sys.modules:
        del sys.modules["ui.command_palette"]
    if "ui.output_window" in sys.modules:
        del sys.modules["ui.output_window"]
    import PyQt6.QtTest  # noqa: F401
    from PyQt6.QtGui import QCursor, QGuiApplication
    from PyQt6.QtWidgets import QApplication
    from pytestqt.qt_compat import qt_api

    import ui.command_palette
    import ui.output_window

    importlib.reload(ui.command_palette)
    real_palette = ui.command_palette

    qt_api.QtTest = sys.modules["PyQt6.QtTest"]

    # Create a real QApplication *before* constructing the window so the
    # offscreen platform's QWidget constructor does not abort.
    application = QApplication.instance()
    if application is None:
        application = QApplication([])

    # Build the _PaletteWindow bound to a MagicMock palette that never touches
    # the command/search services.
    from ui.command_palette import _TAB_COMMANDS

    services = MagicMock()
    services.get_all_commands.return_value = [
        {"group": "System", "label": "Terminal", "command": "gnome-terminal"},
        {"group": "System", "label": "Editor", "command": "gedit"},
        {"group": "Git", "label": "Status", "command": "git status"},
    ]
    palette = MagicMock()
    palette._services = services
    window = real_palette._PaletteWindow(palette=palette)
    # Show the window before setting focus, so that setFocus() actually grants
    # keyboard focus and Tab navigation can be observed through focusWidget().
    window.show()
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
        # The test target's swap of the PyQt6 stub can delete the PyQt6.QtTest
        # entry; make sure it is not left behind on teardown.
        sys.modules.pop("PyQt6.QtTest", None)
    if stub_palette is not None:
        sys.modules["ui.command_palette"] = stub_palette
    if stub_output is not None:
        sys.modules["ui.output_window"] = stub_output


# --- Keyboard navigation tests --------------------------------------------


def test_tab_moves_focus_between_tab_buttons(keyboard, qtbot):
    """Tab moves focus between the Commands and Apps tab buttons.

    setTabOrder is configured as Commands tab button -> Apps tab button ->
    search field -> cmd_list -> app_list -> retry_button, so the chain is:
    Commands tab button, Apps tab button, search field, then the list widgets
    and retry button.  Pressing Tab while the Commands tab button has focus
    moves focus to the Apps tab button, and a second Tab press moves focus to
    the search field.
    """
    from PyQt6.QtCore import Qt

    window = keyboard.window

    # Commands tab button -> Apps tab button
    window._cmd_tab_btn.setFocus()
    print("DEBUG before tab: focusWidget =", window.focusWidget().objectName())
    qtbot.keyClick(window._cmd_tab_btn, Qt.Key.Key_Tab)
    print("DEBUG after tab: focusWidget =", window.focusWidget().objectName())
    assert window.focusWidget() is window._app_tab_btn, (
        "Tab from Commands tab button should move focus to the Apps tab button"
    )

    # Apps tab button -> search field
    window._app_tab_btn.setFocus()
    qtbot.keyClick(window._app_tab_btn, Qt.Key.Key_Tab)
    assert window.focusWidget() is window._search, (
        "Tab from Apps tab button should move focus to the search field"
    )


def test_eventfilter_has_no_key_tab_branch(keyboard):
    """The eventFilter on the search field has no Key_Tab branch.

    Tab is not handled by _PaletteWindow.eventFilter, so pressing Tab while
    the search field has focus moves focus to the next widget in the tab
    order (cmd_list) instead of launching, navigating, or closing.
    """
    window = keyboard.window
    import inspect

    source = inspect.getsource(window.__class__.eventFilter)
    assert "Key_Tab" not in source, "eventFilter should not handle Key_Tab"
    handled = [
        "Qt.Key.Key_Return",
        "Qt.Key.Key_Enter",
        "Qt.Key.Key_Down",
        "Qt.Key.Key_Up",
        "Qt.Key.Key_Escape",
    ]
    for key in handled:
        assert key in source, f"eventFilter should handle {key}"
