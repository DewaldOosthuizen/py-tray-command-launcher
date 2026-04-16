# SPDX-License-Identifier: GPL-3.0-or-later

"""
CommandSearch — fuzzy command search dialog.

Uses ``rapidfuzz.fuzz.WRatio`` for scoring.  Falls back to exact
substring search with a log warning when rapidfuzz is unavailable.

Keyboard navigation:
  • Arrow keys move selection in the results tree
  • Enter  → execute selected command and close
  • Escape → close without executing
"""

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz as _fuzz
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False
    logger.warning(
        "rapidfuzz not available; falling back to substring search in CommandSearch"
    )


def _score(query: str, text: str) -> float:
    """Return a match score 0–100 for *query* against *text*."""
    if _FUZZY_AVAILABLE:
        return _fuzz.WRatio(query, text)
    return 100.0 if query.lower() in text.lower() else 0.0


class CommandSearch:
    """Provides fuzzy search functionality for commands."""

    def __init__(self, services):
        """Initialize with an AppServices instance."""
        self.services = services

    def show_dialog(self):
        """Show the command search dialog."""
        dialog = QDialog()
        dialog.setWindowTitle("Search Commands")
        dialog.setMinimumSize(600, 420)
        layout = QVBoxLayout(dialog)

        search_box = QLineEdit()
        search_box.setPlaceholderText("Type to search commands…")
        layout.addWidget(search_box)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Results tree (name, group, command columns)
        results_tree = QTreeWidget()
        results_tree.setColumnCount(3)
        results_tree.setHeaderLabels(["Name", "Group", "Command"])
        results_tree.header().setStretchLastSection(True)
        results_tree.setAlternatingRowColors(True)
        splitter.addWidget(results_tree)

        # Preview pane
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setPlaceholderText("Command preview…")
        preview.setMaximumHeight(80)
        splitter.addWidget(preview)

        splitter.setSizes([300, 80])
        layout.addWidget(splitter)

        # Button row
        btn_row = QHBoxLayout()
        execute_btn = QPushButton("Execute")
        close_btn = QPushButton("Close")
        btn_row.addStretch()
        btn_row.addWidget(execute_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        all_commands = self.services.get_all_commands()

        def _populate(query: str):
            results_tree.clear()
            if not query.strip():
                scored = [(100, cmd) for cmd in all_commands]
            else:
                scored = []
                for cmd in all_commands:
                    text = f"{cmd['group']} {cmd['label']}"
                    s = _score(query, text)
                    if s > 30 or query.lower() in text.lower():
                        scored.append((s, cmd))
                scored.sort(key=lambda x: x[0], reverse=True)

            for _s, cmd in scored:
                item = QTreeWidgetItem([
                    cmd["label"],
                    cmd["group"],
                    cmd.get("command", ""),
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, cmd)
                results_tree.addTopLevelItem(item)

            if results_tree.topLevelItemCount() > 0:
                results_tree.setCurrentItem(results_tree.topLevelItem(0))

        def _update_preview():
            item = results_tree.currentItem()
            if item:
                cmd = item.data(0, Qt.ItemDataRole.UserRole) or {}
                preview.setPlainText(cmd.get("command", ""))

        def _execute():
            item = results_tree.currentItem()
            if not item:
                return
            cmd_info = item.data(0, Qt.ItemDataRole.UserRole)
            if not cmd_info:
                return
            self.services.execute(
                cmd_info["label"],
                cmd_info["command"],
                cmd_info.get("confirm", False),
                cmd_info.get("showOutput", False),
                cmd_info.get("prompt"),
            )
            dialog.accept()

        search_box.textChanged.connect(_populate)
        results_tree.currentItemChanged.connect(lambda *_: _update_preview())
        results_tree.itemDoubleClicked.connect(lambda *_: _execute())
        execute_btn.clicked.connect(_execute)
        close_btn.clicked.connect(dialog.reject)

        # Keyboard: Enter executes, arrows navigate tree
        def _key_press(event):
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                _execute()
            elif key == Qt.Key.Key_Down:
                results_tree.setFocus()
                current = results_tree.currentItem()
                if current:
                    idx = results_tree.indexOfTopLevelItem(current)
                    nxt = results_tree.topLevelItem(idx + 1)
                    if nxt:
                        results_tree.setCurrentItem(nxt)
            elif key == Qt.Key.Key_Up:
                results_tree.setFocus()
                current = results_tree.currentItem()
                if current:
                    idx = results_tree.indexOfTopLevelItem(current)
                    if idx > 0:
                        results_tree.setCurrentItem(results_tree.topLevelItem(idx - 1))
            else:
                QLineEdit.keyPressEvent(search_box, event)

        search_box.keyPressEvent = _key_press

        _populate("")
        search_box.setFocus()
        dialog.resize(640, 460)
        dialog.exec()
