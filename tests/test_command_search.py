# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for CommandSearch.show_dialog() -- tree population, ordering, keyboard
execution, and dialog dismissal.

PyQt6 is stubbed in conftest.py (sys.modules injection) so these tests run
headlessly without a QApplication. The tests patch the Qt widget classes at
the import location used by src/modules/command_search.py and drive the dialog
via signal emission and direct widget attribute access.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from unittest.mock import MagicMock, patch

# IMPORTANT: conftest's _StubAttr.__eq__ always returns True, so Qt.Key
# comparisons like `key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)` would
# match anything. We provide integer constants that tests use as key values.
_QT_KEY_RETURN = 0x0100002
_QT_KEY_ENTER = 0x01000002
_QT_KEY_ESCAPE = 0x01000004
_QT_KEY_DOWN = 0x01000005
_QT_KEY_UP = 0x01000006


# ---------------------------------------------------------------------------
# Stubs that track their constructed instances
# ---------------------------------------------------------------------------


class _HeaderTracker:
    def setStretchLastSection(self, flag):
        pass


class _TextChangedSignal:
    """Signal stand-in for QLineEdit.textChanged: connect() registers a slot
    and setText() (on the owning stub) dispatches to every registered slot.
    """

    def __init__(self, slots: list):
        self._slots = slots

    def connect(self, slot):
        self._slots.append(slot)

    def disconnect(self, slot):
        try:
            self._slots.remove(slot)
        except ValueError:
            pass


class _ClickedSignal:
    def __init__(self, slots: list):
        self._slots = slots

    def connect(self, slot):
        self._slots.append(slot)

    def disconnect(self, slot):
        try:
            self._slots.remove(slot)
        except ValueError:
            pass

    def emit(self):
        for fn in self._slots:
            fn()


class _TreeItemsChangedSignal:
    """Signal stand-in for QTreeWidget signals that carry (item, selected) tuples."""

    def __init__(self, slots: list):
        self._slots = slots

    def connect(self, slot):
        self._slots.append(slot)

    def disconnect(self, slot):
        try:
            self._slots.remove(slot)
        except ValueError:
            pass


# Simple object to hold Qt.Key constants and other required Qt attributes
class _QtKeyNamespace:
    Key_Return = _QT_KEY_RETURN
    Key_Enter = _QT_KEY_ENTER
    Key_Escape = _QT_KEY_ESCAPE
    Key_Down = _QT_KEY_DOWN
    Key_Up = _QT_KEY_UP


# Mock Qt.Orientation enum (used by QSplitter)
class _Orientation:
    Vertical = 1
    Horizontal = 2


# Mock Qt.ItemDataRole enum (used by tree item data)
class _ItemDataRole:
    UserRole = 1


class _QtNamespace:
    Key = _QtKeyNamespace()
    Orientation = _Orientation()
    ItemDataRole = _ItemDataRole()


class _TrackedTreeWidget:
    """Stub for QTreeWidget that records every added top-level item and the
    instance created so tests can drive current-item selection.
    """

    instances: list = []
    added_items: list = []
    _item_changed_slots: list = []
    _item_double_clicked_slots: list = []

    def __init__(self, *args, **kwargs):
        self._current_item = None
        _TrackedTreeWidget.instances.append(self)

    def setColumnCount(self, count):
        pass

    def setHeaderLabels(self, labels):
        pass

    def header(self):
        return _HeaderTracker()

    def setAlternatingRowColors(self, flag):
        pass

    def setFocus(self):
        pass

    def addTopLevelItem(self, item):
        _TrackedTreeWidget.added_items.append(item)

    def topLevelItemCount(self) -> int:
        return len(_TrackedTreeWidget.added_items)

    def topLevelItem(self, index: int):
        if 0 <= index < len(_TrackedTreeWidget.added_items):
            return _TrackedTreeWidget.added_items[index]
        return None

    def indexOfTopLevelItem(self, item) -> int:
        try:
            return _TrackedTreeWidget.added_items.index(item)
        except ValueError:
            return -1

    def setCurrentItem(self, item):
        self._current_item = item

    def currentItem(self):
        return self._current_item

    def clear(self):
        _TrackedTreeWidget.added_items.clear()
        self._current_item = None

    @classmethod
    def reset(cls):
        cls.instances.clear()
        cls.added_items.clear()
        cls._item_changed_slots.clear()
        cls._item_double_clicked_slots.clear()

    @property
    def currentItemChanged(self):
        return _TreeItemsChangedSignal(_TrackedTreeWidget._item_changed_slots)

    @property
    def itemDoubleClicked(self):
        return _TreeItemsChangedSignal(_TrackedTreeWidget._item_double_clicked_slots)


class _TrackedLineEdit:
    """Stub for QLineEdit whose textChanged signal dispatches to connected
    slots, and whose keyPressEvent can be replaced by show_dialog().
    """

    instances: list = []
    text_changed_slots: list = []

    def __init__(self, *args, **kwargs):
        self._text = ""
        _TrackedLineEdit.instances.append(self)

    def setPlaceholderText(self, text):
        pass

    def setFocus(self):
        pass

    def setText(self, text):
        self._text = text
        for fn in _TrackedLineEdit.text_changed_slots:
            fn(text)

    def text(self) -> str:
        return self._text

    def keyPressEvent(self, event):
        """Handle key events when they propagate to the base class.

        This is called when show_dialog() sets search_box.keyPressEvent = _key_press
        and _key_press falls through to the base class handler for non-special keys.
        Escape is a special case - it should call dialog.reject() to mimic QDialog.
        """
        key = event.key()
        if key == _QT_KEY_ESCAPE and _TrackedDialog.instances:
            _TrackedDialog.instances[0].reject()

    @property
    def textChanged(self):
        return _TextChangedSignal(_TrackedLineEdit.text_changed_slots)

    @property
    def currentItemChanged(self):
        return _TextChangedSignal([])

    @property
    def itemDoubleClicked(self):
        return _TextChangedSignal([])

    @classmethod
    def reset(cls):
        cls.instances.clear()
        cls.text_changed_slots.clear()


class _TrackedTreeWidgetItem:
    """Stub for QTreeWidgetItem that preserves text and UserRole data."""

    def __init__(self, texts=None, *args, **kwargs):
        self._texts = list(texts or [])
        self._data = {}

    def setData(self, column, role, value):
        self._data[(column, role)] = value

    def data(self, column, role):
        return self._data.get((column, role))

    def text(self, column):
        return self._texts[column]


class _TrackedPushButton:
    """Stub for QPushButton whose clicked signal dispatches and whose click()
    triggers it.  Instances are tracked so tests can find Execute vs Close.
    """

    instances: list = []

    def __init__(self, text="", *args, **kwargs):
        self._text = text
        self._clicked_slots: list = []
        self.clicked = _ClickedSignal(self._clicked_slots)
        _TrackedPushButton.instances.append(self)

    def click(self):
        for fn in self._clicked_slots:
            fn()

    @classmethod
    def reset(cls):
        cls.instances.clear()


class _TrackedSplitter:
    instances: list = []

    def __init__(self, orientation=None, *args, **kwargs):
        _TrackedSplitter.instances.append(self)

    def addWidget(self, widget):
        pass

    def setSizes(self, sizes):
        pass

    @classmethod
    def reset(cls):
        cls.instances.clear()


class _TrackedLayout:
    instances: list = []

    def __init__(self, parent=None, *args, **kwargs):
        _TrackedLayout.instances.append(self)

    def addWidget(self, widget):
        pass

    def addLayout(self, layout):
        pass

    def addStretch(self):
        pass

    @classmethod
    def reset(cls):
        cls.instances.clear()


class _TrackedDialog:
    """Tracks the single QDialog instance created by show_dialog().  Its
    accept()/reject() are per-instance MagicMocks so each test gets a fresh
    call recorder.
    """

    instances: list = []

    def __init__(self, *args, **kwargs):
        self.accept = MagicMock()
        self.reject = MagicMock()
        _TrackedDialog.instances.append(self)

    def exec(self):
        pass

    def setWindowTitle(self, title):
        pass

    def setMinimumSize(self, w, h):
        pass

    def resize(self, w, h):
        pass

    def setFocus(self):
        pass

    @classmethod
    def reset(cls):
        cls.instances.clear()


# ---------------------------------------------------------------------------
# Helper: patch all Qt classes used by show_dialog() at once
# ---------------------------------------------------------------------------

# Patch targets: module.class -> stub class
_PATCH_TARGETS = [
    ("modules.command_search.QDialog", _TrackedDialog),
    ("modules.command_search.QTreeWidget", _TrackedTreeWidget),
    ("modules.command_search.QTreeWidgetItem", _TrackedTreeWidgetItem),
    ("modules.command_search.QLineEdit", _TrackedLineEdit),
    ("modules.command_search.QPushButton", _TrackedPushButton),
    ("modules.command_search.QSplitter", _TrackedSplitter),
    ("modules.command_search.QVBoxLayout", _TrackedLayout),
    ("modules.command_search.QHBoxLayout", _TrackedLayout),
]


@contextmanager
def _patch_all():
    """Context manager that patches all Qt widget classes used by
    show_dialog() with tracked stubs.  Also replaces Qt.Key with a
    namespace of distinct integers for reliable key comparison.
    """
    _TrackedTreeWidget.reset()
    _TrackedLineEdit.reset()
    _TrackedPushButton.reset()
    _TrackedSplitter.reset()
    _TrackedLayout.reset()
    _TrackedDialog.reset()

    with ExitStack() as stack:
        # First, patch all widget classes
        for target, stub in _PATCH_TARGETS:
            stack.enter_context(patch(target, stub))

        # Patch Qt.Key on the modules.command_search module
        # This must be done BEFORE importing CommandSearch
        import modules.command_search

        original_qt_key = getattr(modules.command_search, "Qt", None)
        if original_qt_key is not None:
            modules.command_search.Qt = _QtNamespace()

        # Keep Qt patched with test constants so key presses outside the
        # `with` block still compare against the stubbed constants.
        pass

        yield


# Import CommandSearch after our patches are defined, but before any test runs.
from modules.command_search import CommandSearch

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_populate_tree_with_non_empty_query(mock_services):
    """Typing a query into the search box populates the results tree with at
    at least one top-level item.
    """
    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        _TrackedLineEdit.instances[0].setText("Terminal")

    assert len(_TrackedTreeWidget.added_items) >= 1


def test_high_scoring_items_first(mock_services):
    """An exact label match appears before a longer partial match."""
    mock_services.get_all_commands.return_value = [
        {"group": "System", "label": "Terminal", "command": "gnome-terminal"},
        {
            "group": "System",
            "label": "Terminal Settings",
            "command": "terminal-settings",
        },
    ]

    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        _TrackedLineEdit.instances[0].setText("Terminal")

    assert len(_TrackedTreeWidget.added_items) == 2
    assert _TrackedTreeWidget.added_items[0].text(0) == "Terminal"
    assert _TrackedTreeWidget.added_items[1].text(0) == "Terminal Settings"


def test_enter_key_executes_selected_command(mock_services):
    """Pressing Enter on the search box calls services.execute() with the
    selected command's data and then accepts the dialog.
    """
    mock_services.get_all_commands.return_value = [
        {
            "group": "System",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": True,
            "showOutput": True,
            "prompt": "session name",
        },
    ]

    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        line_edit = _TrackedLineEdit.instances[0]
        tree = _TrackedTreeWidget.instances[0]
        dialog = _TrackedDialog.instances[0]

        # Populate with "Terminal".
        line_edit.setText("Terminal")

        # Select the first (Terminal) item.
        tree.setCurrentItem(_TrackedTreeWidget.added_items[0])

        # Simulate Enter key press.
        key_event = MagicMock()
        key_event.key.return_value = _QT_KEY_ENTER
        line_edit.keyPressEvent(key_event)

    mock_services.execute.assert_called_once_with(
        "Terminal",
        "gnome-terminal",
        True,
        True,
        "session name",
    )
    dialog.accept.assert_called_once()


def test_escape_key_hides_dialog(mock_services):
    """Pressing Escape on the search box calls dialog.reject() and does not
    call services.execute().
    """
    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        line_edit = _TrackedLineEdit.instances[0]
        dialog = _TrackedDialog.instances[0]

        key_event = MagicMock()
        key_event.key.return_value = _QT_KEY_ESCAPE
        line_edit.keyPressEvent(key_event)

    dialog.reject.assert_called_once()
    mock_services.execute.assert_not_called()


def test_close_button_rejects_dialog(mock_services):
    """Clicking the Close button calls dialog.reject() and does not call
    services.execute().
    """
    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        dialog = _TrackedDialog.instances[0]
        close_btn = _TrackedPushButton.instances[-1]  # Close is the second button.
        close_btn.click()

    dialog.reject.assert_called_once()
    mock_services.execute.assert_not_called()


def test_execute_button_calls_execute(mock_services):
    """Clicking the Execute button calls services.execute() with the currently
    selected tree item's command data and accepts the dialog.
    """
    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        execute_btn = _TrackedPushButton.instances[0]  # Execute is the first button.
        line_edit = _TrackedLineEdit.instances[0]
        tree = _TrackedTreeWidget.instances[0]
        dialog = _TrackedDialog.instances[0]

        # Populate and select.
        line_edit.setText("Terminal")
        tree.setCurrentItem(_TrackedTreeWidget.added_items[0])

        execute_btn.click()

    mock_services.execute.assert_called_once_with(
        "Terminal",
        "gnome-terminal",
        False,
        False,
        None,
    )
    dialog.accept.assert_called_once()


def test_empty_query_shows_all_commands(mock_services):
    """The initial _populate('') at dialog construction shows all 3 commands."""
    with _patch_all():
        CommandSearch(mock_services).show_dialog()

    assert len(_TrackedTreeWidget.added_items) == 3


def test_no_match_query_shows_empty_tree(mock_services):
    """A query with no plausible match leaves the results tree empty."""
    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        _TrackedLineEdit.instances[0].setText("zzzzzz")
    assert len(_TrackedTreeWidget.added_items) == 0
