# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for startup theme policy and theme-manager delegation."""

from unittest.mock import MagicMock

from core.theme_controller import ThemeController


def test_initialize_applies_configured_theme():
    configuration = MagicMock()
    configuration.get_settings.return_value = {"theme": "dark"}
    manager = MagicMock()
    controller = ThemeController("/app", configuration, theme_manager=manager)

    controller.initialize()

    manager.apply_theme.assert_called_once_with("dark")
    assert controller.theme_manager is manager


def test_initialize_defaults_to_system_theme():
    configuration = MagicMock()
    configuration.get_settings.return_value = {}
    manager = MagicMock()
    controller = ThemeController("/app", configuration, theme_manager=manager)

    controller.initialize()

    manager.apply_theme.assert_called_once_with("system")


def test_apply_theme_delegates_to_theme_manager():
    controller = ThemeController("/app", MagicMock(), theme_manager=MagicMock())

    controller.apply_theme("light")

    controller.theme_manager.apply_theme.assert_called_once_with("light")
