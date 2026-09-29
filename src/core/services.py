# SPDX-License-Identifier: GPL-3.0-or-later

"""
AppServices dataclass — thin service interface passed to all feature modules.

Decouples feature modules from the TrayApp god-object so they only depend
on the specific callables they actually need.

The full dependency-injection contract — including a field-by-field reference,
consumption examples, and a step-by-step "Adding a new module" guide — is
documented in docs/architecture.md under "AppServices (Dependency Injection
Contract)".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config_manager import ConfigManager
    from core.process_tracker import ProcessTracker


@dataclass
class AppServices:
    """Thin service interface passed to all feature modules."""

    config_manager: ConfigManager  # Central config I/O: load/save commands, settings, history, favorites
    execute: Callable[[str, str, bool, bool, str | None], None]  # Execute command with confirmation, output, prompt
    reload_commands: Callable[..., None]  # Reload command menu from disk
    show_output: Callable[[str, str], None]  # Execute command and display output in RichOutputWindow
    get_all_commands: Callable[[], list]  # Flat list of all commands across groups
    save_commands: Callable[[dict], None]  # Persist command dictionary (with backup)
    reload_history_commands: Callable[[], None]  # Refresh Recent Commands submenu
    reload_favorites_commands: Callable[[], None]  # Refresh Favorites submenu
    resolve_icon_path: Callable[[str], str]  # Resolve logical icon path to filesystem path
    notify_user: Callable[[str, str], None]  # Show tray notification
    process_tracker: ProcessTracker  # Track running subprocesses, emit process_count_changed
