# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import datetime
import logging
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

from PyQt6.QtCore import QObject, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon

from core.badge_manager import BadgeManager
from core.config_manager import ConfigurationError, config_manager
from core.icon_resolver import IconResolver
from core.menu_builder import MenuBuilder, MenuBuilderDependencies
from core.menu_controller import MenuController
from core.module_controller import ModuleController
from core.process_output_relay import ProcessOutputRelay
from core.process_tracker import ProcessTracker
from core.services import AppServices
from core.theme_controller import ThemeController
from core.update_checker import (
    CancellationToken,
    ReleaseInfo,
    check_for_update,
    current_platform,
    download_release_asset,
    select_release_asset,
)
from core.version import VERSION, get_current_version
from ui.command_manager import CommandManagerDialog
from ui.output_window import RichOutputWindow
from ui.settings_dialog import SettingsDialog
from utils.dialogs import confirm_execute, confirm_exit, prompt_text, show_error_and_raise

logger = logging.getLogger(__name__)


class UpdateWorker(QThread):
    """Execute a release lookup or download away from the Qt main thread."""

    result = pyqtSignal(object)
    failed = pyqtSignal(object)
    progress = pyqtSignal(int)

    def __init__(self, kind: str, operation, cancellation: CancellationToken) -> None:
        """Initialize a worker with its operation and cooperative cancellation token."""
        super().__init__()
        self.kind = kind
        self.operation = operation
        self.cancellation = cancellation

    def run(self) -> None:
        """Run the operation and report one result or failure through Qt signals."""
        try:
            value = self.operation(self)
        except InterruptedError:
            logger.info("Update %s operation cancelled", self.kind)
            self.failed.emit((self.kind, "cancelled"))
        except Exception as exc:
            logger.warning("Update %s operation failed: %s", self.kind, exc, exc_info=True)
            self.failed.emit((self.kind, str(exc)))
        else:
            self.result.emit((self.kind, value))


class UpdateWorkerBridge(QObject):
    """Deliver worker signals to TrayApp through a main-thread QObject receiver."""

    def __init__(self, tray_app: TrayApp, worker: UpdateWorker) -> None:
        """Bind one worker's callbacks to the tray application's Qt thread."""
        super().__init__()
        self.tray_app: TrayApp | None = tray_app
        self.worker: UpdateWorker | None = worker

    def on_result(self, outcome) -> None:
        """Forward a worker result to the owning tray application."""
        if self.tray_app is not None:
            self.tray_app._on_update_worker_result(outcome)

    def on_failure(self, failure) -> None:
        """Forward a worker failure to the owning tray application."""
        if self.tray_app is not None:
            self.tray_app._on_update_worker_failure(failure)

    def on_progress(self, received: int) -> None:
        """Forward byte progress to the owning tray application."""
        if self.tray_app is not None:
            self.tray_app._on_update_download_progress(received)

    def on_finished(self) -> None:
        """Release the retained worker after its QThread has stopped."""
        tray_app = self.tray_app
        worker = self.worker
        if tray_app is not None and worker is not None:
            tray_app._on_update_worker_finished(worker)
        self.tray_app = None
        self.worker = None


class TrayApp:
    """Main tray application class that manages the system tray icon and menu."""

    def __init__(self, app, instance_checker):
        """Initialise the TrayApp.

        Construction is broken into focused private methods so that each
        responsibility is clear and individually testable:

          _setup_paths()       — base_dir, icon_file
          _setup_theme()       — ThemeManager, apply theme from settings
          _setup_tray_icon()   — QSystemTrayIcon, quit-on-close behaviour
          _build_services()    — AppServices dataclass (ProcessTracker, BadgeManager,
                                 ProcessOutputRelay wiring)
          _build_modules()     — feature module instances
          _build_ui()          — UI widget instances and hotkeys
          _build_menu()        — tray context menu
        """
        self.app = app
        self.instance_checker = instance_checker
        self._update_workers: set[UpdateWorker] = set()
        self._update_worker_bridges: dict[UpdateWorker, UpdateWorkerBridge] = {}
        self._shutting_down = False
        self._available_update: ReleaseInfo | None = None
        self._download_release: ReleaseInfo | None = None
        self._download_progress = 0
        self._update_interval_ms = 0
        self._update_deadline: float | None = None

        self._setup_paths()
        self._setup_theme()
        self._setup_tray_icon()
        self._build_services()
        self._build_modules()
        self._build_menu()

    # ------------------------------------------------------------------ #
    # Initialisation steps                                                 #
    # ------------------------------------------------------------------ #

    def _setup_paths(self) -> None:
        """Resolve base_dir and tray icon path."""
        self.base_dir = config_manager.get_base_dir()
        self.icon_resolver = IconResolver(self.base_dir)

        tray_icon_path = self.icon_resolver.resolve_tray_icon()
        if not tray_icon_path:
            tray_icon_path = os.path.join(
                self.base_dir, "resources", "icons", "branding", "icon.png"
            )
        self.icon_file = tray_icon_path

        logger.info("Base directory resolved to %s", self.base_dir)
        logger.info("Tray icon path resolved to %s", self.icon_file)

        # Apply icon cache TTL from settings (default 7 days)
        ttl_days = config_manager.get_settings().get("icon_cache_ttl_days", 7)
        self.icon_resolver.set_cache_ttl(ttl_days)

    def _setup_theme(self) -> None:
        """Initialize theme policy and expose the manager to settings previews."""
        self.theme_controller = ThemeController(self.base_dir, config_manager)
        self.theme_controller.initialize()
        self.theme_manager = self.theme_controller.theme_manager

    def _setup_tray_icon(self) -> None:
        """Create QSystemTrayIcon and configure application quit behaviour."""
        self.app.aboutToQuit.connect(self.cleanup)
        self.app.setQuitOnLastWindowClosed(False)

        tray_qicon = QIcon(self.icon_file)
        self.app.setWindowIcon(tray_qicon)
        self.tray_icon = QSystemTrayIcon(tray_qicon)
        self.tray_icon.setIcon(tray_qicon)
        self.tray_icon.setVisible(True)

        self.menu = QMenu()
        self.output_windows: list = []
        self.process_tracker = ProcessTracker(self.app)
        self._running_action = None
        self._update_timer = QTimer(self.app)
        self._update_timer.timeout.connect(self._on_update_timer_timeout)

    def _build_services(self) -> None:
        """Construct the AppServices dataclass and load the initial command menu."""
        try:
            self.command_menu = config_manager.get_commands()
        except ConfigurationError as e:
            show_error_and_raise(f"Failed to load commands: {str(e)}")
            self.command_menu = {}

        self.services = AppServices(
            config_manager=config_manager,
            execute=self.execute,
            reload_commands=self.reload_commands,
            show_output=self.show_command_output,
            get_all_commands=self.get_all_commands,
            save_commands=self.save_commands,
            reload_history_commands=self.reload_history_commands,
            reload_favorites_commands=self.reload_favorites_commands,
            resolve_command_reference=self.resolve_command_reference,
            resolve_icon_path=self._resolve_icon_path,
            notify_user=self.notify_user,
            process_tracker=self.process_tracker,
        )

        self.badge_manager = BadgeManager(self.tray_icon, self.icon_file)
        self.process_tracker.process_count_changed.connect(self._on_process_count_changed)

    def _build_modules(self) -> None:
        """Compose the lazy feature and UI module registry."""
        self.module_controller = ModuleController(
            self.services,
            self.icon_file,
            config_manager.get_settings,
        )

    # ------------------------------------------------------------------ #
    # Lazy factory accessors                                               #
    # ------------------------------------------------------------------ #

    def get_history(self):
        return self.module_controller.get_history()

    def get_creator(self):
        return self.module_controller.get_creator()

    def get_executor(self):
        return self.module_controller.get_executor()

    def get_search(self):
        return self.module_controller.get_search()

    def get_backup(self):
        return self.module_controller.get_backup()

    def get_import_export(self):
        return self.module_controller.get_import_export()

    def get_favorites(self):
        return self.module_controller.get_favorites()

    def get_file_encryptor(self):
        return self.module_controller.get_file_encryptor()

    def get_schedule_creator(self):
        return self.module_controller.get_schedule_creator()

    def get_schedule_viewer(self):
        return self.module_controller.get_schedule_viewer()

    def get_palette(self):
        return self.module_controller.get_palette()

    def _build_menu(self) -> None:
        """Build the tray context menu and attach it to the tray icon.

        Heavy (feature-module-touching) menu construction is deferred to the
        first ``aboutToShow`` so startup does not instantiate lazy modules.
        """
        self._reload_command_data()
        dependencies = MenuBuilderDependencies(
            icon_file=self.icon_file,
            get_command_menu=lambda: self.command_menu,
            resolve_icon_path=self._resolve_icon_path,
            execute=self.execute,
            get_favorites=self.get_favorites,
            set_favorites_menu=lambda menu: self.menu_controller.set_favorites_menu(menu),
            reload_favorites_commands=self.reload_favorites_commands,
            set_history_menu=lambda menu: self.menu_controller.set_history_menu(menu),
            reload_history_commands=self.reload_history_commands,
            get_palette=self.get_palette,
            open_command_manager=self._open_command_manager,
            open_commands_json=self.open_commands_json,
            reload_commands=self.reload_commands,
            get_import_export=self.get_import_export,
            get_backup=self.get_backup,
            get_file_encryptor=self.get_file_encryptor,
            get_schedule_creator=self.get_schedule_creator,
            get_schedule_viewer=self.get_schedule_viewer,
            open_settings=self._open_settings,
            set_running_action=lambda action: setattr(self, "_running_action", action),
            restart_app=self.restart_app,
            confirm_exit=self.confirm_exit,
            check_for_updates=self.check_for_updates,
            get_update=lambda: self._available_update,
            open_update=self.open_update,
        )
        builder = MenuBuilder(dependencies)
        self.menu_controller = MenuController(
            menu=self.menu,
            tray_icon=self.tray_icon,
            menu_builder=builder,
            get_command_menu=lambda: self.command_menu,
            reload_command_data=self._reload_command_data,
            update_tooltip=self._update_tray_tooltip,
            get_history=self.get_history,
            get_favorites=self.get_favorites,
        )
        self.menu_controller.attach()

    # ------------------------------------------------------------------ #
    # Icon path resolution (thin proxy to IconResolver)                   #
    # ------------------------------------------------------------------ #

    def _resolve_icon_path(self, icon_path: str) -> str:
        """Resolve an icon path using IconResolver with self.icon_file as fallback."""
        return self.icon_resolver.resolve_icon_path(icon_path, self.icon_file)

    # ------------------------------------------------------------------ #
    # Tray tooltip                                                         #
    # ------------------------------------------------------------------ #

    def _update_tray_tooltip(self) -> None:
        """Show the resolved application version and loaded command count."""
        try:
            count = len(self.get_all_commands())
            self.tray_icon.setToolTip(
                f"Py Tray Command Launcher {get_current_version()} — {count} command(s) loaded"
            )
        except Exception:
            self.tray_icon.setToolTip(f"Py Tray Command Launcher {get_current_version()}")

    def _configure_update_timer(self, run_startup_check: bool = False) -> None:
        """Apply persisted automatic-check settings and optionally check at startup."""
        settings = config_manager.get_settings()
        enabled = settings.get("update_check_enabled", True)
        interval = settings.get("update_check_interval_hours", 24)
        if (
            not isinstance(enabled, bool)
            or not isinstance(interval, int)
            or isinstance(interval, bool)
            or interval < 1
        ):
            logger.warning("Invalid update-check settings; using safe defaults")
            enabled, interval = True, 24
        self._update_timer.stop()
        self._update_deadline = None
        if enabled:
            self._update_interval_ms = interval * 60 * 60 * 1000
            self._update_deadline = time.monotonic() + self._update_interval_ms / 1000
            self._schedule_update_timer()
            if run_startup_check:
                self._start_update_check()

    def _schedule_update_timer(self) -> None:
        """Schedule the next timer chunk without truncating large hour values."""
        if self._update_deadline is None or self._shutting_down:
            return
        remaining_ms = max(1, int((self._update_deadline - time.monotonic()) * 1000))
        self._update_timer.start(min(remaining_ms, 2_147_483_647))

    def _on_update_timer_timeout(self) -> None:
        """Run an automatic check when the configured interval has elapsed."""
        if self._shutting_down or self._update_deadline is None:
            return
        if time.monotonic() < self._update_deadline:
            self._schedule_update_timer()
            return
        self._update_deadline = time.monotonic() + self._update_interval_ms / 1000
        self._schedule_update_timer()
        self._start_update_check()

    def check_for_updates(self) -> None:
        """Start a manual release check, even when automatic checks are disabled."""
        self._start_update_check()

    def _start_update_check(self) -> None:
        """Start one background release check unless one is already active."""
        if self._shutting_down or any(worker.kind == "check" for worker in self._update_workers):
            return
        self._start_update_worker(
            "check",
            lambda _worker: check_for_update(VERSION),
        )

    def _start_update_worker(self, kind: str, operation) -> UpdateWorker:
        """Retain, connect, and start an update worker."""
        cancellation = CancellationToken()
        worker = UpdateWorker(kind, operation, cancellation)
        bridge = UpdateWorkerBridge(self, worker)
        self._update_workers.add(worker)
        self._update_worker_bridges[worker] = bridge
        worker.result.connect(bridge.on_result)
        worker.failed.connect(bridge.on_failure)
        worker.progress.connect(bridge.on_progress)
        worker.finished.connect(bridge.on_finished)
        worker.start()
        return worker

    def _on_update_worker_result(self, outcome) -> None:
        """Apply a completed worker result only while the tray is alive."""
        if self._shutting_down:
            return
        kind, value = outcome
        if kind == "check":
            self._available_update = value
            if hasattr(self, "menu_controller"):
                self.menu_controller.refresh_update_action()
            if value is not None:
                settings = config_manager.get_settings()
                if settings.get("dismissed_update_version") != value.version:
                    self.notify_user(
                        "Update available",
                        f"py-tray-command-launcher {value.version} is available.",
                    )
                    settings["dismissed_update_version"] = value.version
                    try:
                        config_manager.save_settings(settings)
                    except ConfigurationError:
                        logger.exception("Could not persist update notification state")
        elif kind == "download":
            self._download_progress = 0
            self._download_release = None
            self._reveal_downloaded_file(value.path)

    def _on_update_worker_failure(self, failure) -> None:
        """Fall back to the release page after a failed transfer, unless shutting down."""
        if self._shutting_down:
            return
        kind, _message = failure
        if kind == "check":
            self._available_update = None
            if hasattr(self, "menu_controller"):
                self.menu_controller.refresh_update_action()
        elif kind == "download" and self._download_release is not None:
            self._open_release_page(self._download_release.html_url)
            self._download_release = None

    def _on_update_worker_finished(self, worker: UpdateWorker) -> None:
        """Release a worker reference only after its QThread has finished."""
        self._update_workers.discard(worker)
        self._update_worker_bridges.pop(worker, None)

    def _on_update_download_progress(self, received: int) -> None:
        """Expose download progress in the tray tooltip while the transfer runs."""
        if self._shutting_down:
            return
        self._download_progress = received
        self.tray_icon.setToolTip(
            f"Py Tray Command Launcher {get_current_version()} — downloading update ({received} bytes)"
        )

    def open_update(self, release: ReleaseInfo) -> None:
        """Download a compatible release or open the release page as fallback."""
        if self._shutting_down:
            return
        system, architecture = current_platform()
        asset = select_release_asset(release.assets, system, architecture)
        checksum_asset = release.asset("SHA256SUMS")
        if asset is None or checksum_asset is None:
            self._open_release_page(release.html_url)
            return
        self._download_release = release

        def download(worker: UpdateWorker):
            return download_release_asset(
                asset,
                checksum_asset,
                Path.home() / "Downloads",
                progress_callback=worker.progress.emit,
                cancellation=worker.cancellation,
            )

        self._start_update_worker("download", download)

    def _open_release_page(self, url: str) -> None:
        """Open the validated GitHub release page in the user's browser."""
        if self._shutting_down or not url.startswith("https://github.com/"):
            return
        QDesktopServices.openUrl(QUrl(url))

    def _reveal_downloaded_file(self, path: Path) -> None:
        """Open the containing folder in a file manager without launching the asset."""
        if self._shutting_down:
            return
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", f"/select,{path}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path.parent)])
        except OSError:
            logger.exception("Could not reveal verified update file %s", path)

    # ------------------------------------------------------------------ #
    # Command execution                                                    #
    # ------------------------------------------------------------------ #

    def load_tray_menu(self):
        """Load commands into the tray menu."""
        self.menu_controller.load_tray_menu()

    def execute(self, title, command, confirm, show_output, prompt):
        """Execute a command with optional confirmation and input prompt."""
        self._record_history(command, title, confirm, show_output, prompt)
        self._route_execution(title, command, confirm, show_output, prompt)
        self.reload_history_commands()
        self.reload_favorites_commands()

    def _record_history(self, command, title, confirm, show_output, prompt):
        """Record a history entry via config_manager."""
        config_manager.add_to_history(
            {
                "command": command,
                "title": title,
                "confirm": confirm,
                "showOutput": show_output,
                "prompt": prompt,
                "timestamp": datetime.datetime.now().isoformat(),
            }
        )

    def _get_prompt_input(self, prompt):
        """Show input dialog. Returns (value, ok) or (None, False)."""
        input_value, ok = prompt_text(None, "Input Required", prompt)
        if not ok or not input_value:
            return None, False
        return input_value, True

    def _substitute_prompt(self, command, prompt):
        """Replace {promptInput} with OS-quoted user input.

        Returns (command, ok) where ok=False if the user cancelled or
        entered empty text.
        """
        input_value, ok = self._get_prompt_input(prompt)
        if not ok:
            return command, False
        if os.name == "nt":
            safe_input = subprocess.list2cmdline([input_value])
        else:
            safe_input = shlex.quote(input_value)
        command = command.replace("{promptInput}", safe_input)
        return command, True

    def _route_execution(self, title, command, confirm, show_output, prompt):
        """Gate on confirmation, substitute prompts, then route execution."""
        if confirm:
            if not confirm_execute(command):
                return
        if prompt:
            command, ok = self._substitute_prompt(command, prompt)
            if not ok:
                return
        if show_output:
            self.show_command_output(title, command)
        else:
            self.get_executor().execute_command(command)

    def notify_user(self, title: str, message: str) -> None:
        """Show a tray notification."""
        self.tray_icon.showMessage(title, message)

    def show_command_output(self, title, command):
        """Execute a command, show output in RichOutputWindow, and update badge."""
        process = self.get_executor().execute_command_process(self.app, command)

        output_win = RichOutputWindow(
            self.app.activeWindow(), self.services, theme_manager=self.theme_manager
        )
        tab = output_win.open_process_tab(title)
        self.output_windows.append(output_win)
        output_win.destroyed.connect(lambda _, w=output_win: self._on_output_window_closed(w))

        proc_id = self.process_tracker.track(process)
        relay = ProcessOutputRelay(process, output_win, tab, command)
        relay.wire(
            on_finished=lambda *_args: self.process_tracker.remove(
                proc_id, expected_process=process
            )
        )
        # process.start() is called inside execute_command_process

    def _on_output_window_closed(self, win):
        """Remove a closed output window from the tracking list."""
        try:
            self.output_windows.remove(win)
        except ValueError:
            pass

    def _on_process_count_changed(self, count: int) -> None:
        """Update the running-action label/visibility and repaint the tray badge."""
        if self._running_action is not None:
            if count > 0:
                self._running_action.setText(f"Running: {count}")
                self._running_action.setVisible(True)
            else:
                self._running_action.setVisible(False)
        self.badge_manager.update_badge(count)

    # ------------------------------------------------------------------ #
    # Utility / reload methods                                             #
    # ------------------------------------------------------------------ #

    def save_commands(self, commands):
        """Save commands to the configuration."""
        try:
            config_manager.save_commands(commands)
        except ConfigurationError as e:
            show_error_and_raise(f"Failed to save commands: {str(e)}")

    def get_all_commands(self):
        """Get all commands from the configuration."""
        try:
            commands = config_manager.get_commands()
            result = []

            def process_items(group_name, items):
                for label, item in items.items():
                    if isinstance(item, dict) and "command" in item and label != "icon":
                        result.append(
                            {
                                "group": group_name,
                                "label": label,
                                "command": item["command"],
                                "confirm": item.get("confirm", False),
                                "showOutput": item.get("showOutput", False),
                                "prompt": item.get("prompt"),
                            }
                        )
                    elif isinstance(item, dict) and "command" not in item and label != "icon":
                        new_group = f"{group_name} → {label}"
                        process_items(new_group, item)

            for group_name, items in commands.items():
                if isinstance(items, dict):
                    process_items(group_name, items)

            return result
        except ConfigurationError as e:
            show_error_and_raise(f"Failed to get commands: {str(e)}")
            return []

    def open_commands_json(self):
        """Open the active commands file with the default text editor."""
        try:
            command_paths = config_manager.get_command_paths()
            commands_file = command_paths["active_commands_file"]

            if not os.path.exists(commands_file):
                legacy = os.path.join(command_paths["config_dir"], "commands.json")
                if os.path.exists(legacy):
                    commands_file = legacy

            if sys.platform == "win32":
                os.startfile(commands_file)  # noqa: S606 — intentional: Windows file open via shell association; path is from config, not user input
            elif sys.platform == "darwin":
                subprocess.call(("open", str(commands_file)))  # noqa: S603, S607 — platform file-open helper, fixed args
            else:
                subprocess.call(("xdg-open", str(commands_file)))  # noqa: S603, S607 — platform file-open helper, fixed args
        except Exception as e:
            show_error_and_raise(f"Failed to open commands file: {e}")

    def reload_commands(self, rebuild_menu: bool = False):
        """Reload the commands from the configuration file."""
        if not hasattr(self, "menu_controller"):
            self._reload_command_data()
            return
        self.menu_controller.reload_commands(rebuild_menu)

    def _reload_command_data(self) -> dict:
        """Read commands from configuration and retain the latest snapshot."""
        try:
            command_paths = config_manager.get_command_paths()
            logger.info(
                "Reloading commands from %s (config dir: %s)",
                command_paths["active_commands_file"],
                command_paths["config_dir"],
            )
            self.command_menu = config_manager.get_commands(refresh=True)
            return self.command_menu
        except ConfigurationError as e:
            show_error_and_raise(f"Failed to reload commands: {str(e)}")
            self.command_menu = {}
            return self.command_menu

    def reload_history_commands(self):
        """Reload the history commands (no-op until the lazy tray menu exists)."""
        if hasattr(self, "menu_controller"):
            self.menu_controller.reload_history_commands()

    def resolve_command_reference(self, group, label, item):
        """Resolve a ``ref`` entry (e.g. a favorite) to the command it points at."""
        return self.menu_controller.resolve_command_reference(group, label, item)

    def reload_favorites_commands(self):
        """Reload the favorites menu with current favorites.

        The submenu only exists once the lazy tray menu has been built; until
        then there is nothing to refresh (it is populated on first build).
        """
        if hasattr(self, "menu_controller"):
            self.menu_controller.reload_favorites_commands()

    # ------------------------------------------------------------------ #
    # Dialog openers                                                       #
    # ------------------------------------------------------------------ #

    def _open_command_manager(self):
        """Open the Command Manager dialog."""
        dialog = CommandManagerDialog(self.services, self.process_tracker.processes, parent=None)
        dialog.exec()

    def _open_settings(self):
        """Open the Settings dialog."""
        dlg = SettingsDialog(
            self.services,
            self.theme_manager,
            parent=None,
            hotkey_callback=self._reregister_hotkey,
            app_launcher_hotkey_callback=self._reregister_app_launcher_hotkey,
        )
        dlg.exec()
        self._configure_update_timer()

    # ------------------------------------------------------------------ #
    # Hotkey re-registration                                               #
    # ------------------------------------------------------------------ #

    def _loaded_palette(self):
        """Return the palette only if it has already been constructed."""
        return self.module_controller.loaded_palette

    def _reregister_hotkey(self, hotkey: str) -> None:
        """Unregister the current palette hotkey and register the new one."""
        palette = self._loaded_palette()
        if palette is None:
            return
        try:
            palette.unregister_hotkey()
            palette.register_hotkey(hotkey)
            logger.info("Palette hotkey re-registered: %s", hotkey)
        except Exception as exc:
            logger.warning("Failed to re-register palette hotkey '%s': %s", hotkey, exc)

    def _reregister_app_launcher_hotkey(self, hotkey: str) -> None:
        """Unregister the app launcher hotkey and register the new one."""
        palette = self._loaded_palette()
        if palette is None:
            return
        try:
            palette.unregister_hotkey()
            palette.update_app_launcher_hotkey(hotkey)
            logger.info("App Launcher hotkey re-registered: %s", hotkey)
        except Exception as exc:
            logger.warning("Failed to re-register app launcher hotkey '%s': %s", hotkey, exc)

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def restart_app(self):
        """Restart the application."""
        self.cleanup()
        python = sys.executable
        os.execl(python, python, *sys.argv)  # noqa: S606 — intentional: restart using the same interpreter; fixed args from sys.executable and sys.argv

    def confirm_exit(self):
        """Show confirmation dialog for exiting the application."""
        if confirm_exit():
            self.app.quit()

    def cleanup(self):
        """Perform cleanup before quitting."""
        if self._shutting_down:
            return
        self._shutting_down = True
        logger.info("Cleaning up before exit")
        self._update_timer.stop()
        workers = tuple(self._update_workers)
        for worker in workers:
            worker.result.disconnect()
            worker.failed.disconnect()
            worker.progress.disconnect()
            worker.finished.disconnect()
            worker.cancellation.cancel()
        for worker in workers:
            worker.wait()
        self._update_workers.clear()
        self._update_worker_bridges.clear()
        for window in self.output_windows:
            window.close()
        self.module_controller.cleanup()
        self.instance_checker.cleanup()

    def run(self):
        """Run the application event loop."""
        self._configure_update_timer(run_startup_check=True)
        sys.exit(self.app.exec())
