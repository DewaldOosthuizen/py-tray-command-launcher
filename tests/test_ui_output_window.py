from unittest.mock import patch

from ui.output_window import RichOutputWindow


def test_rich_output_window_instantiates(qtbot):
    with patch("ui.output_window.config_manager") as mock_cm:
        mock_cm.get_settings.return_value = {}
        window = RichOutputWindow()
    qtbot.addWidget(window)
    assert window is not None
