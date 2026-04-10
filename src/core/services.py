#  SPDX-License-Identifier: GPL-3.0-or-later

"""
AppServices dataclass — thin service interface passed to all feature modules.

Decouples feature modules from the TrayApp god-object so they only depend
on the specific callables they actually need.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AppServices:
    """Thin service interface passed to all feature modules."""

    config_manager: Any
    execute: Callable
    reload_commands: Callable
    show_output: Callable
    get_all_commands: Callable
    save_commands: Callable
    reload_history_commands: Callable
    reload_favorites_commands: Callable
    resolve_icon_path: Callable
    resolve_command_reference: Callable
