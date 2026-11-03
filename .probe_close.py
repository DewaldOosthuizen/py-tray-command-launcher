import sys, types
from unittest.mock import MagicMock

# minimal stub mirroring the settings_dialog test stub
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
    def style(self): return MagicMock()
class _QDialog(_QWidget):
    def accept(self): pass
    def reject(self): pass
    def exec(self): return 0
_mm = MagicMock
pyqt6 = types.ModuleType('PyQt6')
QtWidgets = types.ModuleType('PyQt6.QtWidgets')
QtCore = types.ModuleType('PyQt6.QtCore')
QtGui = types.ModuleType('PyQt6.QtGui')
QtWidgets.QWidget = _QWidget
QtWidgets.QDialog = _QDialog
QtWidgets.QApplication = _mm()
class _Layout(_QWidget_base):
    def __init__(self,*a,**k): pass
    def addRow(self,*a): pass
    def addWidget(self,*a): pass
    def setContentsMargins(self,*a): pass
    def setSpacing(self,*a): pass
    def count(self): return 0
    def takeAt(self,i): return None
class _QGroupBox(_QWidget): pass
class _QDialogButtonBox(_QWidget):
    class StandardButton:
        Ok=1; Save=1; Cancel=2
    def __init__(self,*a,**k):
        super().__init__(*a,**k)
        self.accepted=MagicMock(); self.accepted.connect=MagicMock()
        self.rejected=MagicMock(); self.rejected.connect=MagicMock()
    def button(self,*a): return MagicMock()
class _QComboBox(_QWidget_base):
    def __init__(self,*a,**k):
        self._items=[]; self._idx=0
        self.currentTextChanged=MagicMock(); self.currentTextChanged.connect=MagicMock()
    def addItems(self,items): self._items=list(items)
    def findText(self,text): return self._items.index(text) if text in self._items else -1
    def setCurrentIndex(self,i): self._idx=i
    def currentText(self): return self._items[self._idx] if self._items else ''
class _QLineEdit(_QWidget_base):
    def __init__(self,text='',*a,**k): self._text=text
    def text(self): return self._text
    def setPlaceholderText(self,t): pass
class _QSpinBox(_QWidget_base):
    def __init__(self,*a,**k): self._val=0
    def setRange(self,lo,hi): pass
    def setValue(self,v): self._val=v
    def value(self): return self._val
QtWidgets.QComboBox=_QComboBox
QtWidgets.QLineEdit=_QLineEdit
QtWidgets.QSpinBox=_QSpinBox
QtWidgets.QVBoxLayout=_Layout
QtWidgets.QHBoxLayout=_Layout
QtWidgets.QFormLayout=_Layout
QtWidgets.QGroupBox=_QGroupBox
QtWidgets.QDialogButtonBox=_QDialogButtonBox
QtWidgets.QScrollArea=_mm()
QtWidgets.QLabel=_Base
for n in ['QListWidget','QListWidgetItem','QPushButton','QFrame','QStackedWidget','QSizePolicy','QToolButton','QScrollArea','QCheckBox']:
    setattr(QtWidgets, n, _mm())
QtWidgets.QLabel=_Base
QtWidgets.__getattr__=lambda n: _QWidget_base
QtCore.QObject=_Base
QtCore.pyqtSignal=lambda *a,**k: (_mm(),)
QtCore.Qt=_mm()
QtCore.Qt.WindowType=_mm()
QtCore.Qt.WidgetAttribute=_mm()
QtCore.Qt.ConnectionType=_mm(); QtCore.Qt.ConnectionType.QueuedConnection=0
QtGui.QIcon=_mm()
sys.modules['PyQt6']=pyqt6
sys.modules['PyQt6.QtWidgets']=QtWidgets
sys.modules['PyQt6.QtCore']=QtCore
sys.modules['PyQt6.QtGui']=QtGui

sys.path.insert(0, '.')
import ui.settings_dialog as sd
print('QDialog MRO:', sd.QDialog.__mro__)
dlg = sd.SettingsDialog(object(), object())
print('has closeEvent:', hasattr(dlg,'closeEvent'))
print('base has closeEvent:', hasattr(type(dlg),'closeEvent'))
try:
    dlg.closeEvent(Exception())
    print('closeEvent ran without calling super .closeEvent raising?')
except Exception as e:
    print('closeEvent raised:', type(e).__name__, str(e)[:120])
