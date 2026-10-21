# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit lazy construction and caching for feature and UI modules."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

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
from ui.command_palette import CommandPalette

if TYPE_CHECKING:
    from core.services import AppServices

logger = logging.getLogger(__name__)


class ModuleController:
    """Own cache-on-first-use factories without proxying module attributes."""

    def __init__(
        self,
        services: AppServices,
        icon_file: str,
        get_settings: Callable[[], dict],
    ) -> None:
        """Initialize empty feature and UI module slots."""
        self.services = services
        self.icon_file = icon_file
        self._get_settings = get_settings
        self._history: CommandHistory | None = None
        self._creator: CommandCreator | None = None
        self._executor: CommandExecutor | None = None
        self._search: CommandSearch | None = None
        self._backup: BackupRestore | None = None
        self._import_export: ImportExport | None = None
        self._favorites: Favorites | None = None
        self._file_encryptor: FileEncryptor | None = None
        self._schedule_creator: ScheduleCreator | None = None
        self._schedule_viewer: ScheduleViewer | None = None
        self._palette: CommandPalette | None = None

    def get_history(self) -> CommandHistory:
        """Return the cached history feature, constructing it on first access."""
        if self._history is None:
            self._history = CommandHistory(self.services)
        return self._history

    def get_creator(self) -> CommandCreator:
        """Return the cached command-creation feature."""
        if self._creator is None:
            self._creator = CommandCreator(self.services)
        return self._creator

    def get_executor(self) -> CommandExecutor:
        """Return the cached command-execution feature."""
        if self._executor is None:
            self._executor = CommandExecutor(self.services)
        return self._executor

    def get_search(self) -> CommandSearch:
        """Return the cached compatibility facade for the command palette."""
        if self._search is None:
            self._search = CommandSearch(
                self.services,
                show_palette=lambda: self.get_palette().show_palette(),
            )
        return self._search

    def get_backup(self) -> BackupRestore:
        """Return the cached backup/restore feature."""
        if self._backup is None:
            self._backup = BackupRestore(self.services)
        return self._backup

    def get_import_export(self) -> ImportExport:
        """Return the cached import/export feature."""
        if self._import_export is None:
            self._import_export = ImportExport(self.services)
        return self._import_export

    def get_favorites(self) -> Favorites:
        """Return the cached favorites feature."""
        if self._favorites is None:
            self._favorites = Favorites(self.services)
        return self._favorites

    def get_file_encryptor(self) -> FileEncryptor:
        """Return the cached file-encryption feature."""
        if self._file_encryptor is None:
            self._file_encryptor = FileEncryptor(self.services)
        return self._file_encryptor

    def get_schedule_creator(self) -> ScheduleCreator:
        """Return the cached schedule-creation feature."""
        if self._schedule_creator is None:
            self._schedule_creator = ScheduleCreator(self.services)
        return self._schedule_creator

    def get_schedule_viewer(self) -> ScheduleViewer:
        """Return the cached schedule-viewing feature."""
        if self._schedule_viewer is None:
            self._schedule_viewer = ScheduleViewer(self.services)
        return self._schedule_viewer

    def get_palette(self) -> CommandPalette:
        """Construct and cache the command palette with configured hotkeys."""
        if self._palette is None:
            settings = self._get_settings()
            self._palette = CommandPalette(self.services)
            self._palette.register_hotkeys(
                settings.get("hotkey", "ctrl+shift+space"),
                settings.get("app_launcher_hotkey", "ctrl+alt+a"),
            )
        return self._palette

    @property
    def loaded_palette(self) -> CommandPalette | None:
        """Return the palette if already constructed, without creating it."""
        return self._palette

    def cleanup(self) -> None:
        """Release loaded UI hotkeys without constructing modules."""
        if self._palette is not None:
            try:
                self._palette.unregister_hotkey()
            except Exception as exc:
                logger.debug("Palette hotkey cleanup error: %s", exc)
