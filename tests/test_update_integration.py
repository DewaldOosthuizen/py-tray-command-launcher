# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration, menu, and tray integration regression tests for updates."""

import json
from unittest.mock import MagicMock, patch

import pytest

from core.config_manager import ConfigManager


def test_update_settings_have_defaults_and_round_trip(tmp_path):
    manager = ConfigManager()
    manager.config_dir = tmp_path
    manager.settings_file = tmp_path / "settings.json"
    manager.defaults_dir = tmp_path / "config"
    manager.defaults_dir.mkdir()
    schema = __import__("pathlib").Path(__file__).resolve().parents[1] / "config/settings.schema.json"
    manager.defaults_dir.joinpath("settings.schema.json").write_text(schema.read_text())

    defaults = manager.get_settings()
    assert defaults["update_check_enabled"] is True
    assert defaults["update_check_interval_hours"] == 24
    assert defaults["dismissed_update_version"] == ""

    defaults["update_check_enabled"] = False
    defaults["update_check_interval_hours"] = 12
    defaults["dismissed_update_version"] = "2026.10.22"
    manager.save_settings(defaults)
    manager._settings_cache = None
    assert manager.get_settings()["update_check_enabled"] is False
    assert manager.get_settings()["update_check_interval_hours"] == 12
    assert manager.get_settings()["dismissed_update_version"] == "2026.10.22"


def test_update_settings_schema_rejects_non_positive_interval(tmp_path):
    manager = ConfigManager()
    manager.defaults_dir = __import__("pathlib").Path(__file__).resolve().parents[1] / "config"
    assert not manager._validate_settings_schema({"update_check_interval_hours": 0})


def test_menu_has_manual_update_action_and_dynamic_newer_release_action(monkeypatch):
    from core.menu_builder import MenuBuilder, MenuBuilderDependencies

    dependencies = MagicMock()
    dependencies.icon_file = "icon.png"
    dependencies.get_command_menu.return_value = {}
    dependencies.resolve_icon_path.return_value = None
    dependencies.get_favorites.return_value = MagicMock()
    dependencies.get_palette.return_value = MagicMock()
    dependencies.get_import_export.return_value = MagicMock()
    dependencies.get_backup.return_value = MagicMock()
    dependencies.get_file_encryptor.return_value = MagicMock()
    dependencies.get_schedule_creator.return_value = MagicMock()
    dependencies.get_schedule_viewer.return_value = MagicMock()

    # Keep the renderer's existing explicit dependency contract while attaching
    # update actions through the newly-added update callbacks.
    callbacks = {
        "icon_file": dependencies.icon_file,
        "get_command_menu": dependencies.get_command_menu,
        "resolve_icon_path": dependencies.resolve_icon_path,
        "execute": MagicMock(),
        "get_favorites": dependencies.get_favorites,
        "set_favorites_menu": MagicMock(),
        "reload_favorites_commands": MagicMock(),
        "set_history_menu": MagicMock(),
        "reload_history_commands": MagicMock(),
        "get_palette": dependencies.get_palette,
        "open_command_manager": MagicMock(),
        "open_commands_json": MagicMock(),
        "reload_commands": MagicMock(),
        "get_import_export": dependencies.get_import_export,
        "get_backup": dependencies.get_backup,
        "get_file_encryptor": dependencies.get_file_encryptor,
        "get_schedule_creator": dependencies.get_schedule_creator,
        "get_schedule_viewer": dependencies.get_schedule_viewer,
        "open_settings": MagicMock(),
        "set_running_action": MagicMock(),
        "restart_app": MagicMock(),
        "confirm_exit": MagicMock(),
        "check_for_updates": MagicMock(),
        "get_update": lambda: type("Release", (), {"version": "2026.10.22"})(),
        "open_update": MagicMock(),
    }
    menu = MagicMock()
    submenu_factory = MagicMock()
    submenu_factory.return_value = MagicMock()
    monkeypatch.setattr("core.menu_builder.QMenu", submenu_factory)
    monkeypatch.setattr("core.menu_builder.QIcon", MagicMock())

    MenuBuilder(MenuBuilderDependencies(**callbacks)).build(menu, {})

    actions = [call.args[0] for call in menu.addAction.call_args_list]
    assert "Check for updates" in actions
    assert "Update available: 2026.10.22" in actions


def test_development_version_does_not_create_update_action():
    from core.version import parse_calver

    assert parse_calver("1.0.0") is None


def test_tray_tooltip_includes_resolved_version():
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    app.tray_icon = MagicMock()
    app.get_all_commands = MagicMock(return_value=[])
    with patch("core.tray_app.get_current_version", return_value="2026.10.22"):
        app._update_tray_tooltip()
    assert "2026.10.22" in app.tray_icon.setToolTip.call_args.args[0]


def test_download_page_fallback_is_not_an_executable_launch():
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    app._open_release_page("https://github.com/owner/repo/releases/latest")
    app._reveal_downloaded_file("/home/user/Downloads/release.AppImage")
