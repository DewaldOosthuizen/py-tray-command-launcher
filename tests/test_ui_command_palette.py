import os
import subprocess
import sys
from pathlib import Path
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


def test_cold_apps_population_starts_only_one_async_discovery(mock_services, qtbot):
    with patch("ui.command_palette._HotkeyTrigger", return_value=MagicMock()):
        window = _PaletteWindow(CommandPalette(services=mock_services))
    qtbot.addWidget(window)
    window._show_apps_loading = MagicMock()
    window._start_discovery_worker = MagicMock()

    with patch("modules.app_discovery.app_discovery.search", side_effect=AssertionError):
        window._populate_apps("calc")
        window._populate_apps("calculator")

    window._show_apps_loading.assert_called_once()
    window._start_discovery_worker.assert_called_once()
    assert window._discovery_running is True


def test_discovery_completion_renders_current_query(mock_services, qtbot):
    with patch("ui.command_palette._HotkeyTrigger", return_value=MagicMock()):
        window = _PaletteWindow(CommandPalette(services=mock_services))
    qtbot.addWidget(window)
    window._search = MagicMock()
    window._search.text.return_value = "calc"
    window._render_apps = MagicMock()
    entries = [SimpleNamespace(name="Calculator")]
    window._discovery_running = True

    window._on_discovery_completed(entries)

    assert window._apps_loaded is True
    assert window._discovery_running is False
    window._render_apps.assert_called_once_with("calc", entries)


def test_discovery_failure_shows_error_and_retry_action(mock_services, qtbot):
    with patch("ui.command_palette._HotkeyTrigger", return_value=MagicMock()):
        window = _PaletteWindow(CommandPalette(services=mock_services))
    qtbot.addWidget(window)
    window._apps_status = MagicMock()
    window._retry_button = MagicMock()
    window._discovery_running = True

    window._on_discovery_failed("desktop directory is unreadable")

    assert window._discovery_running is False
    window._apps_status.setText.assert_called_once()
    assert "desktop directory is unreadable" in window._apps_status.setText.call_args.args[0]
    window._retry_button.setVisible.assert_called_with(True)


def test_retry_after_failure_starts_worker_and_renders_results(mock_services, qtbot):
    with patch("ui.command_palette._HotkeyTrigger", return_value=MagicMock()):
        window = _PaletteWindow(CommandPalette(services=mock_services))
    qtbot.addWidget(window)
    window._search = MagicMock()
    window._search.text.return_value = "notes"
    window._render_apps = MagicMock()
    window._start_discovery_worker = MagicMock()
    window._on_discovery_failed("temporary scan error")

    window._retry_discovery()
    assert window._discovery_running is True
    window._start_discovery_worker.assert_called_once()

    entries = [SimpleNamespace(name="Notes")]
    window._on_discovery_completed(entries)

    window._render_apps.assert_called_once_with("notes", entries)
    assert window._apps_loaded is True
    assert window._discovery_running is False


def test_real_qt_app_discovery_threading_probe():
    probe = Path(__file__).parent / "qt_integration" / "app_discovery_threading_probe.py"
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, str(probe)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
