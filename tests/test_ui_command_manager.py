from unittest.mock import MagicMock, patch
from ui.command_manager import CommandManagerDialog


def test_command_manager_dialog_instantiates(mock_services, qtbot):
    # Patch the module-level config_manager.get_commands() call inside
    # _load_tree() so the dialog does not touch the real filesystem or
    # JSON-schema resolver during the smoke test.
    with patch("ui.command_manager.config_manager") as mock_cm:
        mock_cm.get_commands.return_value = {}
        dialog = CommandManagerDialog(
            services=mock_services,
            running_processes={},
        )
        qtbot.addWidget(dialog)
        assert dialog is not None
