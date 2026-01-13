"""
Configuration manager module for py-tray-command-launcher.

This module provides a central interface for all configuration operations,
including loading, saving, validating, and managing default configurations.
It follows the singleton pattern to ensure only one instance manages the config.
"""

import os
import sys
import json
import shutil
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Exception raised for configuration-related errors."""

    pass


class ConfigManager:
    """
    Singleton class that manages all configuration operations.

    This class handles loading, saving, validating, and managing defaults for
    all configuration files used by the application.
    """

    _instance = None

    def __new__(cls):
        """Ensure only one instance of ConfigManager exists."""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the config manager if it hasn't been initialized yet."""
        if self._initialized:
            return

        # Set up paths
        from utils.utils import get_base_dir
        self.base_dir = Path(get_base_dir())

        # Read-only bundled defaults inside the app image/bundle
        self.defaults_dir = self.base_dir / "config"

        # OS-appropriate user-writable config directory
        self.config_dir = self._get_user_config_dir()
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Backups under user config dir
        self.backup_dir = self.config_dir / "backups"

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Default config paths
        self.commands_file = self.config_dir / "commands.json"
        self.win_commands_file = self.config_dir / "win-commands.json"
        self.history_file = self.config_dir / "history.json"
        self.favorites_file = self.config_dir / "favorites.json"

        # Cache for loaded configurations
        self._commands_cache = None
        self._history_cache = None
        self._favorites_cache = None
        self._is_windows = os.name == "nt"

        # Mark as initialized
        self._initialized = True
        logger.info(f"ConfigManager initialized (config dir: {self.config_dir})")
        
        # Migrate existing favorites if needed
        self.migrate_favorites_from_commands()

    def get_commands(self, refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Get command configuration data.

        Args:
            refresh: If True, force reload from disk instead of using cache

        Returns:
            Dictionary containing command configuration

        Raises:
            ConfigurationError: If loading the configuration fails
        """
        if self._commands_cache is None or refresh:
            if self._is_windows and self.win_commands_file.exists():
                config_file = self.win_commands_file
            else:
                config_file = self.commands_file
            try:
                logger.debug(f"Loading commands from {config_file}")

                if not config_file.exists():
                    logger.warning(
                        f"Commands file {config_file} not found. Creating default."
                    )
                    self._create_default_commands(config_file)

                with open(config_file, "r", encoding="utf-8") as f:
                    commands = json.load(f)

                # Validate the configuration
                self._validate_commands(commands)

                self._commands_cache = commands
                logger.info(f"Commands loaded successfully from {config_file}")
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in {config_file}: {str(e)}"
                logger.error(error_msg)
                raise ConfigurationError(error_msg)
            except Exception as e:
                error_msg = f"Failed to load commands from {config_file}: {str(e)}"
                logger.error(error_msg)
                raise ConfigurationError(error_msg)

        return self._commands_cache

    def save_commands(self, commands: Dict[str, Dict[str, Any]]) -> None:
        """
        Save command configuration to file.

        Args:
            commands: Dictionary containing command configuration

        Raises:
            ConfigurationError: If saving the configuration fails
        """
        try:
            # Validate the configuration before saving
            self._validate_commands(commands)

            # Create a backup of the current configuration
            self.backup_commands()

            # Determine which file to save to
            config_file = (
                self.win_commands_file if self._is_windows else self.commands_file
            )

            # Save the configuration
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(commands, f, indent=4)

            # Update the cache
            self._commands_cache = commands
            logger.info(f"Commands saved successfully to {config_file}")
        except Exception as e:
            error_msg = f"Failed to save commands: {str(e)}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg)

    def get_history(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get command history data.

        Args:
            refresh: If True, force reload from disk instead of using cache

        Returns:
            List containing command history entries
        """
        if self._history_cache is None or refresh:
            try:
                if self.history_file.exists():
                    with open(self.history_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                else:
                    history = []

                self._history_cache = history
                logger.debug(f"History loaded successfully from {self.history_file}")
            except Exception as e:
                logger.warning(f"Failed to load history, using empty history: {str(e)}")
                self._history_cache = []

        return self._history_cache

    def save_history(self, history: List[Dict[str, Any]]) -> None:
        """
        Save command history to file.

        Args:
            history: List containing command history entries
        """
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)

            # Update the cache
            self._history_cache = history
            logger.debug(f"History saved successfully to {self.history_file}")
        except Exception as e:
            logger.error(f"Failed to save history: {str(e)}")

    def add_to_history(self, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Add an entry to the command history.

        Args:
            entry: Dictionary containing command history entry

        Returns:
            Updated history list
        """
        history = self.get_history()

        # Limit history to 10 items, excluding the current command
        history = [
            cmd for cmd in history if cmd.get("command") != entry.get("command")
        ][:9]

        # Add the new entry to the beginning
        history.insert(0, entry)

        # Save the updated history
        self.save_history(history)

        return history

    def clear_history(self) -> None:
        """Clear the command history."""
        self.save_history([])
        logger.info("Command history cleared")

    def get_favorites(self, refresh: bool = False) -> Dict[str, Any]:
        """
        Get favorites data.

        Args:
            refresh: If True, force reload from disk instead of using cache

        Returns:
            Dictionary containing favorites entries
        """
        if self._favorites_cache is None or refresh:
            try:
                if self.favorites_file.exists():
                    with open(self.favorites_file, "r", encoding="utf-8") as f:
                        favorites = json.load(f)
                else:
                    # Default empty favorites structure (no icon stored)
                    favorites = {}

                self._favorites_cache = favorites
                logger.debug(f"Favorites loaded successfully from {self.favorites_file}")
            except Exception as e:
                logger.warning(f"Failed to load favorites, using empty favorites: {str(e)}")
                self._favorites_cache = {}

        return self._favorites_cache

    def save_favorites(self, favorites: Dict[str, Any]) -> None:
        """
        Save favorites to file.

        Args:
            favorites: Dictionary containing favorites entries
        """
        try:
            with open(self.favorites_file, "w", encoding="utf-8") as f:
                json.dump(favorites, f, indent=4)

            # Update the cache
            self._favorites_cache = favorites
            logger.debug(f"Favorites saved successfully to {self.favorites_file}")
        except Exception as e:
            logger.error(f"Failed to save favorites: {str(e)}")

    def backup_commands(self) -> str:
        """
        Create a backup of the current commands configuration.

        Returns:
            Path to the backup file
        """
        try:
            # Determine which file to backup
            config_file = (
                self.win_commands_file if self._is_windows else self.commands_file
            )

            if not config_file.exists():
                logger.warning(f"Cannot backup non-existent file: {config_file}")
                return ""

            # Generate backup filename with timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"commands_{timestamp}.json"

            # Copy the commands file to the backup location
            shutil.copy2(config_file, backup_file)
            logger.info(f"Created backup at {backup_file}")

            return str(backup_file)
        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            return ""

    def list_backups(self) -> List[Tuple[str, str]]:
        """
        List all available backups.

        Returns:
            List of tuples containing (backup_file_path, formatted_timestamp)
        """
        backups = []

        try:
            # Get list of backup files
            backup_files = [
                f
                for f in os.listdir(self.backup_dir)
                if f.startswith("commands_") and f.endswith(".json")
            ]

            # Sort backup files by name (timestamp) in descending order
            backup_files.sort(reverse=True)

            for file in backup_files:
                # Extract timestamp and format it
                timestamp = file.replace("commands_", "").replace(".json", "")
                formatted_date = (
                    f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]} "
                    f"{timestamp[9:11]}:{timestamp[11:13]}:{timestamp[13:15]}"
                )

                backups.append((str(self.backup_dir / file), formatted_date))

            return backups
        except Exception as e:
            logger.error(f"Failed to list backups: {str(e)}")
            return []

    def restore_from_backup(self, backup_file: str) -> bool:
        """
        Restore commands from a backup file.

        Args:
            backup_file: Path to the backup file

        Returns:
            True if restoration was successful, False otherwise
        """
        try:
            # Create a backup of the current configuration first
            self.backup_commands()

            # Determine which file to restore to
            config_file = (
                self.win_commands_file if self._is_windows else self.commands_file
            )

            # Copy the backup file to the commands file
            shutil.copy2(backup_file, config_file)

            # Invalidate the cache
            self._commands_cache = None

            logger.info(f"Successfully restored from {backup_file} to {config_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore from backup: {str(e)}")
            return False

    def import_command_group(self, import_file: str, overwrite: bool = False) -> bool:
        """
        Import a command group from a JSON file.

        Args:
            import_file: Path to the import file
            overwrite: Whether to overwrite existing groups with the same name

        Returns:
            True if import was successful, False otherwise
        """
        try:
            # Read the import file
            with open(import_file, "r", encoding="utf-8") as f:
                import_data = json.load(f)

            if not isinstance(import_data, dict):
                logger.error(f"Invalid import file format: {import_file}")
                return False

            # Get current commands
            commands = self.get_commands()

            # Check for conflicts
            conflicts = []
            for group_name in import_data.keys():
                if group_name in commands and not overwrite:
                    conflicts.append(group_name)

            if conflicts:
                logger.warning(f"Import conflicts detected: {', '.join(conflicts)}")
                return False

            # Merge the import data with current commands
            for group_name, group_data in import_data.items():
                commands[group_name] = group_data

            # Save the updated commands
            self.save_commands(commands)

            logger.info(f"Successfully imported command groups from {import_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to import command group: {str(e)}")
            return False

    def export_command_group(self, group_name: str, export_file: str) -> bool:
        """
        Export a command group to a JSON file.

        Args:
            group_name: Name of the group to export
            export_file: Path to the export file

        Returns:
            True if export was successful, False otherwise
        """
        try:
            # Get current commands
            commands = self.get_commands()

            # Check if the group exists
            if group_name not in commands:
                logger.error(f"Group '{group_name}' not found")
                return False

            # Export the group to the file
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump({group_name: commands[group_name]}, f, indent=4)

            logger.info(f"Successfully exported group '{group_name}' to {export_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to export command group: {str(e)}")
            return False

    def add_to_favorites(
        self, command_path: str, custom_label: Optional[str] = None
    ) -> bool:
        """
        Add a command to favorites by reference instead of duplicating it.

        Args:
            command_path: Path to the command in format "Group.Subgroup.Command"
            custom_label: Optional custom label for the favorite

        Returns:
            True if addition was successful, False otherwise
        """
        try:
            # Get current commands to validate the path exists
            commands = self.get_commands()

            # Parse the command path
            path_parts = command_path.split(".")
            if len(path_parts) < 2:
                logger.error(f"Invalid command path: {command_path}")
                return False

            group = path_parts[0]
            if len(path_parts) == 2:
                # Direct command in a group
                command_name = path_parts[1]
                command_obj = commands.get(group, {}).get(command_name)
            else:
                # Nested command
                current = commands.get(group, {})
                for part in path_parts[1:-1]:
                    current = current.get(part, {})
                command_name = path_parts[-1]
                command_obj = current.get(command_name)

            if (
                not command_obj
                or not isinstance(command_obj, dict)
                or "command" not in command_obj
            ):
                logger.error(f"Command not found: {command_path}")
                return False

            # Use custom label or the original command name
            label = custom_label or command_name

            # Get current favorites
            favorites = self.get_favorites()

            # Add a reference entry to favorites (only store ref, resolve dynamically)
            favorites[label] = {
                "ref": command_path
            }

            # Save the updated favorites
            self.save_favorites(favorites)

            logger.info(
                f"Added reference '{label}' to Favorites pointing to {command_path}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add to favorites: {str(e)}")
            return False

    def remove_from_favorites(self, label: str) -> bool:
        """
        Remove a command from favorites.

        Args:
            label: Label of the favorite to remove

        Returns:
            True if removal was successful, False otherwise
        """
        try:
            # Get current favorites
            favorites = self.get_favorites()

            # Remove the command from favorites
            if label in favorites:
                del favorites[label]

                # Save the updated favorites
                self.save_favorites(favorites)

                logger.info(f"Removed '{label}' from Favorites")
                return True

            return False
        except Exception as e:
            logger.error(f"Failed to remove from favorites: {str(e)}")
            return False

    def migrate_favorites_from_commands(self) -> bool:
        """
        Migrate existing favorites from commands.json to the separate favorites.json file.
        
        This method is called during initialization to ensure existing favorites
        are moved to the new separate file structure.
        
        Returns:
            True if migration was successful or not needed, False if failed
        """
        try:
            # Get current commands to check for existing favorites
            commands = self.get_commands()
            
            # Check if there are favorites in the commands file
            if "Favorites" not in commands or len(commands["Favorites"]) <= 1:
                # No favorites to migrate (only icon or empty)
                return True
                
            logger.info("Migrating existing favorites from commands.json to favorites.json")
            
            # Extract favorites from commands (skip icon)
            favorites_to_migrate = {
                k: v for k, v in commands["Favorites"].items() 
                if k != "icon"
            }
            
            # Get existing favorites (might be empty)
            existing_favorites = self.get_favorites()
            
            # Merge with existing favorites (commands.json takes precedence for conflicts)
            for label, item in favorites_to_migrate.items():
                existing_favorites[label] = item
            
            # Save the merged favorites
            self.save_favorites(existing_favorites)
            
            # Remove favorites from commands.json
            del commands["Favorites"]
            self.save_commands(commands)
            
            logger.info("Successfully migrated favorites to separate file")
            return True
            
        except Exception as e:
            logger.error(f"Failed to migrate favorites: {str(e)}")
            return False

    def _validate_commands(self, commands: Dict[str, Dict[str, Any]]) -> None:
        """
        Validate command configuration structure.

        Args:
            commands: Dictionary containing command configuration

        Raises:
            ConfigurationError: If the configuration is invalid
        """
        if not isinstance(commands, dict):
            raise ConfigurationError("Commands must be a dictionary")

        for group_name, group_items in commands.items():
            if not isinstance(group_items, dict):
                raise ConfigurationError(f"Group '{group_name}' must be a dictionary")

            for item_name, item in group_items.items():
                if item_name == "icon":
                    continue

                if isinstance(item, dict) and "command" in item:
                    # This is a command entry, validate its structure
                    if not isinstance(item["command"], str):
                        raise ConfigurationError(
                            f"Command in '{group_name}.{item_name}' must be a string"
                        )

                    # Check optional fields have correct types
                    if "showOutput" in item and not isinstance(
                        item["showOutput"], bool
                    ):
                        raise ConfigurationError(
                            f"showOutput in '{group_name}.{item_name}' must be a boolean"
                        )

                    if "confirm" in item and not isinstance(item["confirm"], bool):
                        raise ConfigurationError(
                            f"confirm in '{group_name}.{item_name}' must be a boolean"
                        )

                    if "prompt" in item and not isinstance(item["prompt"], str):
                        raise ConfigurationError(
                            f"prompt in '{group_name}.{item_name}' must be a string"
                        )

    def _create_default_commands(self, config_file: Path) -> None:
        """
        Create a default commands configuration file.

        Args:
            config_file: Path to the configuration file to create
        """
        try:
            # Prefer copying bundled defaults from the app's config folder
            default_source = self.defaults_dir / config_file.name
            if default_source.exists():
                config_file.parent.mkdir(exist_ok=True)
                shutil.copy2(default_source, config_file)
                logger.info(f"Copied defaults {default_source} -> {config_file}")
                return

            # Fallback to minimal inline defaults
            default_commands = {
                "System": {
                    "icon": "icons/system.jpeg" if not self._is_windows else "",
                    "Open Terminal": {
                        "command": "terminator" if not self._is_windows else "cmd.exe",
                        "showOutput": False,
                        "confirm": False,
                    },
                    "System Info": {
                        "command": "uname -a" if not self._is_windows else "systeminfo",
                        "showOutput": True,
                        "confirm": False,
                    },
                },
                "Utilities": {
                    "icon": "icons/utilities.jpeg" if not self._is_windows else "",
                    "Text Editor": {
                        "command": "geany" if not self._is_windows else "notepad.exe",
                        "showOutput": False,
                        "confirm": False,
                    },
                },
            }

            config_file.parent.mkdir(exist_ok=True)
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(default_commands, f, indent=4)
            logger.info(f"Created default commands file at {config_file}")
        except Exception as e:
            logger.error(f"Failed to create default commands file: {str(e)}")

    def get_base_dir(self) -> str:
        """
        Get the base directory of the application (dev or packaged).

        Returns:
            Path to the base directory (handles PyInstaller sys._MEIPASS)
        """
        from utils.utils import get_base_dir
        return get_base_dir()

    def _get_user_config_dir(self) -> Path:
        """Return OS-appropriate user config directory for this app."""
        app_name = "py-tray-command-launcher"
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
            return base / app_name
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / app_name
        # Linux and others (XDG)
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / app_name


# Singleton instance
config_manager = ConfigManager()
