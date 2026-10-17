# SPDX-License-Identifier: GPL-3.0-or-later
"""Own startup theme policy while delegating QSS operations to ThemeManager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.theme_manager import ThemeManager

if TYPE_CHECKING:
    from core.config_manager import ConfigManager


class ThemeController:
    """Initialize configured themes and expose the settings-dialog capability."""

    def __init__(
        self,
        base_dir: str,
        configuration: ConfigManager,
        theme_manager: ThemeManager | None = None,
    ) -> None:
        """Create a theme policy controller."""
        self.configuration = configuration
        self.theme_manager = theme_manager if theme_manager is not None else ThemeManager(base_dir)

    def initialize(self) -> None:
        """Apply the persisted theme, defaulting to the native system theme."""
        settings = self.configuration.get_settings()
        self.apply_theme(settings.get("theme", "system"))

    def apply_theme(self, theme: str) -> None:
        """Delegate a theme change to the QSS manager."""
        self.theme_manager.apply_theme(theme)
