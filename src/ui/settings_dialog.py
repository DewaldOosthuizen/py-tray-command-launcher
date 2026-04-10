#  SPDX-License-Identifier: GPL-3.0-or-later

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

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QCheckBox,
)

from core.config_manager import config_manager

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings dialog covering theme, hotkey, logging, history, and output font."""

    def __init__(self, theme_manager, parent=None, hotkey_callback=None, bar_hotkey_callback=None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._hotkey_callback = hotkey_callback
        self._bar_hotkey_callback = bar_hotkey_callback
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)

        settings = config_manager.get_settings()

        layout = QVBoxLayout(self)

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

        layout.addWidget(appearance_box)

        # --- Behaviour --------------------------------------------------
        behaviour_box = QGroupBox("Behaviour")
        behaviour_form = QFormLayout(behaviour_box)

        self._hotkey_edit = QLineEdit(settings.get("hotkey", "ctrl+shift+space"))
        self._hotkey_edit.setPlaceholderText("e.g. ctrl+shift+space")
        behaviour_form.addRow("Command Palette hotkey:", self._hotkey_edit)

        self._history_spin = QSpinBox()
        self._history_spin.setRange(0, 500)
        self._history_spin.setValue(int(settings.get("history_limit", 50)))
        behaviour_form.addRow("History limit:", self._history_spin)

        layout.addWidget(behaviour_box)

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

        layout.addWidget(output_box)

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

        layout.addWidget(qlb_box)

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

        layout.addWidget(logging_box)

        # --- Buttons ----------------------------------------------------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self._cancel)
        layout.addWidget(buttons)

        self._original_theme = current_theme

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _preview_theme(self, theme: str) -> None:
        """Apply theme change live as the user moves the combo."""
        self._theme_manager.apply_theme(theme)

    def _save(self) -> None:
        """Persist settings and accept the dialog."""
        try:
            settings = config_manager.get_settings(refresh=True)

            settings["theme"] = self._theme_combo.currentText()
            settings["hotkey"] = self._hotkey_edit.text().strip()
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

            config_manager.save_settings(settings)
            logger.info("Settings saved")
            # Theme already applied via preview; ensure final value is set
            self._theme_manager.apply_theme(settings["theme"])
            # Re-register hotkeys immediately so changes take effect without restart
            if self._hotkey_callback:
                self._hotkey_callback(settings["hotkey"])
            if self._bar_hotkey_callback:
                self._bar_hotkey_callback(qlb_cfg["hotkey"])
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save settings:\n{exc}")

    def _cancel(self) -> None:
        """Revert any live theme preview and close."""
        self._theme_manager.apply_theme(self._original_theme)
        self.reject()
