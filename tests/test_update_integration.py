# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration, menu, and tray integration regression tests for updates."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.config_manager import ConfigManager
from core.update_checker import ReleaseAsset, ReleaseInfo


def test_update_settings_have_defaults_and_round_trip(tmp_path):
    manager = object.__new__(ConfigManager)
    manager.config_dir = tmp_path
    manager.settings_file = tmp_path / "settings.json"
    manager.defaults_dir = tmp_path / "config"
    manager._settings_cache = None
    manager.defaults_dir.mkdir()
    schema = Path(__file__).resolve().parents[1] / "config/settings.schema.json"
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
    manager = object.__new__(ConfigManager)
    manager.defaults_dir = Path(__file__).resolve().parents[1] / "config"
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
    update_labels = []

    def make_action(label, _parent):
        action = MagicMock()
        action.text.return_value = label
        update_labels.append(label)
        return action

    submenu_factory = MagicMock()
    submenu_factory.return_value = MagicMock()
    monkeypatch.setattr("core.menu_builder.QMenu", submenu_factory)
    monkeypatch.setattr("core.menu_builder.QIcon", MagicMock())
    monkeypatch.setattr("core.menu_builder.QAction", make_action)

    MenuBuilder(MenuBuilderDependencies(**callbacks)).build(menu, {})

    actions = [call.args[0] for call in menu.addAction.call_args_list]
    assert "Check for updates" in actions
    assert "Update available: 2026.10.22" in update_labels


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
    app._shutting_down = False
    with (
        patch("core.tray_app.QDesktopServices.openUrl") as open_url,
        patch("core.tray_app.QUrl", side_effect=lambda url: url),
        patch("core.tray_app.subprocess.Popen") as popen,
    ):
        app._open_release_page("https://github.com/owner/repo/releases/latest")
        app._reveal_downloaded_file(Path("/home/user/Downloads/release.AppImage"))
    open_url.assert_called_once_with("https://github.com/owner/repo/releases/latest")
    assert popen.call_args.args[0] == ["xdg-open", "/home/user/Downloads"]


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot=None):
        self.slots.clear() if slot is None else self.slots.remove(slot)

    def emit(self, *args):
        for slot in tuple(self.slots):
            slot(*args)


class _Worker:
    def __init__(self, kind, operation, cancellation):
        self.kind = kind
        self.operation = operation
        self.cancellation = cancellation
        self.result = _Signal()
        self.failed = _Signal()
        self.progress = _Signal()
        self.finished = _Signal()
        self.started = False
        self.waited = False
        self.wait_count = 0

    def start(self):
        self.started = True

    def wait(self):
        self.waited = True
        self.wait_count += 1


def test_update_worker_is_retained_until_finished(monkeypatch):
    from core.tray_app import TrayApp

    monkeypatch.setattr("core.tray_app.UpdateWorker", _Worker)
    app = object.__new__(TrayApp)
    app.app = MagicMock()
    app._update_workers = set()
    app._update_worker_bridges = {}
    app._shutting_down = False

    worker = app._start_update_worker("check", lambda _worker: None)

    assert worker.started
    assert worker in app._update_workers
    worker.finished.emit()
    assert worker not in app._update_workers


def test_update_check_does_not_overlap_an_active_check():
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    app._shutting_down = False
    active_worker = MagicMock()
    active_worker.kind = "check"
    app._update_workers = {active_worker}
    app._start_update_worker = MagicMock()

    app._start_update_check()

    app._start_update_worker.assert_not_called()


def test_cleanup_cancels_waits_and_suppresses_late_worker_callbacks(monkeypatch):
    from core.tray_app import TrayApp

    monkeypatch.setattr("core.tray_app.UpdateWorker", _Worker)
    app = object.__new__(TrayApp)
    app.app = MagicMock()
    app._update_workers = set()
    app._update_worker_bridges = {}
    app._shutting_down = False
    app._update_timer = MagicMock()
    app.output_windows = []
    app.module_controller = MagicMock()
    app.instance_checker = MagicMock()
    app._available_update = None
    worker = app._start_update_worker("check", lambda _worker: None)

    app.cleanup()
    worker.result.emit(("check", object()))
    worker.progress.emit(50)

    assert app._shutting_down
    assert worker.cancellation.cancelled
    assert worker.waited
    assert app._update_workers == set()
    app.module_controller.cleanup.assert_called_once_with()
    app.instance_checker.cleanup.assert_called_once_with()
    app.cleanup()
    assert worker.wait_count == 1


def test_tray_run_starts_update_checks_after_app_construction():
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    events = []
    app._configure_update_timer = MagicMock(
        side_effect=lambda **_kwargs: events.append("configure_updates")
    )
    app.app = MagicMock()
    app.app.exec.side_effect = lambda: events.append("event_loop") or 0

    with patch("core.tray_app.sys.exit") as exit_process:
        app.run()

    assert events == ["configure_updates", "event_loop"]
    app._configure_update_timer.assert_called_once_with(run_startup_check=True)
    exit_process.assert_called_once_with(0)


def test_update_notification_is_persisted_and_shown_once_per_version():
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    app._shutting_down = False
    app._available_update = None
    app.menu_controller = MagicMock()
    app.notify_user = MagicMock()
    settings = {"dismissed_update_version": ""}
    release = ReleaseInfo(
        "2026.10.22",
        "2026.10.22",
        "https://github.com/DewaldOosthuizen/py-tray-command-launcher/releases/tag/2026.10.22",
        (ReleaseAsset("bundle.AppImage", 10, "https://github.com/bundle"),),
    )
    with patch("core.tray_app.config_manager") as config:
        config.get_settings.return_value = settings
        app._on_update_worker_result(("check", release))
        app._on_update_worker_result(("check", release))

    app.notify_user.assert_called_once()
    assert settings["dismissed_update_version"] == "2026.10.22"
    assert config.save_settings.call_count == 1
    app.menu_controller.refresh_update_action.assert_called_with()


def test_automatic_check_can_be_disabled_without_disabling_manual_check():
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    app._update_timer = MagicMock()
    app._start_update_check = MagicMock()
    with patch(
        "core.tray_app.config_manager.get_settings", return_value={"update_check_enabled": False}
    ):
        app._configure_update_timer(run_startup_check=True)

    app._update_timer.stop.assert_called_once_with()
    app._update_timer.start.assert_not_called()
    app._start_update_check.assert_not_called()
    app.check_for_updates()
    app._start_update_check.assert_called_once_with()


def test_automatic_timer_waits_full_interval_and_runs_check(monkeypatch):
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    app._shutting_down = False
    app._update_timer = MagicMock()
    app._start_update_check = MagicMock()
    now = [100.0]
    monkeypatch.setattr("core.tray_app.time.monotonic", lambda: now[0])
    with patch(
        "core.tray_app.config_manager.get_settings",
        return_value={"update_check_enabled": True, "update_check_interval_hours": 1},
    ):
        app._configure_update_timer()

    assert app._update_deadline == 3700.0
    app._update_timer.start.assert_called_with(3_600_000)
    app._on_update_timer_timeout()
    app._start_update_check.assert_not_called()

    now[0] = 3700.0
    app._on_update_timer_timeout()
    app._start_update_check.assert_called_once_with()


def test_unsupported_platform_opens_release_page(monkeypatch):
    from core.tray_app import TrayApp

    app = object.__new__(TrayApp)
    app._shutting_down = False
    release = ReleaseInfo(
        "2026.10.22",
        "2026.10.22",
        "https://github.com/DewaldOosthuizen/py-tray-command-launcher/releases/tag/2026.10.22",
        (
            ReleaseAsset(
                "py-tray-command-launcher-2026.10.22-x86_64.AppImage",
                10,
                "https://github.com/asset",
            ),
        ),
    )
    monkeypatch.setattr("core.tray_app.current_platform", lambda: ("windows", "amd64"))
    with patch.object(app, "_open_release_page") as open_page:
        app.open_update(release)
    open_page.assert_called_once_with(release.html_url)
