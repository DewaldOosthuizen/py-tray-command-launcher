# SPDX-License-Identifier: GPL-3.0-or-later

"""
SettingsDialog — GUI for editing application settings stored in settings.json.

Covers:
  • Theme selection (dark / light / system)
  • Global hotkey string
  • Logging level
  • History size cap
  • Output font family and size
  • Quick-launch bar visibility toggle
"""

import logging

from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.quick_launch_pin_manager import QuickLaunchPinManager
from utils.dialogs import show_error

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog covering theme, hotkey, logging, history, and output font."""

    def __init__(
        self,
        services,
        theme_manager,
        parent=None,
        hotkey_callback=None,
        bar_hotkey_callback=None,
        app_launcher_hotkey_callback=None,
        quick_launch_bar=None,
    ):
        """Initialize the settings controls and anchor the dialog to the cursor display.

        Args:
            services: Application services used to load and save settings.
            theme_manager: Manager used to preview and restore theme changes.
            parent: Optional parent widget.
            hotkey_callback: Optional callback to register the command-palette hotkey.
            bar_hotkey_callback: Optional callback to register the bar hotkey.
            app_launcher_hotkey_callback: Optional callback for the app-launcher hotkey.
            quick_launch_bar: Optional bar refreshed after pin changes are committed.

        Raises:
            Exceptions raised while loading settings or constructing Qt controls.
        """
        super().__init__(parent)
        self.services = services
        self._theme_manager = theme_manager
        self._hotkey_callback = hotkey_callback
        self._bar_hotkey_callback = bar_hotkey_callback
        self._app_launcher_hotkey_callback = app_launcher_hotkey_callback
        self._quick_launch_bar = quick_launch_bar
        self.setWindowTitle("Settings")

        screen = self._screen_for_cursor()
        geometry = screen.availableGeometry() if screen is not None else None
        screen_width = geometry.width() if geometry is not None else None
        screen_height = geometry.height() if geometry is not None else None
        max_width = max_height = 0
        if (
            isinstance(screen_width, int)
            and isinstance(screen_height, int)
            and screen_width > 0
            and screen_height > 0
        ):
            max_width = min(int(screen_width * 0.8), 860)
            max_height = min(int(screen_height * 0.8), 720)
            self.setMaximumSize(max_width, max_height)
            self.setMinimumWidth(min(420, max_width))
            self.resize(max_width, max_height)
        else:
            self.setMinimumWidth(420)

        settings = self.services.config_manager.get_settings()
        self._settings = settings

        dialog_layout = QVBoxLayout()
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)

        # --- Appearance -------------------------------------------------
        appearance_box = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_box)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["system", "dark", "light"])
        current_theme = settings.get("theme", "system")
        idx = self._theme_combo.findText(current_theme)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        appearance_form.addRow("Theme:", self._theme_combo)

        # Live preview on selection change
        self._theme_combo.currentTextChanged.connect(self._preview_theme)

        settings_layout.addWidget(appearance_box)

        # --- Behaviour --------------------------------------------------
        behaviour_box = QGroupBox("Behaviour")
        behaviour_form = QFormLayout(behaviour_box)

        self._hotkey_edit = QLineEdit(settings.get("hotkey", "ctrl+shift+space"))
        self._hotkey_edit.setPlaceholderText("e.g. ctrl+shift+space")
        behaviour_form.addRow("Command Palette hotkey:", self._hotkey_edit)

        self._app_launcher_hotkey_edit = QLineEdit(
            settings.get("app_launcher_hotkey", "ctrl+alt+a")
        )
        self._app_launcher_hotkey_edit.setPlaceholderText("e.g. ctrl+alt+a")
        behaviour_form.addRow("App Launcher hotkey:", self._app_launcher_hotkey_edit)

        self._history_spin = QSpinBox()
        self._history_spin.setRange(0, 500)
        self._history_spin.setValue(int(settings.get("history_limit", 50)))
        behaviour_form.addRow("History limit:", self._history_spin)

        settings_layout.addWidget(behaviour_box)

        # --- Output Window ----------------------------------------------
        output_box = QGroupBox("Output Window")
        output_form = QFormLayout(output_box)

        font_cfg = settings.get("output_font", {})
        if not isinstance(font_cfg, dict):
            font_cfg = {}

        self._font_family_edit = QLineEdit(font_cfg.get("family", "monospace"))
        output_form.addRow("Font family:", self._font_family_edit)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(6, 48)
        self._font_size_spin.setValue(int(font_cfg.get("size", 10)))
        output_form.addRow("Font size:", self._font_size_spin)

        settings_layout.addWidget(output_box)

        # --- Quick-Launch Bar -------------------------------------------
        qlb_box = QGroupBox("Quick-Launch Bar")
        qlb_form = QFormLayout(qlb_box)

        qlb_cfg = settings.get("quick_launch_bar", {})
        if not isinstance(qlb_cfg, dict):
            qlb_cfg = {}

        self._qlb_visible_check = QCheckBox("Show Quick-Launch Bar")
        self._qlb_visible_check.setChecked(bool(qlb_cfg.get("visible", False)))
        qlb_form.addRow(self._qlb_visible_check)

        self._qlb_hotkey_edit = QLineEdit(qlb_cfg.get("hotkey", "ctrl+shift+b"))
        self._qlb_hotkey_edit.setPlaceholderText("e.g. ctrl+shift+b")
        qlb_form.addRow("Bar hotkey:", self._qlb_hotkey_edit)

        settings_layout.addWidget(qlb_box)

        # --- Pinned Commands --------------------------------------------
        self._qlb_pin_manager = QuickLaunchPinManager(
            self.services,
            self._settings,
        )
        if self._quick_launch_bar is not None:
            self._qlb_pin_manager.pins_committed.connect(lambda: self._quick_launch_bar.refresh())

        pinned_box = QGroupBox("Pinned Commands")
        pinned_layout = QVBoxLayout(pinned_box)
        pinned_layout.addWidget(self._qlb_pin_manager)
        settings_layout.addWidget(pinned_box)

        # --- Logging ----------------------------------------------------
        logging_box = QGroupBox("Logging")
        logging_form = QFormLayout(logging_box)

        log_cfg = settings.get("logging", {})
        if not isinstance(log_cfg, dict):
            log_cfg = {}

        self._log_level_combo = QComboBox()
        self._log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        current_level = log_cfg.get("level", "WARNING").upper()
        idx = self._log_level_combo.findText(current_level)
        if idx >= 0:
            self._log_level_combo.setCurrentIndex(idx)
        logging_form.addRow("Log level:", self._log_level_combo)

        settings_layout.addWidget(logging_box)

        # --- Scheduling help --------------------------------------------
        help_label = QLabel(
            'See <a href="docs/configuration.md#safe-scheduling">'
            "docs/configuration.md#safe-scheduling</a> for safe scheduling constraints."
        )
        settings_layout.addWidget(help_label)

        scroll_area.setWidget(settings_content)
        dialog_layout.addWidget(scroll_area)

        # --- Buttons ----------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self._cancel)
        dialog_layout.addWidget(buttons)
        self.setLayout(dialog_layout)

        if geometry is not None and max_width > 0 and max_height > 0:
            x = geometry.center().x() - self.width() // 2
            y = geometry.center().y() - self.height() // 2
            x = max(geometry.left(), min(x, geometry.right() - self.width() + 1))
            y = max(geometry.top(), min(y, geometry.bottom() - self.height() + 1))
            self.move(x, y)

        self._original_theme = current_theme

    def _screen_for_cursor(self):
        """Return the cursor's screen, falling back to the primary screen or None."""
        screen = QGuiApplication.screenAt(QCursor.pos())
        return screen if screen is not None else QApplication.primaryScreen()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _preview_theme(self, theme: str) -> None:
        """Apply theme change live as the user moves the combo."""
        self._theme_manager.apply_theme(theme)

    def _save(self) -> None:
        """Persist settings and accept the dialog."""
        try:
            settings = self.services.config_manager.get_settings()

            settings["theme"] = self._theme_combo.currentText()
            settings["hotkey"] = self._hotkey_edit.text().strip()
            settings["app_launcher_hotkey"] = self._app_launcher_hotkey_edit.text().strip()
            settings["history_limit"] = self._history_spin.value()
            settings["output_font"] = {
                "family": self._font_family_edit.text().strip() or "monospace",
                "size": self._font_size_spin.value(),
            }

            qlb_cfg = settings.get("quick_launch_bar", {})
            if not isinstance(qlb_cfg, dict):
                qlb_cfg = {}
            qlb_cfg["visible"] = self._qlb_visible_check.isChecked()
            qlb_cfg["hotkey"] = self._qlb_hotkey_edit.text().strip()
            settings["quick_launch_bar"] = qlb_cfg

            log_cfg = settings.get("logging", {})
            if not isinstance(log_cfg, dict):
                log_cfg = {}
            log_cfg["level"] = self._log_level_combo.currentText()
            settings["logging"] = log_cfg

            self._qlb_pin_manager.commit()

            self.services.config_manager.save_settings(settings)
            logger.info("Settings saved")
            # Theme already applied via preview; ensure final value is set
            self._theme_manager.apply_theme(settings["theme"])
            # Re-register hotkeys immediately so changes take effect without restart
            if self._hotkey_callback:
                self._hotkey_callback(settings["hotkey"])
            if self._bar_hotkey_callback:
                self._bar_hotkey_callback(qlb_cfg["hotkey"])
            if self._app_launcher_hotkey_callback:
                self._app_launcher_hotkey_callback(settings["app_launcher_hotkey"])
            self.accept()
        except Exception as exc:
            show_error(self, "Error", f"Failed to save settings:\n{exc}")

    def _cancel(self) -> None:
        """Revert any live theme preview and close."""
        self._theme_manager.apply_theme(self._original_theme)
        self.reject()
