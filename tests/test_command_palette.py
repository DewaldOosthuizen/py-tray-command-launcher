# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ui.command_palette module.

Strategy: provide a PyQt6 stub with real (empty) base classes so that
src/ui/command_palette.py defines real Python classes we can instantiate
and test. The stub is installed before conftest.py processes so it takes
priority over the MagicMock stub.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Install a real-class PyQt6 stub BEFORE any src imports
# ---------------------------------------------------------------------------


def _install_real_pyqt6_stub():
    """Replace the MagicMock PyQt6 stub with one that has real base classes."""
    # Capture the existing QWidget stub *before* clearing the modules so that
    # instances of our custom _QWidget are still isinstance-compatible with
    # qt_api.QtWidgets.QWidget (which pytest-qt captures during pytest_configure
    # from the conftest stub and never updates afterwards).
    _qw_mod = sys.modules.get("PyQt6.QtWidgets")
    _existing_QWidget = getattr(_qw_mod, "QWidget", None) if _qw_mod else None
    _QWidget_base = _existing_QWidget if isinstance(_existing_QWidget, type) else object

    # Remove existing stub so we can replace key entries
    for key in list(sys.modules.keys()):
        if key.startswith("PyQt6"):
            del sys.modules[key]

    class _Base:
        def __init__(self, *a, **kw):
            pass

    class _QObject(_Base):
        pass

    class _QWidget(_QWidget_base):
        def show(self):
            pass

        def hide(self):
            pass

        def isVisible(self):
            return False

        def raise_(self):
            pass

        def activateWindow(self):
            pass

        def move(self, *a):
            pass

        def adjustSize(self):
            pass

        def x(self):
            return 0

        def y(self):
            return 0

        def setObjectName(self, n):
            pass

        def setAttribute(self, *a):
            pass

        def setMinimumWidth(self, v):
            pass

        def setMaximumHeight(self, v):
            pass

        def setWindowTitle(self, t):
            pass

        def childAt(self, *a):
            return None

        def frameGeometry(self):
            return MagicMock()

        def width(self):
            return 500

        def height(self):
            return 400

        def style(self):
            return MagicMock()

    _mm = MagicMock

    pyqt6 = types.ModuleType("PyQt6")
    QtWidgets = types.ModuleType("PyQt6.QtWidgets")
    QtCore = types.ModuleType("PyQt6.QtCore")
    QtGui = types.ModuleType("PyQt6.QtGui")

    # Real base classes used in class definitions
    QtWidgets.QWidget = _QWidget
    QtWidgets.QDialog = _Base
    QtWidgets.QApplication = _mm()

    # Everything else is a Mock
    for name in [
        "QCheckBox",
        "QComboBox",
        "QDialogButtonBox",
        "QFormLayout",
        "QGroupBox",
        "QLineEdit",
        "QMessageBox",
        "QSpinBox",
        "QVBoxLayout",
        "QHBoxLayout",
        "QLabel",
        "QListWidget",
        "QListWidgetItem",
        "QPushButton",
        "QFrame",
        "QStackedWidget",
        "QSizePolicy",
        "QToolButton",
        "QScrollArea",
    ]:
        setattr(QtWidgets, name, _mm())

    _qt = _mm()
    _qt.WindowType = _mm()
    _qt.WindowType.FramelessWindowHint = 0
    _qt.WindowType.Popup = 0
    _qt.WindowType.NoDropShadowWindowHint = 0
    _qt.WindowType.Tool = 0
    _qt.WindowType.WindowStaysOnTopHint = 0
    _qt.WidgetAttribute = _mm()
    _qt.WidgetAttribute.WA_TranslucentBackground = 0
    _qt.ScrollBarPolicy = _mm()
    _qt.ScrollBarPolicy.ScrollBarAlwaysOff = 0
    _qt.AlignmentFlag = _mm()
    _qt.AlignmentFlag.AlignCenter = 0
    _qt.ConnectionType = _mm()
    _qt.ConnectionType.QueuedConnection = 0
    _qt.ItemDataRole = _mm()
    _qt.ItemDataRole.UserRole = 256
    _qt.Key = _mm()
    _qt.Key.Key_Return = 16777220
    _qt.Key.Key_Enter = 16777221
    _qt.Key.Key_Down = 16777237
    _qt.Key.Key_Up = 16777235
    _qt.Key.Key_Escape = 16777216
    _qt.MouseButton = _mm()
    _qt.MouseButton.LeftButton = 1

    def _pyqtSignal(*args, **kwargs):
        m = _mm()
        m.connect = _mm()
        m.emit = _mm()
        return m

    QtCore.Qt = _qt
    QtCore.QObject = _QObject
    QtCore.QTimer = _mm()
    QtCore.pyqtSignal = _pyqtSignal
    QtCore.PYQT_VERSION = 0x060100
    QtCore.PYQT_VERSION_STR = "6.1.0"
    QtCore.QT_VERSION_STR = "6.1.0"
    QtCore.qVersion = lambda: "6.1.0"
    QtCore.QSize = _mm()
    QtCore.QPoint = _mm()
    QtCore.QEvent = _mm()
    QtCore.QEvent.Type = _mm()
    QtCore.QEvent.Type.KeyPress = 6

    QtGui.QIcon = _mm()
    QtGui.QKeyEvent = _mm()

    # Fallback: any attribute not explicitly listed returns a _QWidget_base
    # subclass-compatible stub so that:
    #   • `from PyQt6.QtWidgets import UnknownClass` works without ImportError
    #   • `class Foo(UnknownClass):` creates a real Python class (not a broken
    #     MagicMock wrapper) that is isinstance-compatible with qt_api.QtWidgets.QWidget
    def _fallback(name):
        return _QWidget_base

    QtWidgets.__getattr__ = _fallback
    QtCore.__getattr__ = _fallback
    QtGui.__getattr__ = _fallback

    pyqt6.QtWidgets = QtWidgets
    pyqt6.QtCore = QtCore
    pyqt6.QtGui = QtGui

    sys.modules["PyQt6"] = pyqt6
    sys.modules["PyQt6.QtWidgets"] = QtWidgets
    sys.modules["PyQt6.QtCore"] = QtCore
    sys.modules["PyQt6.QtGui"] = QtGui


_install_real_pyqt6_stub()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Ensure modules.app_discovery is stubbed
if "modules.app_discovery" not in sys.modules:
    _ad = MagicMock()
    _app = MagicMock()
    _app.name = "TestApp"
    _app.categories_str = "Utility"
    _app.icon_name = ""
    _ad.app_discovery.search.return_value = [_app]
    _ad.app_discovery.resolve_icon_pixmap.return_value = None
    sys.modules["modules.app_discovery"] = _ad

from ui.command_palette import CommandPalette, _PaletteWindow, _score, _to_pynput_str

# ---------------------------------------------------------------------------
# Pure-logic: _score
# ---------------------------------------------------------------------------


class TestScoreFunction(unittest.TestCase):
    def test_exact_match_scores_high(self):
        assert _score("Terminal", "Terminal") >= 90

    def test_partial_match_nonzero(self):
        assert _score("term", "Terminal") > 0

    def test_empty_query_gives_non_negative_score(self):
        score = _score("", "anything")
        assert score >= 0

    def test_no_match_low_score(self):
        assert _score("zzzzunlikely", "Terminal") < 90

    def test_special_chars_do_not_raise(self):
        try:
            _score("!@#$%^", "some command --flag=value")
        except Exception as exc:
            self.fail(f"_score raised unexpectedly: {exc}")


# ---------------------------------------------------------------------------
# Pure-logic: _to_pynput_str
# ---------------------------------------------------------------------------


class TestToPynputStr(unittest.TestCase):
    def test_modifier_keys_get_brackets(self):
        result = _to_pynput_str("ctrl+shift+space")
        assert "<ctrl>" in result and "<shift>" in result and "<space>" in result

    def test_single_alpha_no_brackets(self):
        assert _to_pynput_str("a") == "a"

    def test_multi_char_combo(self):
        result = _to_pynput_str("ctrl+alt+a")
        assert "<ctrl>" in result and "<alt>" in result


# ---------------------------------------------------------------------------
# CommandPalette lifecycle
# ---------------------------------------------------------------------------


class TestCommandPaletteLifecycle(unittest.TestCase):
    def _make_palette(self):
        svc = MagicMock()
        svc.get_all_commands.return_value = [
            {"group": "System", "label": "Terminal", "command": "xterm"},
            {"group": "System", "label": "Editor", "command": "gedit"},
            {"group": "Git", "label": "Status", "command": "git status"},
        ]
        p = CommandPalette(svc)
        return p, svc

    def test_show_palette_shows_commands_tab(self):
        p, svc = self._make_palette()
        mock_win = MagicMock()
        p._window = mock_win
        p.show_palette()
        mock_win.show_on_tab.assert_called_with("commands")

    def test_show_app_launcher_shows_apps_tab(self):
        p, svc = self._make_palette()
        mock_win = MagicMock()
        p._window = mock_win
        p.show_app_launcher()
        mock_win.show_on_tab.assert_called_with("apps")

    def test_register_hotkeys_returns_false_for_empty(self):
        p, svc = self._make_palette()
        result = p.register_hotkeys("", "")
        assert result is False

    def test_unregister_hotkey_no_listener_does_not_raise(self):
        p, svc = self._make_palette()
        p._hotkey_listener = None
        p.unregister_hotkey()  # Should not raise

    def test_show_on_tab_reuses_existing_window(self):
        p, svc = self._make_palette()
        mock_win = MagicMock()
        p._window = mock_win
        p.show_on_tab("commands")
        assert p._window is mock_win

    def test_empty_query_all_commands_shown(self):
        """_populate_commands shows all commands when query is empty."""
        p, svc = self._make_palette()
        win = _PaletteWindow(p)
        win._cmd_list.count.return_value = 0
        win._populate_commands("")
        assert win._cmd_list.addItem.call_count == len(svc.get_all_commands())

    def test_fuzzy_query_filters_commands(self):
        """_populate_commands filters commands by fuzzy query."""
        p, svc = self._make_palette()
        win = _PaletteWindow(p)
        win._cmd_list.count.return_value = 0
        win._populate_commands("terminal")
        assert win._cmd_list.addItem.call_count >= 1

    def test_enter_key_triggers_execute(self):
        """eventFilter triggers _execute on Enter."""
        p, svc = self._make_palette()
        win = _PaletteWindow(p)
        win._execute = MagicMock()
        import ui.command_palette as cp

        class _FakeKeyEvent:
            def __init__(self, key):
                self._key = key

            def type(self):
                return cp.QEvent.Type.KeyPress

            def key(self):
                return self._key

        cp.QKeyEvent = _FakeKeyEvent
        event = _FakeKeyEvent(cp.Qt.Key.Key_Return)
        assert win.eventFilter(win._search, event) is True
        win._execute.assert_called_once()

    def test_escape_key_hides_window(self):
        """eventFilter hides the window on Escape."""
        p, svc = self._make_palette()
        win = _PaletteWindow(p)
        win.hide = MagicMock()
        import ui.command_palette as cp

        class _FakeKeyEvent:
            def __init__(self, key):
                self._key = key

            def type(self):
                return cp.QEvent.Type.KeyPress

            def key(self):
                return self._key

        cp.QKeyEvent = _FakeKeyEvent
        event = _FakeKeyEvent(cp.Qt.Key.Key_Escape)
        assert win.eventFilter(win._search, event) is True
        win.hide.assert_called_once()

    def test_apps_tab_populates_list(self):
        """_switch_tab('apps') switches stack index and repopulates."""
        p, svc = self._make_palette()
        win = _PaletteWindow(p)
        win._populate = MagicMock()
        win._search.text.return_value = "calc"
        win._switch_tab("apps")
        win._stack.setCurrentIndex.assert_called_with(1)
        win._populate.assert_called_once_with("calc")
