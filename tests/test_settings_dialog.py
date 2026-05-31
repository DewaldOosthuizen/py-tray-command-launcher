# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ui.settings_dialog module.

Strategy: install a real-class PyQt6 stub so SettingsDialog becomes a real
Python class. QDialog and all Qt widgets are stubbed with minimal no-op
implementations that allow __init__ to run to completion. We then test
_preview_theme, _save, and _cancel directly on the constructed instance.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def _install_real_pyqt6_stub():
    """Replace the MagicMock PyQt6 stub with one that has real base classes."""
    for key in list(sys.modules.keys()):
        if key.startswith("PyQt6") or key in ("ui.settings_dialog",):
            del sys.modules[key]

    class _Base:
        def __init__(self, *a, **kw):
            pass

    class _QWidget(_Base):
        def show(self): pass
        def hide(self): pass
        def isVisible(self): return False
        def setObjectName(self, n): pass
        def setAttribute(self, *a): pass
        def setMinimumWidth(self, v): pass
        def setWindowTitle(self, t): pass
        def adjustSize(self): pass
        def style(self): return MagicMock()

    class _QDialog(_QWidget):
        def accept(self): pass
        def reject(self): pass
        def exec(self): return 0

    _mm = MagicMock

    pyqt6 = types.ModuleType("PyQt6")
    QtWidgets = types.ModuleType("PyQt6.QtWidgets")
    QtCore = types.ModuleType("PyQt6.QtCore")
    QtGui = types.ModuleType("PyQt6.QtGui")

    QtWidgets.QWidget = _QWidget
    QtWidgets.QDialog = _QDialog
    QtWidgets.QApplication = _mm()

    # QVBoxLayout / QFormLayout / QGroupBox instances must be real enough to
    # support addRow/addWidget calls. A simple no-op _Layout class covers this.
    class _Layout(_Base):
        def addRow(self, *a): pass
        def addWidget(self, *a): pass
        def setContentsMargins(self, *a): pass
        def setSpacing(self, *a): pass
        # count() must return 0 — quick_launch_bar._build_buttons does
        # `while self._layout.count():` and would loop forever otherwise.
        def count(self): return 0
        def takeAt(self, i): return None

    class _QGroupBox(_QWidget):
        pass

    # Avoid SyntaxError: use type() for signal-like attrs
    class _QDialogButtonBox(_QWidget):
        class StandardButton:
            Save = 1
            Cancel = 2

        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.accepted = MagicMock()
            self.accepted.connect = MagicMock()
            self.rejected = MagicMock()
            self.rejected.connect = MagicMock()

        def button(self, *a):
            return MagicMock()

    # QLabel needs a real class — function-level `from PyQt6.QtWidgets import QLabel`
    # calls in other modules re-fetch from sys.modules at test-run time; a MagicMock
    # instance would fail with AttributeError: 'setObjectName'.
    class _QLabel(_Base):
        def __init__(self, *a, **kw): pass
        def setObjectName(self, n): pass
        def addWidget(self, *a): pass

    QtWidgets.QLabel = _QLabel

    for name in [
        "QListWidget", "QListWidgetItem",
        "QPushButton", "QFrame", "QStackedWidget", "QSizePolicy",
        "QToolButton", "QScrollArea",
    ]:
        setattr(QtWidgets, name, _mm())

    # Widget classes that need real instantiation
    QtWidgets.QVBoxLayout = _Layout
    QtWidgets.QFormLayout = _Layout
    QtWidgets.QHBoxLayout = _Layout
    QtWidgets.QGroupBox = _QGroupBox
    QtWidgets.QDialogButtonBox = _QDialogButtonBox

    # Widgets that are just used for value access — MagicMock instances are fine
    class _QComboBox(_Base):
        def __init__(self, *a, **kw):
            self._items = []
            self._idx = 0
            self.currentTextChanged = MagicMock()
            self.currentTextChanged.connect = MagicMock()
        def addItems(self, items): self._items = list(items)
        def findText(self, text): return self._items.index(text) if text in self._items else -1
        def setCurrentIndex(self, i): self._idx = i
        def currentText(self): return self._items[self._idx] if self._items else ""

    class _QLineEdit(_Base):
        def __init__(self, text="", *a, **kw):
            self._text = text
        def text(self): return self._text
        def setPlaceholderText(self, t): pass

    class _QSpinBox(_Base):
        def __init__(self, *a, **kw):
            self._val = 0
        def setRange(self, lo, hi): pass
        def setValue(self, v): self._val = v
        def value(self): return self._val

    class _QCheckBox(_Base):
        def __init__(self, *a, **kw):
            self._checked = False
        def setChecked(self, v): self._checked = v
        def isChecked(self): return self._checked

    QtWidgets.QComboBox = _QComboBox
    QtWidgets.QLineEdit = _QLineEdit
    QtWidgets.QSpinBox = _QSpinBox
    QtWidgets.QCheckBox = _QCheckBox
    QtWidgets.QMessageBox = _mm()

    _qt = _mm()
    _qt.WindowType = _mm()
    _qt.WidgetAttribute = _mm()
    _qt.ConnectionType = _mm()
    _qt.ConnectionType.QueuedConnection = 0

    def _pyqtSignal(*args, **kwargs):
        m = _mm()
        m.connect = _mm()
        m.emit = _mm()
        return m

    QtCore.Qt = _qt
    QtCore.QObject = _Base
    QtCore.pyqtSignal = _pyqtSignal
    QtCore.PYQT_VERSION = 0x060100
    QtCore.PYQT_VERSION_STR = "6.1.0"
    QtCore.QT_VERSION_STR = "6.1.0"
    QtCore.qVersion = lambda: "6.1.0"

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

# Import at module level so SettingsDialog is bound to the correct QDialog stub
# BEFORE test_single_instance.py's module-level code can overwrite QDialog in
# sys.modules["PyQt6.QtWidgets"].
from ui.settings_dialog import SettingsDialog  # noqa: E402

_DEFAULT_SETTINGS = {
    "theme": "dark",
    "hotkey": "ctrl+shift+space",
    "app_launcher_hotkey": "ctrl+alt+a",
    "history_limit": 100,
    "output_font": {"family": "monospace", "size": 12},
    "quick_launch_bar": {"visible": True, "hotkey": "ctrl+shift+b"},
    "logging": {"level": "WARNING"},
}


def _build_dialog_direct(settings_override=None):
    """Build a SettingsDialog using __init__ with stubbed Qt/config objects."""
    settings = dict(_DEFAULT_SETTINGS)
    if settings_override:
        for key, value in settings_override.items():
            if isinstance(value, dict) and isinstance(settings.get(key), dict):
                merged = dict(settings[key])
                merged.update(value)
                settings[key] = merged
            else:
                settings[key] = value

    mock_cm = MagicMock()
    mock_cm.get_settings.return_value = dict(settings)
    mock_theme_mgr = MagicMock()

    with patch("ui.settings_dialog.config_manager", mock_cm):
        dlg = SettingsDialog(mock_theme_mgr)
    dlg.accept = MagicMock()
    dlg.reject = MagicMock()

    return dlg, mock_cm, mock_theme_mgr


class TestSettingsDialogPreview(unittest.TestCase):
    """Test _preview_theme method."""

    def test_preview_theme_calls_theme_manager_apply(self):
        """_preview_theme('light') calls theme_manager.apply_theme('light')."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        dlg._preview_theme("light")
        theme_mgr.apply_theme.assert_called_with("light")

    def test_preview_theme_called_for_all_themes(self):
        """_preview_theme works for dark, light, and system without error."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        for t in ("dark", "light", "system"):
            dlg._preview_theme(t)
        assert theme_mgr.apply_theme.call_count == 3

    def test_preview_theme_passes_through_theme_name(self):
        """Whatever string is passed to _preview_theme reaches apply_theme."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        dlg._preview_theme("custom-theme")
        theme_mgr.apply_theme.assert_called_with("custom-theme")


class TestSettingsDialogCancel(unittest.TestCase):
    """Test _cancel method."""

    def test_cancel_restores_original_theme(self):
        """_cancel reverts to _original_theme."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        dlg._original_theme = "light"
        dlg._cancel()
        theme_mgr.apply_theme.assert_called_with("light")

    def test_cancel_calls_reject(self):
        """_cancel calls dialog.reject()."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        dlg._cancel()
        dlg.reject.assert_called()


class TestSettingsDialogSave(unittest.TestCase):
    """Test _save method."""

    def test_save_calls_config_manager_save_settings(self):
        """_save calls config_manager.save_settings with a dict."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        mock_cm = MagicMock()
        mock_cm.get_settings.return_value = {
            "theme": "dark",
            "quick_launch_bar": {},
            "logging": {},
        }

        with patch("ui.settings_dialog.config_manager", mock_cm):
            dlg._save()

        mock_cm.save_settings.assert_called_once()

    def test_save_writes_theme_from_combo(self):
        """_save stores the selected theme in saved settings."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        dlg._theme_combo.setCurrentIndex(dlg._theme_combo.findText("light"))
        mock_cm = MagicMock()
        mock_cm.get_settings.return_value = {
            "theme": "dark",
            "quick_launch_bar": {},
            "logging": {},
        }

        with patch("ui.settings_dialog.config_manager", mock_cm):
            dlg._save()

        saved = mock_cm.save_settings.call_args[0][0]
        assert saved["theme"] == "light"

    def test_save_writes_hotkey_from_edit(self):
        """_save stores the hotkey text in saved settings."""
        dlg, cm, theme_mgr = _build_dialog_direct()
        dlg._hotkey_edit._text = "ctrl+shift+x"
        mock_cm = MagicMock()
        mock_cm.get_settings.return_value = {
            "theme": "dark",
            "quick_launch_bar": {},
            "logging": {},
        }

        with patch("ui.settings_dialog.config_manager", mock_cm):
            dlg._save()

        saved = mock_cm.save_settings.call_args[0][0]
        assert saved["hotkey"] == "ctrl+shift+x"

    def test_dialog_prepopulates_theme_from_config(self):
        """Config theme value 'dark' should be reflected in dlg._theme_combo."""
        dlg, cm, theme_mgr = _build_dialog_direct({"theme": "dark"})
        assert dlg._theme_combo.currentText() == "dark"

    def test_dialog_prepopulates_hotkey_from_config(self):
        """Config hotkey should be reflected in dlg._hotkey_edit."""
        dlg, cm, theme_mgr = _build_dialog_direct({"hotkey": "ctrl+alt+p"})
        assert dlg._hotkey_edit.text() == "ctrl+alt+p"
