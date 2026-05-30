from unittest.mock import MagicMock, patch

from ui.settings_dialog import SettingsDialog


def test_settings_dialog_instantiates(qtbot):
    theme_manager = MagicMock()
    with patch("ui.settings_dialog.config_manager") as mock_cm:
        mock_cm.get_settings.return_value = {}
        dialog = SettingsDialog(theme_manager=theme_manager)
    qtbot.addWidget(dialog)
    assert dialog is not None
