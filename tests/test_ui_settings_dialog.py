from unittest.mock import MagicMock

from ui.settings_dialog import SettingsDialog


def test_settings_dialog_instantiates(qtbot):
    mock_services = MagicMock()
    theme_manager = MagicMock()
    dialog = SettingsDialog(mock_services, theme_manager=theme_manager)
    qtbot.addWidget(dialog)
    assert dialog is not None