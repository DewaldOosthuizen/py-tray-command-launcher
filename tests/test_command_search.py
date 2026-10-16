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

import pytest

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
        """Stand in for the base handler used by non-special key events."""

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

        stack.enter_context(patch.object(modules.command_search, "Qt", _QtNamespace()))

        yield


# Import CommandSearch after our patches are defined, but before any test runs.
from modules.command_search import (
    COMMAND_SEARCH_CACHE_SIZE,
    CommandSearch,
    _score,
    clear_command_search_cache,
    command_search_cache_info,
    search_commands,
    search_commands_uncached,
)


def test_exact_match_scores_high():
    score = _score("Terminal", "Terminal")
    assert score >= 90


def test_partial_match_returns_nonzero():
    score = _score("term", "Terminal")
    assert score > 0


def test_empty_query_gives_positive_score():
    # An empty string substring matches every string
    score = _score("", "anything")
    assert score >= 0  # Must not raise; score value depends on backend


def test_no_match_scores_low():
    score = _score("zzzzunlikely", "Terminal")
    # rapidfuzz may still return a small partial score; without it score is 0
    assert score < 90


def test_special_characters_do_not_raise():
    try:
        _score("!@#$%^&*()", "some command --flag=value")
    except Exception as exc:
        pytest.fail(f"_score raised unexpectedly: {exc}")


def test_score_is_symmetric_ish():
    s1 = _score("git", "Git Status")
    s2 = _score("Git Status", "git")
    assert s1 > 0 and s2 > 0


def test_cached_search_matches_uncached_for_query_variants():
    commands = [
        {"group": "System", "label": "Terminal", "command": "terminal-v1"},
        {"group": "System", "label": "Terminal Settings", "command": "settings"},
        {"group": "Git", "label": "Status", "command": "git status"},
    ]

    for query in ("terminal", "TERMINAL", " terminal", "term set", "", "zzzzunlikely"):
        assert search_commands(query, commands) == search_commands_uncached(query, commands)


def test_search_preserves_raw_query_case_sensitive_ranking_and_cache_keys():
    commands = [
        {"group": "System", "label": "Terminal", "command": "system-terminal"},
        {
            "group": "Development",
            "label": "terminal",
            "command": "development-terminal",
        },
    ]

    raw_scores = {
        ("Terminal", "System Terminal"): 90,
        ("Terminal", "Development terminal"): 84,
        ("terminal", "System Terminal"): 84,
        ("terminal", "Development terminal"): 90,
    }

    def prior_raw_query_score(query, text):
        return raw_scores[(query, text)]

    for query, expected_labels in (
        ("Terminal", ["Terminal", "terminal"]),
        ("terminal", ["terminal", "Terminal"]),
    ):
        expected = [
            (prior_raw_query_score(query, f"{command['group']} {command['label']}"), command)
            for command in commands
        ]
        expected.sort(key=lambda result: result[0], reverse=True)
        assert [command["label"] for _, command in expected] == expected_labels

        with patch("modules.command_search._score", side_effect=prior_raw_query_score):
            assert search_commands_uncached(query, commands) == expected
            assert search_commands(query, commands) == expected

    clear_command_search_cache()
    with patch("modules.command_search._score", side_effect=prior_raw_query_score):
        search_commands("Terminal", commands)
        search_commands("terminal", commands)
    assert command_search_cache_info().misses == 2


def test_search_cache_does_not_merge_case_distinct_queries():
    commands = [{"group": "System", "label": "Terminal", "command": "terminal"}]
    clear_command_search_cache()

    search_commands("terminal", commands)
    first_info = command_search_cache_info()
    search_commands("TERMINAL", commands)
    second_info = command_search_cache_info()

    assert second_info.misses == first_info.misses + 1


def test_search_cache_does_not_merge_queries_with_distinct_whitespace():
    commands = [{"group": "System", "label": "Terminal", "command": "terminal"}]
    clear_command_search_cache()

    search_commands("terminal", commands)
    before_whitespace_variant = command_search_cache_info()
    search_commands(" terminal", commands)
    after_whitespace_variant = command_search_cache_info()

    assert after_whitespace_variant.misses == before_whitespace_variant.misses + 1


def test_whitespace_only_query_shows_all_commands():
    commands = [
        {"group": "System", "label": "Terminal", "command": "terminal"},
        {"group": "Development", "label": "Editor", "command": "editor"},
    ]
    expected = [(100, command) for command in commands]
    clear_command_search_cache()

    with patch("modules.command_search._score", return_value=0):
        assert search_commands_uncached("  \t", commands) == expected
        assert search_commands("  \t", commands) == expected


def test_cached_results_use_current_payload_and_distinguish_searchable_snapshots():
    original = [{"group": "System", "label": "Terminal", "command": "old"}]
    updated = [{"group": "System", "label": "Terminal", "command": "new"}]
    renamed = [{"group": "System", "label": "Console", "command": "new"}]
    clear_command_search_cache()

    assert search_commands("terminal", original)[0][1] is original[0]
    assert search_commands("terminal", updated)[0][1] is updated[0]
    before_renamed_search = command_search_cache_info()
    renamed_results = search_commands("terminal", renamed)
    after_renamed_search = command_search_cache_info()

    assert renamed_results
    assert all(command is renamed[0] for _, command in renamed_results)
    assert after_renamed_search.misses == before_renamed_search.misses + 1


def test_search_cache_is_bounded_and_evicts_least_recently_used():
    commands = [{"group": "System", "label": "Terminal", "command": "terminal"}]
    clear_command_search_cache()
    search_commands("first", commands)
    search_commands("second", commands)
    search_commands("first", commands)
    for index in range(COMMAND_SEARCH_CACHE_SIZE - 1):
        search_commands(f"query-{index}", commands)

    before = command_search_cache_info()
    search_commands("first", commands)
    after = command_search_cache_info()

    assert before.currsize == COMMAND_SEARCH_CACHE_SIZE
    assert after.currsize <= COMMAND_SEARCH_CACHE_SIZE
    assert after.hits == before.hits + 1

    search_commands("second", commands)
    assert command_search_cache_info().misses == after.misses + 1


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
    """Higher-scoring results are sorted ahead of earlier lower-scoring ones."""
    mock_services.get_all_commands.return_value = [
        {
            "group": "System",
            "label": "Terminal Settings",
            "command": "terminal-settings",
        },
        {"group": "System", "label": "Terminal", "command": "gnome-terminal"},
    ]

    with (
        _patch_all(),
        patch(
            "modules.command_search._score",
            side_effect=lambda _query, text: 100 if text == "System Terminal" else 50,
        ),
    ):
        CommandSearch(mock_services).show_dialog()
        _TrackedLineEdit.instances[0].setText("Terminal")

    assert len(_TrackedTreeWidget.added_items) == 2
    assert _TrackedTreeWidget.added_items[0].text(0) == "Terminal"
    assert _TrackedTreeWidget.added_items[1].text(0) == "Terminal Settings"


def test_dialog_repeated_query_uses_cached_scores(mock_services):
    commands = [
        {"group": "System", "label": "Terminal", "command": "terminal"},
        {"group": "System", "label": "Terminal Settings", "command": "settings"},
    ]
    mock_services.get_all_commands.return_value = commands
    clear_command_search_cache()

    with (
        _patch_all(),
        patch("modules.command_search._score", wraps=_score) as scoring,
    ):
        CommandSearch(mock_services).show_dialog()
        line_edit = _TrackedLineEdit.instances[0]
        line_edit.setText("Terminal")
        initial_score_calls = scoring.call_count
        first_info = command_search_cache_info()
        line_edit.setText("Terminal")
        second_info = command_search_cache_info()

    assert scoring.call_count == initial_score_calls
    assert second_info.hits == first_info.hits + 1


def test_open_dialog_uses_replaced_command_snapshot(mock_services):
    original = [{"group": "System", "label": "Terminal", "command": "old"}]
    replacement = [
        {"group": "Tools", "label": "Console", "command": "new"},
        {"group": "Tools", "label": "New Entry", "command": "new-entry"},
    ]
    mock_services.get_all_commands.return_value = original
    clear_command_search_cache()

    with _patch_all():
        CommandSearch(mock_services).show_dialog()
        line_edit = _TrackedLineEdit.instances[0]
        line_edit.setText("terminal")
        mock_services.get_all_commands.return_value = replacement
        line_edit.setText("")
        rendered_commands = [
            item.data(0, _QtNamespace.ItemDataRole.UserRole)
            for item in _TrackedTreeWidget.added_items
        ]

    assert rendered_commands == replacement


def test_dialog_uses_rebuilt_configuration_for_added_edited_removed_and_renamed_commands(
    mock_services,
):
    from core.menu_builder import MenuBuilder

    original = [
        {"group": "System", "label": "EditableEntry", "command": "old-command"},
        {"group": "System", "label": "RemoveObsoleteFeature", "command": "obsolete"},
        {"group": "System", "label": "OldScarletCommand", "command": "old-name"},
    ]
    replacement = [
        {"group": "Tools", "label": "EditableEntry", "command": "edited-command"},
        {"group": "Tools", "label": "BrandNewFeature", "command": "added-command"},
        {"group": "Tools", "label": "NewVioletCommand", "command": "renamed-command"},
    ]
    mock_services.get_all_commands.return_value = original
    clear_command_search_cache()

    tray_app = MagicMock()
    tray_app.icon_file = "/nonexistent/tray_icon.png"
    tray_app.command_menu = {}
    tray_menu = MagicMock()

    with _patch_all(), patch("core.menu_builder.QMenu", return_value=MagicMock()):
        CommandSearch(mock_services).show_dialog()
        line_edit = _TrackedLineEdit.instances[0]
        assert [
            item.data(0, _QtNamespace.ItemDataRole.UserRole)
            for item in _TrackedTreeWidget.added_items
        ] == original

        tray_app.command_menu = {
            "Tools": {command["label"]: {"command": command["command"]} for command in replacement}
        }
        mock_services.get_all_commands.return_value = replacement
        MenuBuilder(tray_app).build(tray_menu, tray_app.command_menu)

        line_edit.setText("")
        rendered_commands = [
            item.data(0, _QtNamespace.ItemDataRole.UserRole)
            for item in _TrackedTreeWidget.added_items
        ]
        line_edit.setText("EditableEntry")
        edited_results = [
            item.data(0, _QtNamespace.ItemDataRole.UserRole)
            for item in _TrackedTreeWidget.added_items
        ]
        line_edit.setText("BrandNewFeature")
        added_results = [
            item.data(0, _QtNamespace.ItemDataRole.UserRole)
            for item in _TrackedTreeWidget.added_items
        ]
        line_edit.setText("NewVioletCommand")
        renamed_results = [
            item.data(0, _QtNamespace.ItemDataRole.UserRole)
            for item in _TrackedTreeWidget.added_items
        ]

    assert rendered_commands == replacement
    assert all(
        command["label"] not in {"RemoveObsoleteFeature", "OldScarletCommand"}
        for command in rendered_commands
    )
    assert replacement[0] in edited_results
    assert (
        next(command for command in edited_results if command["label"] == "EditableEntry")[
            "command"
        ]
        == "edited-command"
    )
    assert replacement[1] in added_results
    assert replacement[2] in renamed_results


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


def test_patch_all_restores_module_qt_namespace():
    """The helper must not leak test-only Qt constants into other tests."""
    import modules.command_search as command_search_module

    original_qt = command_search_module.Qt

    with _patch_all():
        assert command_search_module.Qt is not original_qt

    assert command_search_module.Qt is original_qt
