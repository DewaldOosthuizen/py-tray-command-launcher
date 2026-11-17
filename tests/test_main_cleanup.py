# SPDX-License-Identifier: GPL-3.0-or-later
"""Shutdown routing regression tests for the application entry point."""

from unittest.mock import MagicMock

from main import _cleanup_application


def test_cleanup_routes_through_tray_app_when_it_exists():
    tray_app = MagicMock()
    instance_checker = MagicMock()

    _cleanup_application(tray_app, instance_checker)

    tray_app.cleanup.assert_called_once_with()
    instance_checker.cleanup.assert_not_called()


def test_cleanup_uses_instance_checker_before_tray_app_exists():
    instance_checker = MagicMock()

    _cleanup_application(None, instance_checker)

    instance_checker.cleanup.assert_called_once_with()
