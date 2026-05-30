# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared pytest fixtures for py-tray-command-launcher tests.

All fixtures avoid importing PyQt6 at module level so the test suite can run
headlessly without a display (QApplication is only created when a test
explicitly requests the ``qt_app`` fixture).
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# PyQt6 stub — injected before any src module is imported so the test suite
# can run headlessly without PyQt6 installed.
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock as _MagicMock

def _make_pyqt6_stub():
    pyqt6 = _MagicMock()
    pyqt6.QtCore = _MagicMock()
    pyqt6.QtCore.QProcess = _MagicMock()
    pyqt6.QtCore.Qt = _MagicMock()
    # pytest-qt checks PYQT_VERSION as an integer — provide a real int so the
    # comparison does not raise TypeError.
    pyqt6.QtCore.PYQT_VERSION = 0x060100  # 6.1.0
    pyqt6.QtWidgets = _MagicMock()
    # pytest-qt calls QApplication.instance() to process events after each test.
    # Return None so it treats the result as "no app running" and skips gracefully.
    # Must be set as a MagicMock callable directly on the class object.
    _qapp_mock = _MagicMock()
    _qapp_mock.instance = _MagicMock(return_value=None)
    pyqt6.QtWidgets.QApplication = _qapp_mock
    # pytest-qt uses isinstance(widget, QWidget) — must be a real type.
    # All widget base classes must also be this type so that src subclasses pass.
    class _StubAttr:
        """Callable stub that also has attribute access and .connect support."""
        def __call__(self, *args, **kwargs):
            return _StubAttr()  # always chainable
        def __getattr__(self, name):
            return _StubAttr()
        def __int__(self): return 0
        def __bool__(self): return False
        def __str__(self): return ""
        def __repr__(self): return "_StubAttr()"
        def __iter__(self): return iter([])
        def __len__(self): return 0
        def __or__(self, other): return _StubAttr()
        def __ror__(self, other): return _StubAttr()
        def __and__(self, other): return _StubAttr()
        def __ge__(self, other): return True
        def __gt__(self, other): return True
        def __le__(self, other): return True
        def __lt__(self, other): return True
        def __eq__(self, other): return True
        def __hash__(self): return 0
        def connect(self, *a, **kw): pass
        def disconnect(self, *a, **kw): pass
        def emit(self, *a, **kw): pass

    class _StubMeta(type):
        """Metaclass that allows class-level attribute access (e.g. QDialogButtonBox.StandardButton)."""
        def __getattr__(cls, name):
            return _StubAttr()

    class _QWidget(metaclass=_StubMeta):  # noqa: N801
        """Stub base class for all Qt widget types under test."""
        def __init__(self, *args, **kwargs):
            pass
        def __getattr__(self, name):
            attr = _StubAttr()
            object.__setattr__(self, name, attr)
            return attr
    pyqt6.QtWidgets.QWidget = _QWidget
    pyqt6.QtWidgets.QMainWindow = _QWidget
    pyqt6.QtWidgets.QDialog = _QWidget
    pyqt6.QtWidgets.QFrame = _QWidget
    pyqt6.QtWidgets.QTabWidget = _QWidget
    pyqt6.QtWidgets.QToolBar = _QWidget
    pyqt6.QtWidgets.QTextEdit = _QWidget
    pyqt6.QtWidgets.QLabel = _QWidget
    pyqt6.QtWidgets.QPushButton = _QWidget
    pyqt6.QtWidgets.QLineEdit = _QWidget
    pyqt6.QtWidgets.QTreeWidget = _QWidget
    pyqt6.QtWidgets.QTreeWidgetItem = _QWidget
    pyqt6.QtWidgets.QSplitter = _QWidget
    pyqt6.QtWidgets.QScrollArea = _QWidget
    pyqt6.QtWidgets.QComboBox = _QWidget
    pyqt6.QtWidgets.QCheckBox = _QWidget
    pyqt6.QtWidgets.QSpinBox = _QWidget
    pyqt6.QtWidgets.QGroupBox = _QWidget
    pyqt6.QtWidgets.QListWidget = _QWidget
    pyqt6.QtWidgets.QStackedWidget = _QWidget
    pyqt6.QtWidgets.QHBoxLayout = _QWidget
    pyqt6.QtWidgets.QVBoxLayout = _QWidget
    pyqt6.QtWidgets.QFormLayout = _QWidget
    pyqt6.QtWidgets.QGridLayout = _QWidget
    pyqt6.QtWidgets.QSizePolicy = _QWidget
    pyqt6.QtWidgets.QToolButton = _QWidget
    pyqt6.QtWidgets.QAbstractItemView = _QWidget
    pyqt6.QtWidgets.QListWidgetItem = _QWidget
    pyqt6.QtWidgets.QDialogButtonBox = _QWidget
    pyqt6.QtWidgets.QHeaderView = _QWidget
    pyqt6.QtGui = _MagicMock()
    return pyqt6

if "PyQt6" not in sys.modules:
    _stub = _make_pyqt6_stub()
    sys.modules["PyQt6"] = _stub
    sys.modules["PyQt6.QtCore"] = _stub.QtCore
    sys.modules["PyQt6.QtWidgets"] = _stub.QtWidgets
    sys.modules["PyQt6.QtGui"] = _stub.QtGui

# Make src/ importable without installing the package
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_config_dir(tmp_path: Path) -> Path:
    """Return a temporary directory suitable for use as a config dir."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    return cfg


@pytest.fixture()
def tmp_commands_file(tmp_config_dir: Path) -> Path:
    """Write a minimal valid commands.json and return its path."""
    data = {
        "System": {
            "Terminal": {"command": "gnome-terminal"},
            "Editor": {"command": "gedit", "showOutput": False},
        },
        "Git": {
            "Status": {"command": "git status", "showOutput": True},
        },
    }
    path = tmp_config_dir / "commands.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Mock AppServices
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_services() -> MagicMock:
    """Return a MagicMock that quacks like AppServices."""
    svc = MagicMock()
    svc.get_all_commands.return_value = [
        {"group": "System", "label": "Terminal", "command": "gnome-terminal"},
        {"group": "System", "label": "Editor", "command": "gedit"},
        {"group": "Git", "label": "Status", "command": "git status"},
    ]
    svc.resolve_icon_path.return_value = None
    svc.resolve_command_reference.side_effect = lambda group, label, item: item
    return svc
