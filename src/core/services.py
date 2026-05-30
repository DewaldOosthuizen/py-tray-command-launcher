# SPDX-License-Identifier: GPL-3.0-or-later

"""
AppServices dataclass — thin service interface passed to all feature modules.

Decouples feature modules from the TrayApp god-object so they only depend
on the specific callables they actually need.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config_manager import ConfigManager


@dataclass
class AppServices:
    """Thin service interface passed to all feature modules."""

    config_manager: ConfigManager
    execute: Callable[[str, str, bool, bool, str | None], None]
    reload_commands: Callable[..., None]
    show_output: Callable[[str, str], None]
    get_all_commands: Callable[[], list]
    save_commands: Callable[[dict], None]
    reload_history_commands: Callable[[], None]
    reload_favorites_commands: Callable[[], None]
    resolve_icon_path: Callable[[str], str]
    notify_user: Callable[[str, str], None]
