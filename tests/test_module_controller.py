# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for explicit lazy feature and UI module construction."""

from unittest.mock import MagicMock, patch


def _module_controller(*args):
    """Import after tests with custom Qt stubs have been collected."""
    from core.module_controller import ModuleController

    return ModuleController(*args)


def test_feature_factories_are_lazy_and_cache_first_instance():
    services = MagicMock()
    controller = _module_controller(services, "icon.png", MagicMock(return_value={}))
    with (
        patch("core.module_controller.CommandHistory") as history_factory,
        patch("core.module_controller.CommandCreator") as creator_factory,
    ):
        assert controller._history is None
        assert controller._creator is None
        history = controller.get_history()
        assert controller.get_history() is history
        creator = controller.get_creator()

    history_factory.assert_called_once_with(services)
    creator_factory.assert_called_once_with(services)
    assert controller._history is history
    assert controller._creator is creator


def test_all_feature_factories_use_app_services_and_cache():
    services = MagicMock()
    controller = _module_controller(services, "icon.png", MagicMock(return_value={}))
    with (
        patch("core.module_controller.CommandHistory") as history,
        patch("core.module_controller.CommandCreator") as creator,
        patch("core.module_controller.CommandExecutor") as executor,
        patch("core.module_controller.CommandSearch") as search,
        patch("core.module_controller.BackupRestore") as backup,
        patch("core.module_controller.ImportExport") as import_export,
        patch("core.module_controller.Favorites") as favorites,
        patch("core.module_controller.FileEncryptor") as encryptor,
        patch("core.module_controller.ScheduleCreator") as schedule_creator,
        patch("core.module_controller.ScheduleViewer") as schedule_viewer,
    ):
        expected = {
            "history": controller.get_history(),
            "creator": controller.get_creator(),
            "executor": controller.get_executor(),
            "search": controller.get_search(),
            "backup": controller.get_backup(),
            "import_export": controller.get_import_export(),
            "favorites": controller.get_favorites(),
            "file_encryptor": controller.get_file_encryptor(),
            "schedule_creator": controller.get_schedule_creator(),
            "schedule_viewer": controller.get_schedule_viewer(),
        }
        factories = (
            history,
            creator,
            executor,
            search,
            backup,
            import_export,
            favorites,
            encryptor,
            schedule_creator,
            schedule_viewer,
        )
        for factory in factories:
            factory.assert_called_once_with(services)
        for name, module in expected.items():
            assert getattr(controller, f"get_{name}")() is module


def test_ui_factories_register_configured_hotkeys_only_on_first_use():
    services = MagicMock()
    settings = {
        "hotkey": "ctrl+x",
        "app_launcher_hotkey": "ctrl+y",
        "quick_launch_bar": {"hotkey": "ctrl+z"},
    }
    get_settings = MagicMock(return_value=settings)
    controller = _module_controller(services, "icon.png", get_settings)

    with (
        patch("core.module_controller.CommandPalette") as palette_factory,
        patch("core.module_controller.QuickLaunchBar") as bar_factory,
    ):
        assert controller.loaded_palette is None
        assert controller.loaded_quick_launch_bar is None
        assert controller.get_palette() is controller.get_palette()
        assert controller.get_quick_launch_bar() is controller.get_quick_launch_bar()

    palette_factory.assert_called_once_with(services)
    palette_factory.return_value.register_hotkeys.assert_called_once_with("ctrl+x", "ctrl+y")
    bar_factory.assert_called_once_with(services, "icon.png")
    bar_factory.return_value.register_hotkey.assert_called_once_with("ctrl+z")
    assert get_settings.call_count == 2


def test_cleanup_hotkeys_does_not_construct_unused_ui_modules():
    controller = _module_controller(MagicMock(), "icon.png", MagicMock(return_value={}))
    with (
        patch("core.module_controller.CommandPalette") as palette_factory,
        patch("core.module_controller.QuickLaunchBar") as bar_factory,
    ):
        controller.cleanup()

    palette_factory.assert_not_called()
    bar_factory.assert_not_called()
