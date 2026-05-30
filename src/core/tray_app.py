# SPDX-License-Identifier: GPL-3.0-or-later

import datetime
import logging
import os
import subprocess
import sys
import weakref

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QInputDialog, QMenu, QSystemTrayIcon

from core.config_manager import ConfigurationError, config_manager
from core.icon_resolver import IconResolver
from core.menu_builder import MenuBuilder
from core.services import AppServices
from core.theme_manager import ThemeManager
from modules.backup_restore import BackupRestore
from modules.command_creator import CommandCreator
from modules.command_executor import CommandExecutor
from modules.command_history import CommandHistory
from modules.command_search import CommandSearch
from modules.favorites import Favorites
from modules.file_encryptor import FileEncryptor
from modules.import_export import ImportExport
from modules.schedule_creator import ScheduleCreator
from modules.schedule_viewer import ScheduleViewer
from ui.command_manager import CommandManagerDialog
from ui.command_palette import CommandPalette
from ui.output_window import RichOutputWindow
from ui.quick_launch_bar import QuickLaunchBar
from ui.settings_dialog import SettingsDialog
from utils.dialogs import confirm_execute, confirm_exit, show_error_and_raise

logger = logging.getLogger(__name__)


class TrayApp:
    """Main tray application class that manages the system tray icon and menu."""

    def __init__(self, app, instance_checker):
        """Initialise the TrayApp.

        Construction is broken into focused private methods so that each
        responsibility is clear and individually testable:

          _setup_paths()       — base_dir, icon_file
          _setup_theme()       — ThemeManager, apply theme from settings
          _setup_tray_icon()   — QSystemTrayIcon, quit-on-close behaviour
          _build_services()    — AppServices dataclass
          _build_modules()     — feature module instances
          _build_ui()          — UI widget instances and hotkeys
          _build_menu()        — tray context menu
        """
        self.app = app
        self.instance_checker = instance_checker

        self._setup_paths()
        self._setup_theme()
        self._setup_tray_icon()
        self._build_services()
        self._build_modules()
        self._build_ui()
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
                self.base_dir, "resources", "icons", "icon.png"
            )
        self.icon_file = tray_icon_path

        logger.info("Base directory resolved to %s", self.base_dir)
        logger.info("Tray icon path resolved to %s", self.icon_file)

        # Apply icon cache TTL from settings (default 7 days)
        ttl_days = config_manager.get_settings().get("icon_cache_ttl_days", 7)
        self.icon_resolver.set_cache_ttl(ttl_days)

    def _setup_theme(self) -> None:
        """Construct ThemeManager and apply the configured theme."""
        self.theme_manager = ThemeManager(self.base_dir)
        settings = config_manager.get_settings()
        self.theme_manager.apply_theme(settings.get("theme", "system"))

    def _setup_tray_icon(self) -> None:
        """Create QSystemTrayIcon and configure application quit behaviour."""
        self.app.aboutToQuit.connect(self.cleanup)
        self.app.setQuitOnLastWindowClosed(False)

        tray_qicon = QIcon(self.icon_file)
        self.tray_icon = QSystemTrayIcon(tray_qicon)
        self.tray_icon.setIcon(tray_qicon)
        self.tray_icon.setVisible(True)

        self.menu = QMenu()
        self.output_windows: list = []
        self._running_processes: dict = {}
        self._running_action = None

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
            resolve_icon_path=self._resolve_icon_path,
        )

    def _build_modules(self) -> None:
        """Construct all feature module instances."""
        self.history_menu: list = []
        self.history = CommandHistory(self.services)
        self.creator = CommandCreator(self.services)
        self.executor = CommandExecutor(self.services)
        self.search = CommandSearch(self.services)
        self.backup = BackupRestore(self.services)
        self.importExport = ImportExport(self.services)
        self.favorites = Favorites(self.services)
        self.file_encryptor = FileEncryptor(self.services)
        self.schedule_creator = ScheduleCreator(self.services)
        self.schedule_viewer = ScheduleViewer(self.services)

    def _build_ui(self) -> None:
        """Construct UI widgets and register hotkeys."""
        settings = config_manager.get_settings()

        self.palette = CommandPalette(self.services)
        hotkey = settings.get("hotkey", "ctrl+shift+space")
        app_launcher_hotkey = settings.get("app_launcher_hotkey", "ctrl+alt+a")
        self.palette.register_hotkeys(hotkey, app_launcher_hotkey)

        self.quick_launch_bar = QuickLaunchBar(self.services, self.icon_file)
        bar_hotkey = settings.get("quick_launch_bar", {}).get("hotkey", "ctrl+shift+b")
        self.quick_launch_bar.register_hotkey(bar_hotkey)

    def _build_menu(self) -> None:
        """Build the tray context menu and attach it to the tray icon."""
        self.reload_commands()
        MenuBuilder(self).build(self.menu, self.command_menu)
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        self._update_tray_tooltip()

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
        """Set the tray tooltip to show the app name and the number of loaded commands."""
        try:
            count = len(self.get_all_commands())
            self.tray_icon.setToolTip(
                f"py-tray-command-launcher — {count} command(s) loaded"
            )
        except Exception:
            self.tray_icon.setToolTip("py-tray-command-launcher")


    # ------------------------------------------------------------------ #
    # Command execution                                                    #
    # ------------------------------------------------------------------ #

    def load_tray_menu(self):
        """Load commands into the tray menu."""
        self.reload_commands()
        MenuBuilder(self).build(self.menu, self.command_menu)

    def execute(self, title, command, confirm, show_output, prompt):
        """Execute a command with optional confirmation and input prompt."""
        history_entry = {
            "command": command,
            "title": title,
            "confirm": confirm,
            "showOutput": show_output,
            "prompt": prompt,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        config_manager.add_to_history(history_entry)

        if confirm:
            if not confirm_execute(command):
                return

        if prompt:
            input_value, ok = QInputDialog.getText(None, "Input Required", prompt)
            if not ok or not input_value:
                return
            command = command.replace("{promptInput}", input_value)

        if show_output:
            self.show_command_output(title, command)
        else:
            self.executor.execute_command(command)

        self.reload_history_commands()
        self.reload_favorites_commands()

    def show_command_output(self, title, command):
        """Execute a command, show output in RichOutputWindow, and update badge."""
        import uuid
        proc_id = str(uuid.uuid4())

        process = self.executor.execute_command_process(self.app, command)

        output_win = RichOutputWindow(self.app.activeWindow())
        tab = output_win.open_process_tab(title)
        self.output_windows.append(output_win)
        output_win.destroyed.connect(
            lambda _, w=output_win: self._on_output_window_closed(w)
        )

        output_win_ref = weakref.ref(output_win)

        def _on_stdout():
            output = process.readAllStandardOutput().data().decode(errors="replace")
            if not output:
                return
            win = output_win_ref()
            if win is not None:
                try:
                    win.append_output(tab, output)
                except RuntimeError as exc:
                    logger.debug("Output window destroyed before stdout could be written: %s", exc)

        def _on_stderr():
            output = process.readAllStandardError().data().decode(errors="replace")
            if not output:
                return
            win = output_win_ref()
            if win is not None:
                try:
                    win.append_output(tab, output)
                except RuntimeError as exc:
                    logger.debug("Output window destroyed before stderr could be written: %s", exc)

        process.readyReadStandardOutput.connect(_on_stdout)
        process.readyReadStandardError.connect(_on_stderr)

        self._running_processes[proc_id] = process
        self._update_tray_badge()

        def _on_finished():
            self._running_processes.pop(proc_id, None)
            self._update_tray_badge()

        def _on_error(error):
            logger.error(
                "QProcess error for command '%s': %s", command, error
            )
            win = output_win_ref()
            if win is not None:
                try:
                    win.append_output(tab, f"\n[ERROR] Process error: {error}\n")
                except RuntimeError:
                    pass
            self._running_processes.pop(proc_id, None)
            self._update_tray_badge()

        process.finished.connect(_on_finished)
        process.errorOccurred.connect(_on_error)
        # process.start() is called inside execute_command_process

    def _on_output_window_closed(self, win):
        """Remove a closed output window from the tracking list."""
        try:
            self.output_windows.remove(win)
        except ValueError:
            pass

    def _update_tray_badge(self):
        """Repaint the tray icon with a badge showing running process count."""
        count = len(self._running_processes)

        if self._running_action is not None:
            if count > 0:
                self._running_action.setText(f"Running: {count}")
                self._running_action.setVisible(True)
            else:
                self._running_action.setVisible(False)

        base = QPixmap(self.icon_file)
        if base.isNull():
            return

        if count == 0:
            self.tray_icon.setIcon(QIcon(base))
            return

        badge_size = max(base.width() // 3, 12)
        painter = QPainter(base)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bx = base.width() - badge_size - 1
        by = base.height() - badge_size - 1
        painter.setBrush(QColor("#e64553"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(bx, by, badge_size, badge_size)

        font = QFont()
        font.setPixelSize(max(badge_size - 4, 8))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("white"))
        painter.drawText(
            bx, by, badge_size, badge_size,
            Qt.AlignmentFlag.AlignCenter, str(count)
        )
        painter.end()

        self.tray_icon.setIcon(QIcon(base))

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
                    elif (
                        isinstance(item, dict)
                        and "command" not in item
                        and label != "icon"
                    ):
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
                subprocess.call(("open", str(commands_file)))     # noqa: S603, S607 — platform file-open helper, fixed args
            else:
                subprocess.call(("xdg-open", str(commands_file))) # noqa: S603, S607 — platform file-open helper, fixed args
        except Exception as e:
            show_error_and_raise(f"Failed to open commands file: {e}")

    def reload_commands(self, rebuild_menu: bool = False):
        """Reload the commands from the configuration file."""
        try:
            command_paths = config_manager.get_command_paths()
            logger.info(
                "Reloading commands from %s (config dir: %s)",
                command_paths["active_commands_file"],
                command_paths["config_dir"],
            )
            self.command_menu = config_manager.get_commands(refresh=True)

            if rebuild_menu:
                self.menu.clear()
                self.load_tray_menu()
                self.tray_icon.setContextMenu(self.menu)
                self._update_tray_tooltip()
        except ConfigurationError as e:
            show_error_and_raise(f"Failed to reload commands: {str(e)}")
            self.command_menu = {}

    def reload_history_commands(self):
        """Reload the history commands."""
        self.history.populate_menu(self.history_menu)

    def reload_favorites_commands(self):
        """Reload the favorites menu with current favorites."""
        self.favorites_menu.clear()
        self.favorites.populate_favorites_menu(self.favorites_menu)

    # ------------------------------------------------------------------ #
    # Dialog openers                                                       #
    # ------------------------------------------------------------------ #

    def _open_command_manager(self):
        """Open the Command Manager dialog."""

    # ------------------------------------------------------------------ #
    # Quick-Launch Bar pinning                                             #
    # ------------------------------------------------------------------ #

    def _pin_to_quick_launch(self, cmd_info: dict) -> None:
        """Add a command to the Quick-Launch Bar pinned list.

        If the entry is already pinned the call is a no-op and no dialog is shown.
        The Quick-Launch Bar widget is refreshed immediately if it is visible.
        """
        settings = config_manager.get_settings()
        qlb = settings.setdefault("quick_launch_bar", {})
        pinned: list = qlb.setdefault("pinned", [])
        entry = {
            "label": cmd_info.get("label", ""),
            "command": cmd_info.get("command", ""),
            "confirm": cmd_info.get("confirm", False),
            "showOutput": cmd_info.get("showOutput", False),
        }
        if entry in pinned:
            logger.debug("Command '%s' is already pinned to Quick-Launch Bar", entry["label"])
            return
        pinned.append(entry)
        config_manager.save_settings(settings)
        if hasattr(self, "quick_launch_bar") and self.quick_launch_bar:
            self.quick_launch_bar.refresh()
        logger.info("Pinned '%s' to Quick-Launch Bar", entry["label"])

        dlg = CommandManagerDialog(self.services, self._running_processes, parent=None)
        dlg.exec()

    def _open_settings(self):
        """Open the Settings dialog."""
        dlg = SettingsDialog(
            self.theme_manager,
            parent=None,
            hotkey_callback=self._reregister_hotkey,
            bar_hotkey_callback=self._reregister_bar_hotkey,
            app_launcher_hotkey_callback=self._reregister_app_launcher_hotkey,
        )
        dlg.exec()

    # ------------------------------------------------------------------ #
    # Hotkey re-registration                                               #
    # ------------------------------------------------------------------ #

    def _reregister_hotkey(self, hotkey: str) -> None:
        """Unregister the current palette hotkey and register the new one."""
        try:
            self.palette.register_hotkey(hotkey)
            logger.info("Palette hotkey re-registered: %s", hotkey)
        except Exception as exc:
            logger.warning("Failed to re-register palette hotkey '%s': %s", hotkey, exc)

    def _reregister_app_launcher_hotkey(self, hotkey: str) -> None:
        """Unregister the app launcher hotkey and register the new one."""
        try:
            self.palette.update_app_launcher_hotkey(hotkey)
            logger.info("App Launcher hotkey re-registered: %s", hotkey)
        except Exception as exc:
            logger.warning(
                "Failed to re-register app launcher hotkey '%s': %s", hotkey, exc
            )

    def _reregister_bar_hotkey(self, hotkey: str) -> None:
        """Unregister the current bar hotkey and register the new one."""
        try:
            self.quick_launch_bar.unregister_hotkey()
            self.quick_launch_bar.register_hotkey(hotkey)
            logger.info("Bar hotkey re-registered: %s", hotkey)
        except Exception as exc:
            logger.warning(
                "Failed to re-register bar hotkey '%s': %s", hotkey, exc
            )

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
        logger.info("Cleaning up before exit")
        for window in self.output_windows:
            window.close()
        self.palette.unregister_hotkey()
        self.quick_launch_bar.unregister_hotkey()
        self.quick_launch_bar.close()
        self.instance_checker.cleanup()

    def run(self):
        """Run the application event loop."""
        sys.exit(self.app.exec())
