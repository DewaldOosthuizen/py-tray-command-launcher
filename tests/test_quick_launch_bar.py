# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ui.quick_launch_bar module.

Strategy: replace the MagicMock PyQt6 stub with one that has real base
classes so QuickLaunchBar becomes a real Python class we can test.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Install a real-class PyQt6 stub BEFORE any src imports
# ---------------------------------------------------------------------------

def _install_real_pyqt6_stub():
    for key in list(sys.modules.keys()):
        if key.startswith("PyQt6") or key in ("ui.quick_launch_bar",):
            del sys.modules[key]

    class _Base:
        def __init__(self, *a, **kw): pass

    class _QObject(_Base): pass

    class _QWidget(_Base):
        def show(self): pass
        def hide(self): pass
        def isVisible(self): return False
        def raise_(self): pass
        def activateWindow(self): pass
        def move(self, *a): pass
        def adjustSize(self): pass
        def x(self): return 100
        def y(self): return 100
        def setObjectName(self, n): pass
        def setAttribute(self, *a): pass
        def childAt(self, *a): return None
        def frameGeometry(self): return MagicMock()
        def style(self): return MagicMock()
        def deleteLater(self): pass

    _mm = MagicMock

    pyqt6 = types.ModuleType("PyQt6")
    QtWidgets = types.ModuleType("PyQt6.QtWidgets")
    QtCore = types.ModuleType("PyQt6.QtCore")
    QtGui = types.ModuleType("PyQt6.QtGui")

    QtWidgets.QWidget = _QWidget
    QtWidgets.QDialog = _Base
    QtWidgets.QApplication = _mm()

    for name in [
        "QCheckBox", "QComboBox", "QDialogButtonBox", "QFormLayout",
        "QGroupBox", "QListWidget", "QListWidgetItem",
        "QPushButton", "QFrame", "QStackedWidget", "QSizePolicy",
        "QToolButton", "QScrollArea",
    ]:
        setattr(QtWidgets, name, _mm())

    # QLabel needs setObjectName for the placeholder in _build_buttons
    class _QLabel(_Base):
        def __init__(self, *a, **kw): pass
        def setObjectName(self, n): pass
        def addWidget(self, *a): pass

    QtWidgets.QLabel = _QLabel

    # QHBoxLayout instances must return 0 from count() to prevent infinite loops
    # in _build_buttons which does: while self._layout.count(): ...
    _hlayout_instance = _mm()
    _hlayout_instance.count.return_value = 0
    _hlayout_class = _mm(return_value=_hlayout_instance)
    QtWidgets.QHBoxLayout = _hlayout_class

    _qt = _mm()
    _qt.WindowType = _mm()
    _qt.WindowType.FramelessWindowHint = 0
    _qt.WindowType.Tool = 0
    _qt.WindowType.WindowStaysOnTopHint = 0
    _qt.WidgetAttribute = _mm()
    _qt.WidgetAttribute.WA_TranslucentBackground = 0
    _qt.ConnectionType = _mm()
    _qt.ConnectionType.QueuedConnection = 0
    _qt.MouseButton = _mm()
    _qt.MouseButton.LeftButton = 1

    def _pyqtSignal(*args, **kwargs):
        m = _mm()
        m.connect = _mm()
        m.emit = _mm()
        return m

    QtCore.Qt = _qt
    QtCore.QObject = _QObject
    QtCore.pyqtSignal = _pyqtSignal
    QtCore.PYQT_VERSION = 0x060100
    QtCore.PYQT_VERSION_STR = "6.1.0"
    QtCore.QT_VERSION_STR = "6.1.0"
    QtCore.qVersion = lambda: "6.1.0"
    QtCore.QPoint = _mm()

    QtGui.QIcon = _mm()

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

from ui.quick_launch_bar import QuickLaunchBar, _to_pynput_str


def _make_services(pinned=None, commands=None, visible=False):
    svc = MagicMock()
    settings = {
        "quick_launch_bar": {
            "visible": visible,
            "position": [100, 100],
            "pinned": pinned if pinned is not None else [],
        }
    }
    svc.config_manager.get_settings.return_value = settings
    svc.get_all_commands.return_value = commands or [
        {"group": "System", "label": "Terminal", "command": "xterm"},
        {"group": "System", "label": "Editor", "command": "gedit"},
    ]
    return svc


def _repair_qtwidgets_stub():
    """Re-apply critical symbols on the live PyQt6.QtWidgets module.

    Other test files (e.g. test_single_instance.py) run module-level code that
    unconditionally overwrites QLabel and QHBoxLayout with plain ``MagicMock``.
    That breaks the function-level `from PyQt6.QtWidgets import QLabel` call
    inside QuickLaunchBar._build_buttons.  Calling this at setUpClass time
    ensures our well-behaved stubs are in place for every test in this file.
    """
    import sys
    QtWidgets = sys.modules.get("PyQt6.QtWidgets")
    if QtWidgets is None:
        return  # nothing to repair

    class _Base:
        def __init__(self, *a, **kw): pass

    class _QLabel(_Base):
        def __init__(self, *a, **kw): pass
        def setObjectName(self, n): pass
        def addWidget(self, *a): pass

    QtWidgets.QLabel = _QLabel

    _hlayout_instance = MagicMock()
    _hlayout_instance.count.return_value = 0
    QtWidgets.QHBoxLayout = MagicMock(return_value=_hlayout_instance)


class TestQuickLaunchBarButtonLogic(unittest.TestCase):
    """Test button-creation logic without real Qt display."""

    @classmethod
    def setUpClass(cls):
        _repair_qtwidgets_stub()

    def test_one_button_per_pinned_item(self):
        """_build_buttons creates one button per valid pinned entry."""
        services = _make_services(pinned=[
            {"group": "System", "label": "Terminal"},
            {"group": "System", "label": "Editor"},
        ])
        bar = QuickLaunchBar(services)
        bar._layout.addWidget.reset_mock()
        bar._build_buttons()
        assert bar._layout.addWidget.call_count == 2

    def test_missing_pinned_command_skipped(self):
        """_build_buttons skips pinned commands that cannot be resolved."""
        services = _make_services(pinned=[{"group": "Nonexistent", "label": "Ghost"}])
        bar = QuickLaunchBar(services)
        bar._layout.addWidget.reset_mock()
        bar._build_buttons()
        assert bar._layout.addWidget.call_count == 0

    def test_clicking_button_triggers_command(self):
        """Generated button click handler executes the command."""
        services = _make_services(pinned=[{"group": "System", "label": "Terminal"}])
        bar = QuickLaunchBar(services)
        import ui.quick_launch_bar as qlb

        qlb.QToolButton.reset_mock()
        bar._build_buttons()
        callback = qlb.QToolButton.return_value.clicked.connect.call_args[0][0]
        callback()
        services.execute.assert_called_once_with(
            "Terminal", "xterm", False, False, None
        )

    def test_bar_instantiation_with_no_pinned_does_not_raise(self):
        """QuickLaunchBar can be created with no pinned commands."""
        services = _make_services(pinned=[])
        try:
            bar = QuickLaunchBar(services)
        except Exception as exc:
            self.fail(f"QuickLaunchBar() raised: {exc}")


class TestQuickLaunchBarToggle(unittest.TestCase):
    """Test toggle() visibility logic."""

    @classmethod
    def setUpClass(cls):
        _repair_qtwidgets_stub()

    def _make_bar(self, visible=False):
        services = _make_services(visible=visible)
        bar = QuickLaunchBar(services)
        return bar, services

    def test_toggle_shows_when_hidden(self):
        """toggle() shows bar when it is hidden."""
        bar, svc = self._make_bar(visible=False)
        bar.show = MagicMock()
        bar.isVisible = MagicMock(return_value=False)
        bar.raise_ = MagicMock()
        bar.activateWindow = MagicMock()
        bar.toggle()
        bar.show.assert_called()

    def test_toggle_hides_when_visible(self):
        """toggle() hides bar when it is visible."""
        bar, svc = self._make_bar(visible=True)
        bar.hide = MagicMock()
        bar.isVisible = MagicMock(return_value=True)
        bar.toggle()
        bar.hide.assert_called()

    def test_toggle_alternates_visibility(self):
        """Calling toggle twice returns to original hidden state."""
        services = _make_services()
        services.config_manager.get_settings.return_value = {"quick_launch_bar": {}}
        bar = QuickLaunchBar(services)
        state = [False]

        bar.isVisible = MagicMock(side_effect=lambda: state[0])
        bar.show = MagicMock(side_effect=lambda: state.__setitem__(0, True))
        bar.hide = MagicMock(side_effect=lambda: state.__setitem__(0, False))
        bar.raise_ = MagicMock()
        bar.activateWindow = MagicMock()

        assert not state[0]
        bar.toggle()
        assert state[0]
        bar.toggle()
        assert not state[0]

    def test_toggle_persists_settings(self):
        """toggle() persists visibility via config_manager.save_settings."""
        services = _make_services()
        services.config_manager.get_settings.return_value = {"quick_launch_bar": {}}
        bar = QuickLaunchBar(services)
        bar.isVisible = MagicMock(return_value=False)
        bar.show = MagicMock()
        bar.raise_ = MagicMock()
        bar.activateWindow = MagicMock()

        bar.toggle()
        services.config_manager.save_settings.assert_called()
