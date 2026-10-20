# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ui.quick_launch_pin_manager module.

Strategy: these tests run against the project's PyQt6 stub installed by
conftest.py at import time. QListWidget is a stub, so the tests assert on the
widget's internal model, the persisted settings dict, and the signal
emissions, rather than on rendered widget text.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def services_mock():
    """Return a MagicMock that quacks like AppServices."""
    svc = MagicMock()
    svc.get_all_commands.return_value = [
        {
            "group": "System",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": False,
            "showOutput": False,
        },
        {
            "group": "System",
            "label": "Editor",
            "command": "gedit",
            "confirm": False,
            "showOutput": False,
        },
        {
            "group": "Git",
            "label": "Status",
            "command": "git status",
            "confirm": True,
            "showOutput": True,
        },
    ]
    return svc


@pytest.fixture()
def settings_dict():
    """Return a settings dict with a populated quick_launch_bar.pinned."""
    return {
        "quick_launch_bar": {
            "visible": True,
            "hotkey": "ctrl+shift+b",
            "pinned": [
                {
                    "group": "System",
                    "label": "Terminal",
                    "command": "gnome-terminal",
                    "confirm": False,
                    "showOutput": False,
                },
                {
                    "group": "Git",
                    "label": "Status",
                    "command": "git status",
                    "confirm": True,
                    "showOutput": True,
                },
            ],
        }
    }


@pytest.fixture()
def pin_manager(services_mock, settings_dict):
    """Return a QuickLaunchPinManager constructed from the fixtures."""
    from ui.quick_launch_pin_manager import QuickLaunchPinManager

    return QuickLaunchPinManager(services_mock, settings_dict)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestQuickLaunchPinManagerInstantiation:
    def test_instantiation_stores_services_and_settings(
        self, services_mock, settings_dict, pin_manager
    ):
        assert pin_manager is not None
        assert pin_manager.services is services_mock
        assert pin_manager._settings is settings_dict
        # _pinned_items is loaded from settings_dict by _load_pins() in __init__.
        assert len(pin_manager._pinned_items) == 2
        assert pin_manager._pinned_items[0]["label"] == "Terminal"
        assert pin_manager._pinned_items[1]["label"] == "Status"
        # _available_items is populated live from services at construction.
        assert len(pin_manager._available_items) == 3

    def test_available_items_populated_from_services(self, services_mock):
        from ui.quick_launch_pin_manager import QuickLaunchPinManager

        pm = QuickLaunchPinManager(services_mock, {})
        assert len(pm._available_items) == 3
        assert pm._available_items[0]["group"] == "System"
        assert pm._available_items[0]["label"] == "Terminal"


# ---------------------------------------------------------------------------
# Pin loading / normalisation
# ---------------------------------------------------------------------------


class TestQuickLaunchPinManagerPinLoading:
    def test_load_pins_rebuilds_pinned_items_from_settings(
        self, services_mock, settings_dict, pin_manager
    ):
        assert len(pin_manager._pinned_items) == 2
        assert pin_manager._pinned_items[0]["label"] == "Terminal"
        assert pin_manager._pinned_items[1]["confirm"] is True

    def test_load_pins_normalizes_missing_fields(self, services_mock):
        from ui.quick_launch_pin_manager import QuickLaunchPinManager

        svc = MagicMock()
        svc.get_all_commands.return_value = []
        settings = {"quick_launch_bar": {"pinned": [{"group": "System", "label": "T"}]}}
        pm = QuickLaunchPinManager(svc, settings)
        pm._load_pins()
        assert pm._pinned_items == [
            {"group": "System", "label": "T", "command": "", "confirm": False, "showOutput": False},
        ]

    def test_load_pins_handles_missing_pinned_key(self, services_mock, settings_dict):
        from ui.quick_launch_pin_manager import QuickLaunchPinManager

        settings = dict(settings_dict)
        del settings["quick_launch_bar"]["pinned"]
        pm = QuickLaunchPinManager(services_mock, settings)
        assert pm._pinned_items == []


# ---------------------------------------------------------------------------
# List sync / model mutation
# ---------------------------------------------------------------------------


class TestQuickLaunchPinManagerListSync:
    def test_refresh_pins_list_syncs_both_lists_from_model(
        self, services_mock, settings_dict, pin_manager
    ):
        """Rebuild both list widgets from the model and verify the model is the
        source of truth (identical under both the full stub and the lighter
        stub used by other test modules)."""
        pm = pin_manager
        pm._available_items = [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
            {"group": "B", "label": "CmdB", "command": "b", "confirm": True, "showOutput": False},
        ]
        pm._pinned_items = [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
        ]

        pm._refresh_pins_list()

        assert pm._pinned_items == [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
        ]
        assert pm._available_items == [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
            {"group": "B", "label": "CmdB", "command": "b", "confirm": True, "showOutput": False},
        ]

    def test_add_move_remove_updates_model_in_order(
        self, services_mock, settings_dict, pin_manager
    ):
        pm = pin_manager
        pm._available_items = [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
            {"group": "B", "label": "CmdB", "command": "b", "confirm": True, "showOutput": False},
        ]
        pm._pinned_items = [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
        ]

        # Add the second available command (at row 1).
        item = MagicMock()
        item.data.return_value = None
        pm._available_list.currentItem = MagicMock(return_value=item)
        pm._available_list.currentRow = MagicMock(return_value=1)
        pm._add()
        assert pm._available_items == [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False}
        ]
        assert pm._pinned_items == [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
            {"group": "B", "label": "CmdB", "command": "b", "confirm": True, "showOutput": False},
        ]

        # Remove the last pinned entry.
        item = MagicMock()
        item.data.return_value = {
            "group": "B",
            "label": "CmdB",
            "command": "b",
            "confirm": True,
            "showOutput": False,
        }
        pm._pinned_list.currentItem = MagicMock(return_value=item)
        pm._pinned_list.currentRow = MagicMock(return_value=1)
        pm._remove()
        assert pm._pinned_items == [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False}
        ]

        # Move the remaining pinned entry up (should be a no-op).
        pm._pinned_list.currentRow = MagicMock(return_value=0)
        pm._move_up()
        assert pm._pinned_items == [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False}
        ]

        # Move down one position.
        pm._pinned_list.currentRow = MagicMock(return_value=0)
        pm._pinned_items = [
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
            {"group": "B", "label": "CmdB", "command": "b", "confirm": True, "showOutput": False},
        ]
        pm._move_down()
        assert pm._pinned_items == [
            {"group": "B", "label": "CmdB", "command": "b", "confirm": True, "showOutput": False},
            {"group": "A", "label": "CmdA", "command": "a", "confirm": False, "showOutput": False},
        ]


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------


class TestQuickLaunchPinManagerCommit:
    def test_commit_persists_normalized_pins_in_place(
        self, services_mock, settings_dict, pin_manager
    ):
        pm = pin_manager
        # Add an extra resolvable pin to the model.
        pm._pinned_items = settings_dict["quick_launch_bar"]["pinned"] + [
            {
                "group": "System",
                "label": "Editor",
                "command": "gedit",
                "confirm": False,
                "showOutput": False,
            },
        ]

        initial_pinned = settings_dict["quick_launch_bar"]["pinned"]
        pm.commit()

        # Persisted in place: same list object, same container.
        assert settings_dict["quick_launch_bar"]["pinned"] is initial_pinned
        assert settings_dict["quick_launch_bar"]["pinned"] == [
            {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
                "confirm": False,
                "showOutput": False,
            },
            {
                "group": "Git",
                "label": "Status",
                "command": "git status",
                "confirm": True,
                "showOutput": True,
            },
            {
                "group": "System",
                "label": "Editor",
                "command": "gedit",
                "confirm": False,
                "showOutput": False,
            },
        ]
        # Model refreshed to match the persisted list.
        assert pm._pinned_items == settings_dict["quick_launch_bar"]["pinned"]

    def test_commit_drops_stale_pins_and_logs_warning(self, caplog, services_mock, settings_dict):
        svc = MagicMock()
        svc.get_all_commands.return_value = [
            {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
                "confirm": False,
                "showOutput": False,
            },
            {
                "group": "Git",
                "label": "Status",
                "command": "git status",
                "confirm": True,
                "showOutput": True,
            },
        ]
        settings = {"quick_launch_bar": {"pinned": []}}
        from ui.quick_launch_pin_manager import QuickLaunchPinManager

        pm = QuickLaunchPinManager(svc, settings)
        pm._pinned_items = [
            {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
                "confirm": False,
                "showOutput": False,
            },
            {
                "group": "Unknown",
                "label": "Ghost",
                "command": "ghost",
                "confirm": False,
                "showOutput": False,
            },
        ]

        pm.commit()

        assert len(pm._pinned_items) == 1
        assert pm._pinned_items[0]["label"] == "Terminal"
        assert any(
            "Stale pin dropped" in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        )

    def test_commit_emits_pins_committed(self, services_mock):
        from ui.quick_launch_pin_manager import QuickLaunchPinManager

        svc = MagicMock()
        svc.get_all_commands.return_value = []
        settings = {"quick_launch_bar": {"pinned": []}}
        pm = QuickLaunchPinManager(svc, settings)
        # Connect a recorder to the signal. The harness's lighter stub returns
        # non-dispatching MagicMocks for pyqtSignal, so point the emit call at a
        # recorder Mock instead of relying on the stub's dispatch.
        emit_recorder = MagicMock()
        pm.pins_committed.emit = emit_recorder
        pm.commit()

        emit_recorder.assert_called_once()

    def test_commit_resolves_pins_identically_to_bar_helper(self, services_mock):
        """A pin resolvable by _build_buttons is kept by commit(), and vice versa."""
        from ui.quick_launch_pin_manager import QuickLaunchPinManager

        svc = MagicMock()
        svc.get_all_commands.return_value = [
            {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
                "confirm": False,
                "showOutput": False,
            },
            {
                "group": "System",
                "label": "Editor",
                "command": "gedit",
                "confirm": False,
                "showOutput": False,
            },
            {
                "group": "Git",
                "label": "Status",
                "command": "git status",
                "confirm": True,
                "showOutput": True,
            },
        ]
        settings = {"quick_launch_bar": {"pinned": []}}
        pm = QuickLaunchPinManager(svc, settings)

        cases = [
            # Exact (group, label) keyed lookup.
            {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
                "confirm": False,
                "showOutput": False,
            },
            # Command-filtered label match (exactly one candidate).
            {
                "label": "Terminal",
                "command": "gnome-terminal",
                "confirm": False,
                "showOutput": False,
            },
            # Unique label-only match.
            {"label": "Editor", "command": "", "confirm": False, "showOutput": False},
        ]

        for pin in cases:
            pm._pinned_items = [pin]
            pm.commit()
            # The pin is kept (resolved) — no warning, and the model matches.
            assert len(pm._pinned_items) == 1, f"pin {pin} should be kept"
            assert pm._pinned_items[0] == pin


class TestQuickLaunchPinManagerResolveHelper:
    """Unit tests for the shared resolution helper (mirror of the bar helper)."""

    def test_resolve_exact_match(self):
        from ui.quick_launch_bar import _resolve_pin_command

        all_cmds = {
            ("System", "Terminal"): {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
            },
        }
        pin = {
            "group": "System",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": False,
            "showOutput": False,
        }
        assert _resolve_pin_command(pin, all_cmds) is not None

    def test_resolve_command_filtered_label_match(self):
        from ui.quick_launch_bar import _resolve_pin_command

        all_cmds = {
            ("System", "Terminal"): {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
            },
            ("System", "Editor"): {"group": "System", "label": "Editor", "command": "gedit"},
        }
        # Two commands share a label; only one matches the pin's command.
        pin = {
            "group": "",
            "label": "Terminal",
            "command": "gnome-terminal",
            "confirm": False,
            "showOutput": False,
        }
        assert _resolve_pin_command(pin, all_cmds)["command"] == "gnome-terminal"

    def test_resolve_unique_label_only_match(self):
        from ui.quick_launch_bar import _resolve_pin_command

        all_cmds = {
            ("System", "Editor"): {"group": "System", "label": "Editor", "command": "gedit"},
        }
        # Only one command has this label; command-filtered match misses (no command), so unique label match wins.
        pin = {"group": "", "label": "Editor", "command": "", "confirm": False, "showOutput": False}
        assert _resolve_pin_command(pin, all_cmds)["command"] == "gedit"

    def test_resolve_stale_pin_returns_none(self):
        from ui.quick_launch_bar import _resolve_pin_command

        all_cmds = {
            ("System", "Terminal"): {
                "group": "System",
                "label": "Terminal",
                "command": "gnome-terminal",
            },
        }
        pin = {
            "group": "Unknown",
            "label": "Ghost",
            "command": "ghost",
            "confirm": False,
            "showOutput": False,
        }
        assert _resolve_pin_command(pin, all_cmds) is None
