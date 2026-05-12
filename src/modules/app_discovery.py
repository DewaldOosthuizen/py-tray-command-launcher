# SPDX-License-Identifier: GPL-3.0-or-later

"""
AppDiscovery — scans installed .desktop files and provides fuzzy search over
installed applications for the App Launcher feature.

Public API
----------
``app_discovery``
    Module-level singleton.  Call ``app_discovery.get_all()`` to obtain the
    cached list of :class:`AppEntry` objects, or ``app_discovery.search(query)``
    for a scored, filtered subset.
"""

import configparser
import logging
import os
import re
import shlex
import shutil
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap

logger = logging.getLogger(__name__)

IS_WINDOWS = sys.platform == "win32"

try:
    from rapidfuzz import fuzz as _fuzz
    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False


def _score(query: str, text: str) -> float:
    if _FUZZY_AVAILABLE:
        return _fuzz.WRatio(query, text)
    return 100.0 if query.lower() in text.lower() else 0.0


# Preferred icon sizes to try when scanning icon theme directories
_PREFERRED_SIZES = ("48x48", "32x32", "64x64", "scalable", "24x24", "22x22", "16x16")
_ICON_EXTS = (".png", ".svg", ".xpm")

# Terminal emulators to try (in preference order)
_TERMINAL_EMULATORS = [
    "x-terminal-emulator",
    "gnome-terminal",
    "xfce4-terminal",
    "konsole",
    "xterm",
    "lxterminal",
    "tilix",
    "alacritty",
    "kitty",
]


@dataclass
class AppEntry:
    """Represents a single installed application parsed from a .desktop file."""

    name: str
    exec_cmd: str
    icon_name: str
    categories: List[str] = field(default_factory=list)
    terminal: bool = False

    @property
    def categories_str(self) -> str:
        return ", ".join(self.categories) if self.categories else ""


class AppDiscovery:
    """Discovers installed applications via XDG .desktop files."""

    def __init__(self):
        self._apps: Optional[List[AppEntry]] = None
        # icon_name → resolved absolute path; built once in a background thread
        self._icon_path_index: Dict[str, str] = {}
        # cache_key → QPixmap; eliminates repeated disk I/O on every keystroke
        self._pixmap_cache: Dict[str, QPixmap] = {}
        if not IS_WINDOWS:
            threading.Thread(
                target=self._build_icon_index, daemon=True, name="icon-index"
            ).start()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Populate the internal cache; dispatches to the platform loader."""
        if IS_WINDOWS:
            self._load_windows()
        else:
            self._load_linux()

    # ------------------------------------------------------------------
    # Platform loaders
    # ------------------------------------------------------------------

    def _load_linux(self) -> None:
        """Scan XDG application directories (.desktop files)."""
        search_dirs = []

        xdg_data_home = os.environ.get(
            "XDG_DATA_HOME", str(Path.home() / ".local" / "share")
        )
        search_dirs.append(Path(xdg_data_home) / "applications")

        xdg_data_dirs = os.environ.get(
            "XDG_DATA_DIRS", "/usr/local/share:/usr/share"
        )
        for d in xdg_data_dirs.split(":"):
            if d.strip():
                search_dirs.append(Path(d.strip()) / "applications")

        apps: List[AppEntry] = []
        seen_names: set = set()

        for directory in search_dirs:
            if not directory.is_dir():
                continue
            for desktop_file in sorted(directory.glob("*.desktop")):
                entry = self._parse_desktop_file(desktop_file)
                if entry is not None and entry.name not in seen_names:
                    seen_names.add(entry.name)
                    apps.append(entry)

        apps.sort(key=lambda a: a.name.lower())
        self._apps = apps
        logger.info("AppDiscovery (Linux): loaded %d applications", len(apps))

    def _load_windows(self) -> None:
        """Scan Windows Start Menu .lnk shortcuts from user and system locations."""
        search_dirs = []

        appdata = os.environ.get("APPDATA", "")
        if appdata:
            search_dirs.append(
                Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            )

        programdata = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        search_dirs.append(
            Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        )

        apps: List[AppEntry] = []
        seen_names: set = set()

        for base_dir in search_dirs:
            if not base_dir.is_dir():
                continue
            for lnk_file in sorted(base_dir.rglob("*.lnk")):
                name = lnk_file.stem
                if name in seen_names:
                    continue
                # Derive category from the sub-folder relative to the Programs root
                rel = lnk_file.relative_to(base_dir)
                categories = [p for p in rel.parts[:-1] if p]
                seen_names.add(name)
                lnk_path = str(lnk_file)
                apps.append(AppEntry(
                    name=name,
                    exec_cmd=lnk_path,   # launched via os.startfile()
                    icon_name=lnk_path,  # resolved via QFileIconProvider
                    categories=categories,
                    terminal=False,
                ))

        apps.sort(key=lambda a: a.name.lower())
        self._apps = apps
        logger.info("AppDiscovery (Windows): loaded %d applications", len(apps))

    def _parse_desktop_file(self, path: Path) -> Optional[AppEntry]:
        """Parse a single .desktop file; returns None if the entry should be hidden."""
        parser = configparser.RawConfigParser(strict=False)
        parser.optionxform = str  # preserve case
        try:
            parser.read(str(path), encoding="utf-8")
        except Exception as exc:
            logger.debug("Skipping %s: %s", path, exc)
            return None

        section = "Desktop Entry"
        if not parser.has_section(section):
            return None

        def get(key, fallback=""):
            return parser.get(section, key, fallback=fallback)

        def getbool(key, fallback=False):
            try:
                return parser.getboolean(section, key, fallback=fallback)
            except Exception:
                return fallback

        if get("Type") != "Application":
            return None
        if getbool("NoDisplay"):
            return None
        if getbool("Hidden"):
            return None

        name = get("Name")
        exec_cmd = get("Exec")
        if not name or not exec_cmd:
            return None

        icon_name = get("Icon")
        terminal = getbool("Terminal")
        raw_categories = get("Categories")
        categories = [
            c.strip() for c in raw_categories.split(";") if c.strip()
        ] if raw_categories else []

        return AppEntry(
            name=name,
            exec_cmd=exec_cmd,
            icon_name=icon_name,
            categories=categories,
            terminal=terminal,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all(self) -> List[AppEntry]:
        """Return all discovered apps, loading on first call."""
        if self._apps is None:
            self.load()
        return self._apps

    def search(self, query: str) -> List[AppEntry]:
        """Return apps matching *query*, scored and sorted by relevance.

        When *query* is blank all apps are returned alphabetically.
        """
        apps = self.get_all()
        if not query.strip():
            return apps

        q = query.strip()
        scored = []
        for app in apps:
            text = f"{app.name} {app.categories_str}"
            s = _score(q, text)
            if s > 30 or q.lower() in app.name.lower():
                scored.append((s, app))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [app for _s, app in scored]

    # ------------------------------------------------------------------
    # Icon resolution
    # ------------------------------------------------------------------

    def resolve_icon_pixmap(self, icon_name: str, size: int = 32) -> QPixmap:
        """Return a QPixmap for *icon_name*, using a per-instance cache.

        Only *successful* resolutions are cached.  Fallbacks are never stored
        so that if the background icon index is still building on first open,
        the next repopulation (triggered by the debounce timer) will retry and
        find the real icon once the index is ready.
        """
        if not icon_name:
            return self._fallback_pixmap(size)

        cache_key = f"{icon_name}\x00{size}"
        cached = self._pixmap_cache.get(cache_key)
        if cached is not None:
            return cached

        px = self._find_pixmap(icon_name, size)
        if px is not None:
            self._pixmap_cache[cache_key] = px
            return px
        return self._fallback_pixmap(size)

    def _find_pixmap(self, icon_name: str, size: int) -> Optional[QPixmap]:
        """Return a QPixmap for *icon_name*, or ``None`` if not found.

        Resolution order:
        1. Windows — QFileIconProvider (delegates to the shell).
        2. Absolute path on disk.
        3. ``QIcon.fromTheme`` — Qt's own XDG resolver; internally cached by
           Qt so repeated calls for the same name are O(1).  This works even
           before the background index thread has finished.
        4. Background file index — catches icons that Qt's theme DB misses
           (e.g. older packages that don't register in the active theme).
        """
        # 1. Windows: delegate to QFileIconProvider
        if IS_WINDOWS and os.path.isfile(icon_name):
            try:
                from PyQt6.QtCore import QFileInfo
                from PyQt6.QtWidgets import QFileIconProvider
                provider = QFileIconProvider()
                px = provider.icon(QFileInfo(icon_name)).pixmap(size, size)
                if not px.isNull():
                    return px
            except Exception as exc:
                logger.debug("QFileIconProvider failed for %s: %s", icon_name, exc)
            return None

        # 2. Absolute path on disk
        if os.path.isabs(icon_name) and os.path.isfile(icon_name):
            px = QPixmap(icon_name)
            if not px.isNull():
                return self._scale(px, size)

        # 3. Qt's own XDG theme resolver — fast, correct, no index required
        qt_icon = QIcon.fromTheme(icon_name)
        if not qt_icon.isNull():
            px = qt_icon.pixmap(size, size)
            if not px.isNull():
                return px

        # 4. Background file index (supplementary; catches theme-unregistered icons)
        path = self._icon_path_index.get(icon_name)
        if path:
            px = QPixmap(path)
            if not px.isNull():
                return self._scale(px, size)

        return None

    def _scale(self, px: QPixmap, size: int) -> QPixmap:
        """Scale *px* to *size*\u00d7*size* preserving aspect ratio."""
        if hasattr(Qt, "AspectRatioMode"):
            return px.scaled(
                size, size,
                aspectRatioMode=Qt.AspectRatioMode.KeepAspectRatio,
                transformMode=Qt.TransformationMode.SmoothTransformation,
            )
        return px

    def _build_icon_index(self) -> None:
        """Scan XDG icon directories once and populate *_icon_path_index*.

        Runs in a background daemon thread started at module import so the
        index is likely complete before the user first opens the Apps tab.
        Uses first-wins strategy: hicolor at preferred sizes is scanned first
        so higher-quality icons take priority over lower-resolution variants.
        """
        index: Dict[str, str] = {}

        xdg_data_home = os.environ.get(
            "XDG_DATA_HOME", str(Path.home() / ".local" / "share")
        )
        xdg_data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share")
        all_icon_bases = [Path(xdg_data_home) / "icons"] + [
            Path(d.strip()) / "icons"
            for d in xdg_data_dirs.split(":")
            if d.strip()
        ]

        def _index_dir(directory: Path) -> None:
            try:
                for f in directory.iterdir():
                    if f.is_file() and f.suffix in _ICON_EXTS:
                        index.setdefault(f.stem, str(f))
            except OSError:
                pass

        # Pass 1 — hicolor at preferred sizes (first-wins → best quality wins)
        for base in all_icon_bases:
            hicolor = base / "hicolor"
            for size_name in _PREFERRED_SIZES:
                for category in ("apps", "applications", ""):
                    d = hicolor / size_name / category if category else hicolor / size_name
                    _index_dir(d)

        # Pass 2 — remaining installed themes at preferred sizes
        for base in all_icon_bases:
            if not base.is_dir():
                continue
            try:
                for theme in sorted(base.iterdir()):
                    if not theme.is_dir() or theme.name == "hicolor":
                        continue
                    for size_name in _PREFERRED_SIZES:
                        for category in ("apps", "applications", ""):
                            d = theme / size_name / category if category else theme / size_name
                            _index_dir(d)
            except OSError:
                pass

        # Pass 3 — /usr/share/pixmaps (catch-all for older packages)
        _index_dir(Path("/usr/share/pixmaps"))

        # Atomic replacement so readers always see a complete dict
        self._icon_path_index = index
        logger.info("AppDiscovery: icon index built — %d icons indexed", len(index))

    def _fallback_pixmap(self, size: int) -> QPixmap:
        """Return a generic application pixmap."""
        px = QIcon.fromTheme("application-x-executable").pixmap(size, size)
        if px.isNull():
            px = QIcon.fromTheme("application").pixmap(size, size)
        return px

    # ------------------------------------------------------------------
    # Exec handling
    # ------------------------------------------------------------------

    @staticmethod
    def clean_exec(exec_cmd: str) -> str:
        """Strip .desktop field codes (%f, %u, etc.) from an Exec value."""
        return re.sub(r'%[fFuUdDnNickv]', '', exec_cmd).strip()

    @staticmethod
    def build_launch_args(entry: AppEntry) -> Optional[List[str]]:
        """Build the argv list for launching *entry*.

        Handles ``Terminal=true`` by prepending a detected terminal emulator.
        Returns ``None`` if no terminal emulator can be found for terminal apps.
        """
        cleaned = AppDiscovery.clean_exec(entry.exec_cmd)
        if not cleaned:
            return None
        try:
            args = shlex.split(cleaned)
        except ValueError as exc:
            logger.warning("Failed to parse Exec for %s: %s", entry.name, exc)
            args = [cleaned]

        if entry.terminal:
            terminal = None
            for candidate in _TERMINAL_EMULATORS:
                found = shutil.which(candidate)
                if found:
                    terminal = found
                    break
            if terminal is None:
                logger.warning(
                    "No terminal emulator found for terminal app %s", entry.name
                )
                return None
            args = [terminal, "-e"] + args

        return args

    @staticmethod
    def is_windows_lnk_entry(entry: "AppEntry") -> bool:
        """Return True if *entry* was discovered from a Windows .lnk shortcut."""
        return IS_WINDOWS and entry.exec_cmd.lower().endswith(".lnk")


# Module-level singleton
app_discovery = AppDiscovery()
