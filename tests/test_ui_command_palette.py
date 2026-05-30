from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# PyQt6 stub is injected by conftest.py before this file is collected.
from ui.command_palette import CommandPalette, _PaletteWindow


def test_command_palette_instantiates(mock_services):
    palette = CommandPalette(services=mock_services)
    assert palette is not None


def test_palette_window_instantiates(mock_services, qtbot):
    # Patch _HotkeyTrigger so each CommandPalette() call gets a fresh mock
    # and does not exhaust a shared side_effect iterator.
    with patch("ui.command_palette._HotkeyTrigger", return_value=MagicMock()):
        palette = CommandPalette(services=mock_services)
        window = _PaletteWindow(palette=palette)
        qtbot.addWidget(window)
        assert window is not None


def test_palette_window_notifies_on_launch_failure(mock_services, qtbot):
    with patch("ui.command_palette._HotkeyTrigger", return_value=MagicMock()):
        palette = CommandPalette(services=mock_services)
        window = _PaletteWindow(palette=palette)
        qtbot.addWidget(window)

    entry = SimpleNamespace(name="Broken App", exec_cmd="/broken/app")
    with (
        patch("modules.app_discovery.AppDiscovery.is_windows_lnk_entry", return_value=False),
        patch("modules.app_discovery.AppDiscovery.build_launch_args", return_value=["/broken/app"]),
        patch("ui.command_palette.subprocess.Popen", side_effect=OSError("boom")),
    ):
        window._launch_app(entry)

    mock_services.notify_user.assert_called_once_with(
        "Launch failed",
        "Could not start Broken App: boom",
    )
