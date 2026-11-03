import sys
sys.path.insert(0, 'src')

# Mimic the conftest Qt stub as loaded for test_ui_settings_dialog
import types, unittest.mock as mock

class _Base: pass
class _QWidget_base(object): pass
class _QWidget(_QWidget_base):
    def show(self): pass
    def hide(self): pass
    def isVisible(self): return False
    def setObjectName(self,n): pass
    def setAttribute(self,*a): pass
    def setMinimumWidth(self,v): pass
    def setWindowTitle(self,t): pass
    def adjustSize(self): pass
    def style(self): return mock.MagicMock()
class _QDialog(_QWidget):
    def accept(self): pass
    def reject(self): pass
    def exec(self): return 0

class _QComboBox(_QWidget_base):
    def __init__(self, *a, **kw):
        self._items = []
        self._idx = 0
        self.currentTextChanged = mock.MagicMock()
        self.currentTextChanged.connect = mock.MagicMock()
    def addItems(self, items):
        self._items = list(items)
    def findText(self, text):
        return self._items.index(text) if text in self._items else -1
    def setCurrentIndex(self, i):
        self._idx = i
    def currentText(self):
        return self._items[self._idx] if self._items else ""

_qtwidgets = types.ModuleType('PyQt6.QtWidgets')
_qtcore = types.ModuleType('PyQt6.QtCore')
_qtgui = types.ModuleType('PyQt6.QtGui')
_qtwidgets.QComboBox = _QComboBox
_qtwidgets.QWidget = _QWidget
_qtwidgets.QDialog = _QDialog
_qtwidgets.QApplication = mock.MagicMock()
_qtcore.QObject = _Base
_qtcore.pyqtSignal = lambda *a, **k: (mock.MagicMock(),)
_qtcore.Qt = mock.MagicMock()
_qtcore.Qt.WindowType = mock.MagicMock()
_qtcore.Qt.WidgetAttribute = mock.MagicMock()
_qtcore.Qt.ConnectionType = mock.MagicMock()
_qtcore.Qt.ConnectionType.QueuedConnection = 0
_qtcore.Qt.qVersion = lambda: "6.1.0"
_qtcore.QT_VERSION_STR = "6.1.0"
_qtcore.PYQT_VERSION = 0x060100
_qtcore.PYQT_VERSION_STR = "6.1.0"
_qtgui.QIcon = mock.MagicMock()
_qtgui.QCursor = mock.MagicMock()
_qtgui.QGuiApplication = mock.MagicMock()

sys.modules['PyQt6'] = _qtwidgets
sys.modules['PyQt6.QtWidgets'] = _qtwidgets
sys.modules['PyQt6.QtCore'] = _qtcore
sys.modules['PyQt6.QtGui'] = _qtgui

from ui.settings_dialog import SettingsDialog

# build
settings = {"theme": "dark", "hotkey": "ctrl+shift+space"}
import types as _t
mock_services = _t.SimpleNamespace()
mock_services.config_manager = _t.SimpleNamespace()
mock_services.config_manager.get_settings.return_value = dict(settings)
mock_theme = mock.MagicMock()
dlg = SettingsDialog(mock_services, mock_theme)
print("original_theme:", dlg._original_theme)
print("initial comboText:", repr(dlg._theme_combo.currentText()))
print("items:", dlg._theme_combo._items, "idx:", dlg._theme_combo._idx)

dlg._theme_combo.setCurrentIndex(dlg._theme_combo.findText("light"))
print("after setCurrentIndex(2) -> currentText:", repr(dlg._theme_combo.currentText()))

# call _save
mock_services.config_manager.get_settings.return_value = dict(settings)
mock_services.config_manager.save_settings = mock.MagicMock()
dlg._save()
print("theme_manager.apply_theme calls:", mock_theme.apply_theme.call_args_list)
