# SPDX-License-Identifier: GPL-3.0-or-later
"""
QuickLaunchPinManager — GUI widget for curating the Quick-Launch Bar pins.

Provides Add >>, Remove, Move Up, and Move Down controls so the user can choose
which commands appear on the Quick-Launch Bar, without hand-editing
``settings.json``.

Pins are stored as a list of full ``{group, label, command, confirm, showOutput}``
dicts in ``self._settings['quick_launch_bar']['pinned']``. ``commit()`` resolves
each pin against the known command set, drops any that no longer resolve (logging
a warning per stale pin), persists the remaining pins through an in-place slice
assignment on the settings list, refreshes the widget's own lists, and emits
``pins_committed`` so the parent dialog can refresh the visible bar.

The resolution algorithm is shared with ``QuickLaunchBar._resolve_pin_command``
in ``src/ui/quick_launch_bar.py`` so the widget and the bar keep pins identically.
"""

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.quick_launch_bar import _resolve_pin_command

logger = logging.getLogger(__name__)


class QuickLaunchPinManager(QWidget):
    """Widget for managing the Quick-Launch Bar pinned command list.

    Parameters
    ----------
    services:
        AppServices mock/instance providing ``get_all_commands()``.
    settings:
        The same settings dict that the parent dialog will persist via
        ``config_manager.save_settings()``. The manager mutates it in place so
        that the bar and the saved file stay in sync.
    bar_refresh_callback:
        Optional callable invoked after a successful ``commit()`` so a parent
        component can refresh the visible bar. The SettingsDialog instead wires
        ``pins_committed`` to ``QuickLaunchBar.refresh()``.
    """

    pins_committed = pyqtSignal()

    def __init__(
        self,
        services,
        settings,
        bar_refresh_callback=None,
    ) -> None:
        super().__init__()
        self.services = services
        self._settings = settings
        self._bar_refresh_callback = bar_refresh_callback

        # Ordered model: full {group, label, command, confirm, showOutput} dicts.
        self._pinned_items: list[dict] = []
        # List of available command dicts (live from services).
        self._available_items: list[dict] = self._gather_available_commands()

        # Widget state — each row stores its command dict in UserRole.
        self._available_list = QListWidget()
        self._pinned_list = QListWidget()

        # Control buttons (Add >>, Remove, Move Up, Move Down).
        self._btn_add = QPushButton("Add >>")
        self._btn_remove = QPushButton("Remove")
        self._btn_move_up = QPushButton("Move Up")
        self._btn_move_down = QPushButton("Move Down")

        self._setup_ui()
        self._load_pins()

    # ------------------------------------------------------------------
    # Model loading / normalisation
    # ------------------------------------------------------------------

    def _gather_available_commands(self):
        """Return a copy of the command list straight from services."""
        return list(self.services.get_all_commands())

    # ------------------------------------------------------------------
    # Layout / wiring
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Wire buttons and build the vertical layout."""

        self._btn_add.clicked.connect(self._add)
        self._btn_remove.clicked.connect(self._remove)
        self._btn_move_up.clicked.connect(self._move_up)
        self._btn_move_down.clicked.connect(self._move_down)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        main_layout.addWidget(self._available_list)

        button_row = QVBoxLayout()
        button_row.addWidget(self._btn_add)
        button_row.addWidget(self._btn_remove)
        button_row.addWidget(self._btn_move_up)
        button_row.addWidget(self._btn_move_down)
        main_layout.addLayout(button_row)

        main_layout.addWidget(self._pinned_list)

    # ------------------------------------------------------------------
    # Model loading / normalisation
    # ------------------------------------------------------------------

    def _load_pins(self) -> None:
        """Rebuild ``_pinned_items`` from ``self._settings['quick_launch_bar']``."""

        qlb_cfg = self._settings.get("quick_launch_bar", {})
        if not isinstance(qlb_cfg, dict):
            qlb_cfg = {}
        pinned = qlb_cfg.get("pinned", [])
        if not isinstance(pinned, list):
            pinned = []
        # Normalise every stored pin up front so the model is always canonical.
        self._pinned_items = [self._normalize_pin(p) for p in pinned]

    def _normalize_pin(self, pin):
        """Return a canonical {group, label, command, confirm, showOutput} dict."""

        if not isinstance(pin, dict):
            return {
                "group": "",
                "label": "",
                "command": "",
                "confirm": False,
                "showOutput": False,
            }
        return {
            "group": pin.get("group", ""),
            "label": pin.get("label", ""),
            "command": pin.get("command", ""),
            "confirm": bool(pin.get("confirm", False)),
            "showOutput": bool(pin.get("showOutput", False)),
        }

    # ------------------------------------------------------------------
    # List sync / model mutation
    # ------------------------------------------------------------------

    def _refresh_pins_list(self) -> None:
        """Sync both QListWidgets from the model.

        Every row stores its command dict in ``ItemDataRole.UserRole`` so that
        add/remove/move act on the model dicts, never on widget text.
        """

        self._available_list.clear()
        for cmd in self._available_items:
            item = QListWidgetItem(cmd["label"])
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self._available_list.addItem(item)

        self._pinned_list.clear()
        for pin in self._pinned_items:
            item = QListWidgetItem(pin["label"])
            item.setData(Qt.ItemDataRole.UserRole, pin)
            self._pinned_list.addItem(item)

    # ------------------------------------------------------------------
    # Button actions
    # ------------------------------------------------------------------

    def _add(self) -> None:
        """Move the currently selected available command into the pinned list."""

        current = self._available_list.currentItem()
        if current is None:
            return
        cmd = current.data(Qt.ItemDataRole.UserRole)
        if cmd is None:
            row = self._available_list.currentRow()
            if row < 0:
                return
            cmd = self._available_items[row]
        self._available_items.remove(cmd)
        self._pinned_items.append(cmd)
        self._refresh_pins_list()

    def _remove(self) -> None:
        """Remove the currently selected pinned command."""

        current = self._pinned_list.currentItem()
        if current is None:
            return
        pin = current.data(Qt.ItemDataRole.UserRole)
        if pin is None:
            row = self._pinned_list.currentRow()
            if row < 0:
                return
            pin = self._pinned_items[row]
        self._pinned_items.remove(pin)
        self._refresh_pins_list()

    def _move_up(self) -> None:
        """Swap the currently selected pinned command one position up."""

        row = self._pinned_list.currentRow()
        if row <= 0:
            return
        self._pinned_items[row], self._pinned_items[row - 1] = (
            self._pinned_items[row - 1],
            self._pinned_items[row],
        )
        self._refresh_pins_list()

    def _move_down(self) -> None:
        """Swap the currently selected pinned command one position down."""

        row = self._pinned_list.currentRow()
        if row < 0 or row >= len(self._pinned_items) - 1:
            return
        self._pinned_items[row], self._pinned_items[row + 1] = (
            self._pinned_items[row + 1],
            self._pinned_items[row],
        )
        self._refresh_pins_list()

    # ------------------------------------------------------------------
    # Commit
    # ------------------------------------------------------------------

    def commit(self) -> None:
        """Resolve each pin, drop any whose command no longer resolves, persist
        the remaining normalised pins in place into the settings dict, refresh
        the widget's own lists, and emit ``pins_committed``.

        ``self._settings['quick_launch_bar']['pinned'][:] = normalized`` keeps
        the same list object alive, so the caller's dict reflects the change
        without creating a new list reference.
        """

        all_cmds = {(c["group"], c["label"]): c for c in self.services.get_all_commands()}
        normalized = []
        for pin in self._pinned_items:
            if _resolve_pin_command(pin, all_cmds) is None:
                logger.warning(
                    "Stale pin dropped: %s / %s",
                    pin.get("group", ""),
                    pin.get("label", ""),
                )
                continue
            normalized.append(pin)

        # Drop stale pins from the model, then persist the resolved pins into
        # the settings dict in place (same list object).
        self._pinned_items = normalized

        qlb_cfg = self._settings.get("quick_launch_bar")
        if not isinstance(qlb_cfg, dict):
            qlb_cfg = {}
            self._settings["quick_launch_bar"] = qlb_cfg
        pinned = qlb_cfg.get("pinned")
        if not isinstance(pinned, list):
            pinned = []
            qlb_cfg["pinned"] = pinned
        pinned[:] = normalized

        self._refresh_pins_list()
        self.pins_committed.emit()
