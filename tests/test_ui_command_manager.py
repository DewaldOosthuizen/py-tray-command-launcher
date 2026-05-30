from unittest.mock import MagicMock
from ui.command_manager import CommandManagerDialog


def test_command_manager_dialog_instantiates(mock_services, qtbot):
    dialog = CommandManagerDialog(
        services=mock_services,
        running_processes={},
    )
    qtbot.addWidget(dialog)
    assert dialog is not None
