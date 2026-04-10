#  SPDX-License-Identifier: GPL-3.0-or-later

"""
ThemeManager — loads a QSS stylesheet from resources/themes/ and applies it
globally via QApplication.setStyleSheet.

Supported theme values in settings.json:
  "dark"   → resources/themes/dark.qss
  "light"  → resources/themes/light.qss
  "system" → no custom stylesheet (uses native Qt platform theme)

If the configured QSS file is missing the manager falls back to "system" and
logs a warning so the application never crashes on a missing theme file.
"""

import logging
import os
import sys

from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


class ThemeManager:
    """Manages QSS-based theming for the application."""

    _THEME_FILES = {
        "dark": "dark.qss",
        "light": "light.qss",
    }

    def __init__(self, base_dir: str):
        """
        Args:
            base_dir: The application base directory (project root in source
                      runs, sys._MEIPASS in PyInstaller bundles).
        """
        self._base_dir = base_dir
        self._current_theme: str = "system"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_theme(self, theme: str) -> None:
        """Apply *theme* to the running QApplication.

        Args:
            theme: ``"dark"``, ``"light"``, or ``"system"``.
        """
        theme = (theme or "system").lower().strip()
        self._current_theme = theme

        if theme == "system":
            QApplication.instance().setStyleSheet("")
            logger.info("Theme set to system (no custom QSS)")
            return

        qss_path = self._resolve_qss_path(theme)
        if not qss_path:
            logger.warning(
                "QSS file for theme '%s' not found; falling back to system theme", theme
            )
            QApplication.instance().setStyleSheet("")
            self._current_theme = "system"
            return

        try:
            with open(qss_path, "r", encoding="utf-8") as fh:
                stylesheet = fh.read()
            QApplication.instance().setStyleSheet(stylesheet)
            logger.info("Applied theme '%s' from %s", theme, qss_path)
        except OSError as exc:
            logger.warning(
                "Failed to read QSS file '%s': %s; falling back to system theme",
                qss_path,
                exc,
            )
            QApplication.instance().setStyleSheet("")
            self._current_theme = "system"

    @property
    def current_theme(self) -> str:
        """The name of the currently active theme."""
        return self._current_theme

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_qss_path(self, theme: str) -> str | None:
        """Return the absolute path to the QSS file for *theme*, or None."""
        filename = self._THEME_FILES.get(theme)
        if not filename:
            return None

        candidates = []

        # PyInstaller bundle
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "resources", "themes", filename))

        # Executable-relative (AppImage / system install)
        try:
            exe_dir = os.path.dirname(sys.executable)
            candidates.append(os.path.join(exe_dir, "resources", "themes", filename))
        except Exception:
            pass

        # Source run
        candidates.append(os.path.join(self._base_dir, "resources", "themes", filename))

        for path in candidates:
            if path and os.path.isfile(path):
                return path

        return None
