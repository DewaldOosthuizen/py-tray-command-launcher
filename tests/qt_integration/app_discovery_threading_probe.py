# SPDX-License-Identifier: GPL-3.0-or-later
"""Real-Qt integration probe for asynchronous application discovery."""

import importlib
import os
import sys
import threading
import tempfile
from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtCore import QEventLoop, QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

if "tests.conftest" in sys.modules:
    raise RuntimeError("The real-Qt probe must not load tests.conftest")

AppDiscovery = importlib.import_module("modules.app_discovery").AppDiscovery
palette_module = importlib.import_module("ui.command_palette")
CommandPalette = palette_module.CommandPalette
_PaletteWindow = palette_module._PaletteWindow


class _ProbeSignals(QObject):
    """Notify event-loop waits when palette completion or failure slots run."""

    failed = pyqtSignal()
    completed = pyqtSignal()


def _wait_for(signal, timeout_ms=5000):
    """Run the Qt event loop until *signal* fires or a bounded timeout expires."""
    loop = QEventLoop()
    timed_out = []
    signal.connect(loop.quit, Qt.ConnectionType.QueuedConnection)
    QTimer.singleShot(timeout_ms, lambda: (timed_out.append(True), loop.quit()))
    loop.exec()
    if timed_out:
        raise AssertionError("Timed out waiting for application discovery")


def main():
    """Exercise a failed discovery and retry using real Qt threads and signals."""
    application = QApplication.instance() or QApplication([])
    main_thread_id = threading.get_ident()

    with tempfile.TemporaryDirectory() as directory:
        data_home = Path(directory)
        applications = data_home / "applications"
        applications.mkdir()
        (applications / "probe.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Probe Application\n"
            "Exec=/usr/bin/probe-application\n"
            "Icon=application-x-executable\n",
            encoding="utf-8",
        )
        os.environ["XDG_DATA_HOME"] = str(data_home)
        os.environ["XDG_DATA_DIRS"] = ""

        discovery = AppDiscovery()
        scan_threads = []
        failure_threads = []
        completion_threads = []
        original_parse = discovery._parse_desktop_file
        original_load = discovery._load_linux

        def record_parse(path):
            scan_threads.append(threading.get_ident())
            return original_parse(path)

        discovery._parse_desktop_file = record_parse

        def fail_first_load():
            scan_threads.append(threading.get_ident())
            raise OSError("simulated temporary discovery failure")

        discovery._load_linux = fail_first_load
        palette = CommandPalette(services=SimpleNamespace())
        window = _PaletteWindow(palette, discovery=discovery)
        signals = _ProbeSignals()

        original_failure_slot = window._on_discovery_failed
        original_completion_slot = window._on_discovery_completed

        def record_failure(message):
            failure_threads.append(threading.get_ident())
            original_failure_slot(message)
            signals.failed.emit()

        def record_completion(entries):
            completion_threads.append(threading.get_ident())
            original_completion_slot(entries)
            signals.completed.emit()

        window._on_discovery_failed = record_failure
        window._on_discovery_completed = record_completion

        window._start_discovery_worker()
        assert window._discovery_running
        _wait_for(signals.failed)
        assert not window._apps_loaded
        assert failure_threads == [main_thread_id]
        assert scan_threads and scan_threads[0] != main_thread_id

        discovery._load_linux = original_load
        window._retry_discovery()
        assert window._discovery_running
        _wait_for(signals.completed)

        assert window._apps_loaded
        assert completion_threads == [main_thread_id]
        assert scan_threads[-1] != main_thread_id
        assert any(
            window._app_list.item(index).text().startswith("Probe Application")
            for index in range(window._app_list.count())
        )

        window.close()
        application.processEvents()

    print("real Qt app discovery threading probe passed")


if __name__ == "__main__":
    main()
