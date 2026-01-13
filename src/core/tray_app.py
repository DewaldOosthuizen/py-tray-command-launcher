from ast import Str
import os
import subprocess
import sys
import datetime
import json
import shutil
import urllib.request
import urllib.error
import hashlib
import tempfile
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QMessageBox, QInputDialog
from PyQt6.QtGui import QIcon, QAction

# Import ConfigManager instead of utils.utils
from core.config_manager import config_manager, ConfigurationError
from utils.dialogs import confirm_execute, show_error_and_raise, confirm_exit
from core.output_window import OutputWindow

# Modules for various functionalities
from modules.command_history import CommandHistory
from modules.command_creator import CommandCreator
from modules.command_executor import CommandExecutor
from modules.command_search import CommandSearch
from modules.backup_restore import BackupRestore
from modules.import_export import ImportExport
from modules.favorites import Favorites
from modules.file_encryptor import FileEncryptor
from modules.schedule_creator import ScheduleCreator
from modules.schedule_viewer import ScheduleViewer


class TrayApp:
    """Main tray application class that manages the system tray icon and menu."""

    def _resolve_tray_icon(self) -> str:
        """Resolve the tray icon path robustly across source, PyInstaller, and AppImage.

        Preference order:
        - PyInstaller bundle (sys._MEIPASS)/resources/icons/icon.png
        - Executable dir/resources/icons/icon.png (AppImage or system install)
        - Base dir/resources/icons/icon.png (source run)
        - AppImage top-level icon: ../../py-tray-command-launcher.png (from exe dir)
        - AppImage pixmap: ../share/pixmaps/py-tray-command-launcher.png (from exe dir)
        Returns the first existing path; otherwise returns an empty string.
        """
        candidates = []
        try:
            exe_dir = os.path.dirname(sys.executable)
        except Exception:
            exe_dir = ''

        # PyInstaller bundle
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidates.append(os.path.join(meipass, 'resources', 'icons', 'icon.png'))

        # Executable-relative (AppImage/system install)
        if exe_dir:
            candidates.append(os.path.join(exe_dir, 'resources', 'icons', 'icon.png'))
            candidates.append(os.path.join(exe_dir, 'resources', 'icon.png'))
            # AppImage common placements
            candidates.append(os.path.normpath(os.path.join(exe_dir, '..', '..', 'py-tray-command-launcher.png')))
            candidates.append(os.path.normpath(os.path.join(exe_dir, '..', 'share', 'pixmaps', 'py-tray-command-launcher.png')))

        # Source run (project base)
        candidates.append(os.path.join(self.base_dir, 'resources', 'icons', 'icon.png'))

        for p in candidates:
            if p and os.path.exists(p):
                return p
        return ''

    def _download_icon(self, url):
        """
        Download an icon from a URL and cache it locally.

        Args:
            url: The HTTP/HTTPS URL of the icon

        Returns:
            Local path to the downloaded icon, or None if download failed
        """
        try:
            # Create a cache directory for downloaded icons
            cache_dir = os.path.join(tempfile.gettempdir(), "py-tray-launcher-icons")
            os.makedirs(cache_dir, exist_ok=True)

            # Generate a filename based on URL hash to avoid conflicts
            url_hash = hashlib.md5(url.encode()).hexdigest()

            # Try to determine file extension from URL
            extension = ""
            url_lower = url.lower()
            if url_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico")):
                extension = url_lower.split(".")[-1]
            else:
                extension = "png"  # Default extension

            cached_file = os.path.join(cache_dir, f"{url_hash}.{extension}")

            # If file already cached and exists, return it
            if os.path.exists(cached_file):
                return cached_file

            # Download the icon
            with urllib.request.urlopen(url, timeout=10) as response:
                with open(cached_file, "wb") as f:
                    f.write(response.read())

            return cached_file

        except (urllib.error.URLError, urllib.error.HTTPError, OSError, Exception) as e:
            print(f"Failed to download icon from {url}: {str(e)}")
            return None

    def _resolve_icon_path(self, icon_path):
        """
        Resolve an icon path to an absolute path, handling relative paths,
        URLs, and base64 data URLs correctly.

        Args:
            icon_path: The icon path from configuration (can be relative,
                      absolute, URL, base64 data URL, or with ~)

        Returns:
            Absolute path to the icon file
        """
        if not icon_path:
            return self.icon_file

        # Handle base64 data URL (data:image/png;base64,...)
        if icon_path.startswith("data:image"):
            try:
                import base64
                import re
                match = re.match(r"data:image/(?P<ext>\w+);base64,(?P<data>.+)", icon_path)
                if not match:
                    return self.icon_file
                ext = match.group("ext")
                b64_data = match.group("data")
                cache_dir = os.path.join(tempfile.gettempdir(), "py-tray-launcher-icons")
                os.makedirs(cache_dir, exist_ok=True)
                url_hash = hashlib.md5(icon_path.encode()).hexdigest()
                cached_file = os.path.join(cache_dir, f"{url_hash}.{ext}")
                if not os.path.exists(cached_file):
                    with open(cached_file, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                return cached_file
            except Exception as e:
                print(f"Failed to decode base64 icon: {str(e)}")
                return self.icon_file

        # Check if it's a URL (starts with http or https)
        if icon_path.startswith(("http://", "https://")):
            downloaded_path = self._download_icon(icon_path)
            if downloaded_path and os.path.exists(downloaded_path):
                return downloaded_path
            return self.icon_file

        # Expand user path (handles ~)
        expanded_path = os.path.expanduser(icon_path)

        # If it's already absolute and exists, use as-is
        if os.path.isabs(expanded_path) and os.path.exists(expanded_path):
            return expanded_path

        # Try to resolve relative to PyInstaller bundle (sys._MEIPASS)
        import sys
        candidate_paths = []
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            candidate_paths.append(os.path.join(meipass, "resources", "icons", expanded_path))
            candidate_paths.append(os.path.join(meipass, "resources", expanded_path))
        # Try to resolve relative to executable (AppImage or system install)
        exe_dir = os.path.dirname(sys.executable)
        candidate_paths.append(os.path.join(exe_dir, "resources", "icons", expanded_path))
        candidate_paths.append(os.path.join(exe_dir, "resources", expanded_path))
        # Try to resolve relative to base_dir (source run)
        candidate_paths.append(os.path.join(self.base_dir, "resources", "icons", expanded_path))
        candidate_paths.append(os.path.join(self.base_dir, "resources", expanded_path))

        for path in candidate_paths:
            if os.path.exists(path):
                return path

        # Fallback to default icon
        return self.icon_file

    def __init__(self, app, instance_checker):
        """Initialize the TrayApp with the given QApplication instance."""
        self.app = app
        self.instance_checker = instance_checker
        
        # Initialize paths
        self.base_dir = config_manager.get_base_dir()
        # Resolve a robust tray icon path that works in all packaging modes
        tray_icon_path = self._resolve_tray_icon()
        if not tray_icon_path:
            tray_icon_path = os.path.join(self.base_dir, "resources", "icons", "icon.png")
        self.icon_file = tray_icon_path
        print(f"Base Directory: {self.base_dir}")
        print(f"Icon file: {self.icon_file}")
        
        self.app.aboutToQuit.connect(self.cleanup)
        # Keep the app running even if all windows are closed
        self.app.setQuitOnLastWindowClosed(False)

        # Initialize tray icon and menu
        tray_qicon = QIcon(self.icon_file)
        self.tray_icon = QSystemTrayIcon(tray_qicon)
        # Some environments require explicitly setting the icon after creation
        self.tray_icon.setIcon(tray_qicon)
        self.tray_icon.setVisible(True)
        self.menu = QMenu()
        self.output_windows = []

        # Initialize module components
        try:
            self.command_menu = config_manager.get_commands()
        except ConfigurationError as e:
            show_error_and_raise(f"Failed to load commands: {str(e)}")
            self.command_menu = {}

        self.history_menu = []
        self.history = CommandHistory(self)
        self.creator = CommandCreator(self)
        self.executor = CommandExecutor(self)
        self.search = CommandSearch(self)
        self.backup = BackupRestore(self)
        self.importExport = ImportExport(self)
        self.favorites = Favorites(self)
        self.file_encryptor = FileEncryptor(self)
        self.schedule_creator = ScheduleCreator(self)
        self.schedule_viewer = ScheduleViewer(self)

        # Load menu and set up tray icon
        self.load_tray_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    # Core menu handling methods
    def load_tray_menu(self):
        """Load commands into the tray menu."""
        self.reload_commands()

        # Check if commands is a dictionary
        if not isinstance(self.command_menu, dict):
            show_error_and_raise(
                "Invalid commands configuration. Root element must be a dictionary."
            )

        # Iterate over the commands and create menu items
        for group, items in self.command_menu.items():
            # Check if each group is a dictionary
            if not isinstance(items, dict):
                show_error_and_raise(
                    f"Invalid command group format: {group}. Each group must be a dictionary."
                )

            # Resolve the icon path correctly
            icon_path = self._resolve_icon_path(items.get("icon"))

            # Check if the icon file exists, else default to self.icon_file
            if icon_path != self.icon_file and not os.path.isfile(icon_path):
                icon_path = self.icon_file

            # Create a submenu for each group
            submenu = QMenu(group, self.menu)
            submenu.setIcon(QIcon(icon_path))

            # Recursively add items to the submenu
            self.add_menu_items(submenu, items, icon_path)

            self.menu.addMenu(submenu)

        # Add favorites menu
        self.favorites_menu = QMenu("Favorites", self.menu)
        self.favorites_menu.setIcon(QIcon(self.icon_file))
        self.favorites.populate_favorites_menu(self.favorites_menu)
        self.menu.addMenu(self.favorites_menu)

        # Add history menu
        self.history_menu = QMenu("Recent Commands", self.menu)
        self.history_menu.setIcon(QIcon(self.icon_file))
        self.menu.addMenu(self.history_menu)
        self.reload_history_commands()
        self.reload_favorites_commands()

        self.menu.addSeparator()

        # Commands group
        commands_menu = QMenu("Commands", self.menu)
        commands_menu.setIcon(QIcon(self.icon_file))
        commands_menu.addAction("Search Commands", self.search.show_dialog)
        commands_menu.addAction("Create New Command", self.creator.show_dialog)
        commands_menu.addAction("Edit commands.json", self.open_commands_json)
        commands_menu.addAction("Reload Commands", self.reload_commands)
        commands_menu.addAction("Reload History Commands", self.reload_history_commands)
        commands_menu.addAction("Add to Favorites", self.favorites.add_to_favorites)
        self.menu.addMenu(commands_menu)

        # Tools group
        tools_menu = QMenu("Tools", self.menu)
        tools_menu.setIcon(QIcon(self.icon_file))

        # Import/Export submenu
        import_export_menu = QMenu("Import/Export", tools_menu)
        import_export_menu.setIcon(QIcon(self.icon_file))
        import_export_menu.addAction(
            "Import Command Group", self.importExport.import_command_group
        )
        import_export_menu.addAction(
            "Export Command Group", self.importExport.export_command_group
        )
        tools_menu.addMenu(import_export_menu)

        # Backup/Restore submenu
        backup_restore_menu = QMenu("Backup/Restore", tools_menu)
        backup_restore_menu.setIcon(QIcon(self.icon_file))
        backup_restore_menu.addAction("Backup Commands", self.backup.backup_commands)
        backup_restore_menu.addAction("Restore Commands", self.backup.restore_commands)
        tools_menu.addMenu(backup_restore_menu)

        # Encryption submenu
        encryption_menu = QMenu("Encrypt/Decrypt", tools_menu)
        encryption_menu.setIcon(QIcon(self.icon_file))
        encryption_menu.addAction(
            "Encrypt File/Folder", self.file_encryptor.encrypt_file_or_folder
        )
        encryption_menu.addAction(
            "Decrypt File/Folder", self.file_encryptor.decrypt_file_or_folder
        )
        tools_menu.addMenu(encryption_menu)

        # Add Create Schedule option
        tools_menu.addAction("Create Schedule", self.schedule_creator.show_dialog)
        
        # Add View Schedules option
        tools_menu.addAction("View Schedules", self.schedule_viewer.show_dialog)

        self.menu.addMenu(tools_menu)
        self.menu.addAction("Restart App", self.restart_app)
        self.menu.addAction("Exit", self.confirm_exit)

    def add_menu_items(self, menu, items, parent_icon_path, group_name=""):
        """Recursively add items to the menu."""
        for label, item in items.items():
            # Skip the icon entry
            if label == "icon":
                continue

            # Handle submenu case (nested dictionaries without command and not a reference)
            if isinstance(item, dict) and "command" not in item and "ref" not in item:
                # Create submenu for nested dictionaries
                # If the item has an "icon" key, use it; otherwise inherit from parent
                if "icon" in item:
                    icon_path = self._resolve_icon_path(item.get("icon"))
                    # If the resolved icon path doesn't exist or resolution failed, fall back to parent
                    if not icon_path or not os.path.isfile(icon_path):
                        icon_path = parent_icon_path
                else:
                    # No icon specified, inherit from parent
                    icon_path = parent_icon_path

                submenu = QMenu(label, menu)
                submenu.setIcon(QIcon(icon_path))
                new_group = label if not group_name else f"{group_name} → {label}"
                self.add_menu_items(submenu, item, icon_path, new_group)
                menu.addMenu(submenu)

            # Handle command case (direct commands or references)
            elif isinstance(item, dict) and ("command" in item or "ref" in item):
                # Add command item to menu
                self._add_command_to_menu(
                    menu, label, item, parent_icon_path, group_name
                )

                # # Add "Add to Favorites" as a submenu action for non-favorites
                # if group_name != "Favorites" and action is not None:
                #     add_to_fav_action = QAction("Add to Favorites", menu)
                #     add_to_fav_action.triggered.connect(
                #         lambda checked=False, cmd_info={"group": group_name, "label": label}:
                #         self.favorites.add_to_favorites_directly(cmd_info["group"], cmd_info["label"])
                #     )
                #     # Insert the "Add to Favorites" action right after the command action
                #     menu.addAction(add_to_fav_action)

    def _resolve_command_reference(self, group, label, item):
        """
        Resolve a command reference to get the actual command data.

        Args:
            group: The group name (e.g., 'Favorites')
            label: The command label
            item: The command item data

        Returns:
            The resolved command data dictionary
        """
        if isinstance(item, dict) and "ref" in item:
            try:
                # This is a reference, resolve it
                ref_path = item["ref"]
                path_parts = ref_path.split(".")
                if len(path_parts) < 2:
                    print(f"Invalid reference path: {ref_path}")
                    return item

                ref_group = path_parts[0]
                commands = self.command_menu

                if ref_group not in commands:
                    print(f"Referenced group not found: {ref_group}")
                    return item

                if len(path_parts) == 2:
                    # Direct command in a group
                    ref_command = path_parts[1]
                    resolved = commands[ref_group].get(ref_command, {})
                else:
                    # Nested command
                    current = commands[ref_group]
                    for part in path_parts[1:-1]:
                        if part not in current:
                            print(f"Referenced path part not found: {part}")
                            return item
                        current = current[part]
                    ref_command = path_parts[-1]
                    resolved = current.get(ref_command, {})

                # Validate the resolved command
                if isinstance(resolved, dict) and "command" in resolved:
                    return resolved
                else:
                    print(f"Referenced command is invalid: {ref_path}")
                    return item
            except Exception as e:
                print(f"Error resolving reference: {str(e)}")
                return item

        return item

    def _add_command_to_menu(self, menu, label, item, parent_icon_path, group_name=""):
        """
        Add a command item to the menu.

        Returns:
            The created QAction object
        """
        # Check if this is a reference and resolve it
        if isinstance(item, dict) and "ref" in item:
            resolved_item = self._resolve_command_reference(group_name, label, item)
            if resolved_item != item:
                # Use the resolved item but keep track of the reference
                command = resolved_item.get("command", "")
                # If the resolved item has an icon, use it; otherwise inherit from parent
                if "icon" in resolved_item:
                    icon_path = self._resolve_icon_path(resolved_item.get("icon"))
                    # If the resolved icon path doesn't exist or resolution failed, fall back to parent
                    if not icon_path or not os.path.isfile(icon_path):
                        icon_path = parent_icon_path
                else:
                    # No icon specified in resolved item, inherit from parent
                    icon_path = parent_icon_path
                show_output = resolved_item.get("showOutput", False)
                confirm = resolved_item.get("confirm", False)
                prompt = resolved_item.get("prompt", None)

                # Create action with reference indicator
                action = QAction(QIcon(icon_path), f"{label}", menu)

                # Connect the action to execute command
                action.triggered.connect(
                    lambda checked=False, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: self.execute(
                        lbl, cmd, conf, show, prmpt
                    )
                )

                # QAction does not support context menus directly; consider adding a "Remove from Favorites" action elsewhere if needed.
                menu.addAction(action)
                return action

        # Regular command processing
        command = item.get("command")

        # Validate required fields
        if not command:
            show_error_and_raise(
                f"Invalid command format in commands.json: {label}. 'command' is required."
            )

        # If the item has an "icon" key, use it; otherwise inherit from parent
        if "icon" in item:
            icon_path = self._resolve_icon_path(item.get("icon"))
            # If the resolved icon path doesn't exist or resolution failed, fall back to parent
            if not icon_path or not os.path.isfile(icon_path):
                icon_path = parent_icon_path
        else:
            # No icon specified, inherit from parent
            icon_path = parent_icon_path

        show_output = item.get("showOutput", False)
        confirm = item.get("confirm", False)
        prompt = item.get("prompt", None)
        action = QAction(QIcon(icon_path), label, menu)

        # Connect the action to execute command
        action.triggered.connect(
            lambda checked=False, cmd=command, lbl=label, conf=confirm, show=show_output, prmpt=prompt: self.execute(
                lbl, cmd, conf, show, prmpt
            )
        )

        menu.addAction(action)
        return action

    # Command execution methods
    def execute(self, title, command, confirm, show_output, prompt):
        """Execute a command with optional confirmation and input prompt."""
        # Add to history
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

        self.reload_commands()
        self.reload_history_commands()
        self.reload_favorites_commands()

    def show_command_output(self, title, command):
        """Execute a command and show the output in a new window."""
        process = self.executor.execute_command_process(self.app, command)

        def handle_finished(exit_code, exit_status):
            stdout = process.readAllStandardOutput().data().decode()
            stderr = process.readAllStandardError().data().decode()
            output = stdout if stdout else stderr
            output_window = OutputWindow(title, output, parent=self.app.activeWindow())
            self.output_windows.append(output_window)
            output_window.destroyed.connect(
                lambda _,: (
                    self.output_windows.remove(output_window)
                    if output_window in self.output_windows
                    else None
                )
            )
            output_window.show()

        process.finished.connect(handle_finished)
        process.start()

    # Utility methods
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
                        # For nested menus
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
        """Open the commands.json file with the default text editor."""
        commands_file = config_manager.commands_file
        try:
            # Open the commands.json file with the default text editor
            if sys.platform == "win32":
                os.startfile(commands_file)
            elif sys.platform == "darwin":
                subprocess.call(("open", str(commands_file)))
            else:
                subprocess.call(("xdg-open", str(commands_file)))
        except Exception as e:
            show_error_and_raise(f"Failed to open commands file: {e}")

    def reload_commands(self):
        """Reload the commands from the configuration file."""
        try:
            self.command_menu = config_manager.get_commands(refresh=True)
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

    def restart_app(self):
        """Restart the application."""
        self.cleanup()
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def confirm_exit(self):
        """Show confirmation dialog for exiting the application."""
        if confirm_exit():
            self.app.quit()

    def cleanup(self):
        """Perform any cleanup before quitting."""
        print("Cleaning up before exit...")
        for window in self.output_windows:
            window.close()
        # Always clear single instance lock and PID file
        self.instance_checker.cleanup()

    def run(self):
        """Run the application event loop."""
        sys.exit(self.app.exec())
