# SPDX-License-Identifier: GPL-3.0-or-later

"""
SettingsDialog — GUI for editing application settings stored in settings.json.

Covers:
  • Theme selection (dark / light / system)
  • Global hotkey string
  • Logging level
  • History size cap
  • Output font family and size
"""

import logging

from PyQt6.QtGui import QCursor, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
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

from ui.dialog_conventions import configure_dialog_layout
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
        app_launcher_hotkey_callback=None,
    ):
        """Initialize settings controls and anchor the dialog to the cursor display.

        Args:
            services: Application services used to load and save settings.
            theme_manager: Manager used to preview and restore theme changes.
            parent: Optional parent widget.
            hotkey_callback: Optional callback to register the command-palette hotkey.
            app_launcher_hotkey_callback: Optional callback for the app-launcher hotkey.

        Raises:
            Exceptions raised while loading settings or constructing Qt controls.
        """
        super().__init__(parent)
        self.services = services
        self._theme_manager = theme_manager
        self._hotkey_callback = hotkey_callback
        self._app_launcher_hotkey_callback = app_launcher_hotkey_callback
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
            max_width = max(1, min(int(screen_width * 0.8), 860))
            max_height = max(1, min(int(screen_height * 0.8), 720))
            self.setMaximumSize(max_width, max_height)
            self.setMinimumWidth(min(420, max_width))
            self.resize(max_width, max_height)
        else:
            self.setMinimumWidth(420)

        settings = self.services.config_manager.get_settings()
        self._settings = settings

        layout = QVBoxLayout(self)
        configure_dialog_layout(layout)
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        configure_dialog_layout(settings_layout)

        # --- Appearance -------------------------------------------------
        appearance_box = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_box)
        configure_dialog_layout(appearance_form)

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
        configure_dialog_layout(behaviour_form)

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
        configure_dialog_layout(output_form)

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

        # --- Logging ----------------------------------------------------
        logging_box = QGroupBox("Logging")
        logging_form = QFormLayout(logging_box)
        configure_dialog_layout(logging_form)

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
        layout.addWidget(scroll_area, 1)

        # --- Buttons ----------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is None or cancel_button is None:
            raise RuntimeError("Settings dialog could not create Save and Cancel buttons")
        save_button.setDefault(True)
        cancel_button.setDefault(False)
        cancel_button.setAutoDefault(False)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self._cancel)
        layout.addWidget(buttons)
        tab_order = (
            self._theme_combo,
            self._hotkey_edit,
            self._app_launcher_hotkey_edit,
            self._history_spin,
            self._font_family_edit,
            self._font_size_spin,
            self._log_level_combo,
            save_button,
            cancel_button,
        )
        for current, following in zip(tab_order[:-1], tab_order[1:], strict=True):
            self.setTabOrder(current, following)

        self._original_theme = current_theme
        self._place_on_screen(geometry, max_width, max_height)
        self._theme_combo.setFocus()

    @staticmethod
    def _screen_for_cursor():
        """Return the cursor's screen, falling back to the primary screen or None.

        Returns:
            The screen containing the cursor, the primary screen, or ``None``.
        """
        screen = QGuiApplication.screenAt(QCursor.pos())
        return screen if screen is not None else QApplication.primaryScreen()

    def _place_on_screen(self, geometry, max_width: int, max_height: int) -> None:
        """Centre the bounded dialog in the selected screen's available area.

        Args:
            geometry: Available screen rectangle, or ``None`` when no screen exists.
            max_width: Configured screen-bounded width; zero means no usable geometry.
            max_height: Configured screen-bounded height; zero means no usable geometry.

        Returns:
            None.
        """
        if geometry is None or max_width <= 0 or max_height <= 0:
            return
        x = geometry.center().x() - self.width() // 2
        y = geometry.center().y() - self.height() // 2
        x = max(geometry.left(), min(x, geometry.right() - self.width() + 1))
        y = max(geometry.top(), min(y, geometry.bottom() - self.height() + 1))
        self.move(x, y)

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

            log_cfg = settings.get("logging", {})
            if not isinstance(log_cfg, dict):
                log_cfg = {}
            log_cfg["level"] = self._log_level_combo.currentText()
            settings["logging"] = log_cfg

            self.services.config_manager.save_settings(settings)
            logger.info("Settings saved")
            # Theme already applied via preview; ensure final value is set
            self._theme_manager.apply_theme(settings["theme"])
            # Re-register hotkeys immediately so changes take effect without restart
            if self._hotkey_callback:
                self._hotkey_callback(settings["hotkey"])
            if self._app_launcher_hotkey_callback:
                self._app_launcher_hotkey_callback(settings["app_launcher_hotkey"])
            self.accept()
        except Exception as exc:
            show_error(self, "Error", f"Failed to save settings:\n{exc}")

    def _cancel(self) -> None:
        """Revert any live theme preview and close."""
        self._theme_manager.apply_theme(self._original_theme)
        self.reject()
