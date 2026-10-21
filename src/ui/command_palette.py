# SPDX-License-Identifier: GPL-3.0-or-later

"""
CommandPalette — spotlight-style popup overlay for quick command access and
app launching.

* Frameless ``Qt.Popup`` window — disappears on focus loss.
* Two tabs: **Commands** (existing behaviour) and **Apps** (new app launcher).
* Reuses the same rapidfuzz scoring used in CommandSearch.
* Global hotkey registration uses ``pynput`` via ``_HotkeyTrigger``, which
  emits a ``pyqtSignal`` from a background listener thread into the Qt main
  loop so the palette is shown safely on the main thread.

Public API
----------
``CommandPalette(services)``
    Instantiate once and reuse across show calls.

``palette.show_palette()``
    Show (or raise) the palette on the Commands tab.

``palette.show_app_launcher()``
    Show (or raise) the palette on the Apps tab.

``palette.register_hotkeys(cmd_hotkey, app_hotkey)``
    Register both global hotkeys in a single pynput listener.
"""

import logging
import os
import subprocess
import sys
import weakref

from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent, QScreen
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from modules.command_search import search_commands
from utils.execution_cues import describe_execution_cues, format_execution_cues
from utils.hotkey_helpers import safe_unregister, to_pynput_str

logger = logging.getLogger(__name__)
_ACTIVE_DISCOVERY_WORKERS = set()
_SHUTDOWN_HOOK_CONNECTED = False


def _wait_for_discovery_workers() -> None:
    """Finish outstanding scans before Qt destroys their parentless threads."""
    for worker in tuple(_ACTIVE_DISCOVERY_WORKERS):
        worker.wait()
    _ACTIVE_DISCOVERY_WORKERS.clear()


def _ensure_discovery_shutdown_hook() -> None:
    """Register one orderly worker wait for application shutdown."""
    global _SHUTDOWN_HOOK_CONNECTED
    application = QApplication.instance()
    if application is not None and not _SHUTDOWN_HOOK_CONNECTED:
        application.aboutToQuit.connect(_wait_for_discovery_workers)
        _SHUTDOWN_HOOK_CONNECTED = True


def _release_discovery_worker(worker, window_ref) -> None:
    """Release a finished worker without tying its lifetime to the popup."""
    _ACTIVE_DISCOVERY_WORKERS.discard(worker)
    window = window_ref()
    if window is not None:
        window._on_discovery_worker_finished(worker)


class _HotkeyTrigger(QObject):
    """Thread-safe bridge: emit named signals from any thread into the Qt main loop."""

    cmd_triggered = pyqtSignal()
    app_triggered = pyqtSignal()


# Tab identifiers
_TAB_COMMANDS = "commands"
_TAB_APPS = "apps"


class _PaletteWindow(QWidget):
    """Internal frameless popup window with Commands / Apps tabs."""

    def __init__(self, palette: "CommandPalette", discovery=None):
        """Build the popup and bind it to an application discovery service.

        Args:
            palette: Command palette coordinator owning this window.
            discovery: Optional discovery service; defaults to the singleton.

        Returns:
            None.
        """
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Popup
            | Qt.WindowType.NoDropShadowWindowHint,
        )
        self._palette = palette
        if discovery is None:
            from modules.app_discovery import app_discovery

            discovery = app_discovery
        self._app_discovery = discovery
        self._apps_loaded = discovery.is_loaded is True
        self._apps = discovery.get_all() if self._apps_loaded else None
        self._discovery_running = False
        self._discovery_workers = set()
        self._active_tab = _TAB_COMMANDS
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumWidth(520)
        self.setMaximumHeight(460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Frame gives a visible border independent of QSS
        frame = QFrame(self)
        frame.setObjectName("PaletteFrame")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Tab row
        tab_row = QHBoxLayout()
        tab_row.setSpacing(4)
        self._cmd_tab_btn = QPushButton("Commands")
        self._cmd_tab_btn.setAccessibleName("Commands view")
        self._cmd_tab_btn.setObjectName("PaletteTabActive")
        self._cmd_tab_btn.setFlat(True)
        self._cmd_tab_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._app_tab_btn = QPushButton("Apps")
        self._app_tab_btn.setAccessibleName("Apps view")
        self._app_tab_btn.setObjectName("PaletteTab")
        self._app_tab_btn.setFlat(True)
        self._app_tab_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tab_row.addWidget(self._cmd_tab_btn)
        tab_row.addWidget(self._app_tab_btn)
        layout.addLayout(tab_row)

        # Header row
        header = QHBoxLayout()
        icon_label = QLabel("⌘")
        icon_label.setObjectName("PaletteIcon")
        self._search = QLineEdit()
        self._search.setPlaceholderText("Run a command…")
        self._search.setObjectName("PaletteSearch")
        self._search.setClearButtonEnabled(True)
        header.addWidget(icon_label)
        header.addWidget(self._search)
        layout.addLayout(header)

        # Stacked widget — index 0: commands, index 1: apps
        self._stack = QStackedWidget()

        self._cmd_list = QListWidget()
        self._cmd_list.setObjectName("PaletteList")
        self._cmd_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._stack.addWidget(self._cmd_list)

        self._app_list = QListWidget()
        self._app_list.setObjectName("PaletteList")
        self._app_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._app_list.setIconSize(QSize(32, 32))
        self._apps_status = QLabel()
        self._apps_status.setObjectName("PaletteAppsStatus")
        self._apps_status.setWordWrap(True)
        self._apps_status.setVisible(False)
        self._retry_button = QPushButton("Retry")
        self._retry_button.setObjectName("PaletteAppsRetry")
        self._retry_button.setVisible(False)
        apps_page = QWidget()
        apps_layout = QVBoxLayout(apps_page)
        apps_layout.setContentsMargins(0, 0, 0, 0)
        apps_layout.setSpacing(4)
        apps_layout.addWidget(self._apps_status)
        apps_layout.addWidget(self._retry_button)
        apps_layout.addWidget(self._app_list)
        self._stack.addWidget(apps_page)

        layout.addWidget(self._stack)

        # Footer hint
        footer = QLabel("↑↓ navigate   ↵ execute   Esc close")
        footer.setObjectName("PaletteFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        outer.addWidget(frame)
        self.setTabOrder(self._cmd_tab_btn, self._app_tab_btn)
        self.setTabOrder(self._app_tab_btn, self._search)
        self.setTabOrder(self._search, self._cmd_list)
        self.setTabOrder(self._cmd_list, self._app_list)
        self.setTabOrder(self._app_list, self._retry_button)

        # Debounce timer — waits 150 ms after the last keystroke before
        # updating the list, preventing floods of work during fast typing
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(lambda: self._populate(self._search.text()))

        # Connections
        self._search.textChanged.connect(lambda _: self._search_timer.start())
        self._cmd_list.itemActivated.connect(self._execute)
        self._app_list.itemActivated.connect(self._execute)
        self._cmd_tab_btn.clicked.connect(lambda: self._switch_tab(_TAB_COMMANDS))
        self._app_tab_btn.clicked.connect(lambda: self._switch_tab(_TAB_APPS))
        self._retry_button.clicked.connect(self._retry_discovery)

        self._search.installEventFilter(self)

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _switch_tab(self, tab: str) -> None:
        """Switch the active tab and refresh results."""
        self._active_tab = tab
        if tab == _TAB_COMMANDS:
            self._stack.setCurrentIndex(0)
            self._cmd_tab_btn.setObjectName("PaletteTabActive")
            self._app_tab_btn.setObjectName("PaletteTab")
            self._search.setPlaceholderText("Run a command…")
        else:
            self._stack.setCurrentIndex(1)
            self._cmd_tab_btn.setObjectName("PaletteTab")
            self._app_tab_btn.setObjectName("PaletteTabActive")
            self._search.setPlaceholderText("Search apps…")

        # Force style refresh after objectName change
        for btn in (self._cmd_tab_btn, self._app_tab_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        self._populate(self._search.text())

    # ------------------------------------------------------------------
    # Population / search
    # ------------------------------------------------------------------

    def _populate(self, query: str) -> None:
        if self._active_tab == _TAB_COMMANDS:
            self._populate_commands(query)
        else:
            self._populate_apps(query)

    def _populate_commands(self, query: str) -> None:
        self._cmd_list.clear()
        all_cmds = self._palette._services.get_all_commands()
        scored = search_commands(query, all_cmds)

        for _s, cmd in scored:
            cues = format_execution_cues(cmd, concise=True)
            row_text = f"{cmd['label']}  —  {cmd['group']}"
            if cues:
                row_text = f"{row_text}  ·  {cues}"
            item = QListWidgetItem(row_text)
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                f"{cmd['label']}, {cmd['group']}",
            )
            description = describe_execution_cues(cmd)
            item.setData(Qt.ItemDataRole.AccessibleDescriptionRole, description)
            if description:
                item.setToolTip(description)
            self._cmd_list.addItem(item)

        if self._cmd_list.count() > 0:
            self._cmd_list.setCurrentRow(0)

    def _populate_apps(self, query: str) -> None:
        """Render cached results or start the single cold-discovery job."""
        if not self._apps_loaded:
            if not self._discovery_running:
                self._discovery_running = True
                self._show_apps_loading()
                self._start_discovery_worker()
            return

        self._render_apps(query, self._apps)

    def _render_apps(self, query: str, apps) -> None:
        """Filter and render discovered entries on the Qt main thread.

        Args:
            query: Current Apps-tab search text.
            apps: Fully discovered entries returned by the worker or cache.

        Returns:
            None.
        """
        from PyQt6.QtGui import QIcon as _QIcon

        from modules.app_discovery import search_apps

        self._app_list.clear()
        self._apps_status.clear()
        self._apps_status.setVisible(False)
        self._retry_button.setVisible(False)
        for app in search_apps(query, apps):
            display = app.name
            if app.categories_str:
                display = f"{app.name}\n{app.categories_str}"
            item = QListWidgetItem(display)
            px = self._app_discovery.resolve_icon_pixmap(app.icon_name, size=32)
            if px and not px.isNull():
                item.setIcon(_QIcon(px))
            item.setData(Qt.ItemDataRole.UserRole, app)
            self._app_list.addItem(item)

        if self._app_list.count() > 0:
            self._app_list.setCurrentRow(0)

    def _show_apps_loading(self) -> None:
        """Display non-blocking progress feedback while installed apps are scanned."""
        self._app_list.clear()
        self._retry_button.setVisible(False)
        self._apps_status.setText("Loading installed applications…")
        self._apps_status.setVisible(True)

    def _show_apps_error(self, message: str) -> None:
        """Display the discovery error and expose its retry action."""
        self._app_list.clear()
        self._apps_status.setText(
            f"Unable to load installed applications: {message}\nSelect Retry to try again."
        )
        self._apps_status.setVisible(True)
        self._retry_button.setVisible(True)

    def _start_discovery_worker(self) -> None:
        """Start one worker for the cached discovery service.

        The worker is parentless and retained independently of this popup so
        closing the palette cannot destroy a running QThread. Its signals are
        explicitly queued to the main-thread UI slots.

        Returns:
            None.

        Raises:
            ImportError: If the discovery worker implementation is unavailable.
        """
        from modules.app_discovery import AppDiscoveryWorker

        _ensure_discovery_shutdown_hook()
        self._discovery_running = True
        self._show_apps_loading()
        worker = AppDiscoveryWorker(self._app_discovery)
        self._discovery_workers.add(worker)
        _ACTIVE_DISCOVERY_WORKERS.add(worker)
        worker.completed.connect(self._on_discovery_completed, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._on_discovery_failed, Qt.ConnectionType.QueuedConnection)
        window_ref = weakref.ref(self)
        worker.finished.connect(
            lambda current=worker, owner=window_ref: _release_discovery_worker(current, owner),
            Qt.ConnectionType.QueuedConnection,
        )
        try:
            worker.start()
        except RuntimeError as exc:
            _release_discovery_worker(worker, window_ref)
            self._on_discovery_failed(str(exc) or "The discovery worker could not start.")

    def _on_discovery_completed(self, apps) -> None:
        """Cache worker results, clear progress state, and render the current query."""
        self._apps = apps
        self._apps_loaded = True
        self._discovery_running = False
        self._render_apps(self._search.text(), apps)

    def _on_discovery_failed(self, message: str) -> None:
        """Clear progress state and present a useful, retryable error."""
        self._discovery_running = False
        self._show_apps_error(message or "The discovery operation returned no details.")

    def _on_discovery_worker_finished(self, worker) -> None:
        """Forget a completed thread while preserving any newer retry worker."""
        self._discovery_workers.discard(worker)

    def _retry_discovery(self) -> None:
        """Retry a failed discovery asynchronously without changing the query."""
        if self._discovery_running or self._apps_loaded:
            return
        self._discovery_running = True
        self._show_apps_loading()
        self._start_discovery_worker()

    # ------------------------------------------------------------------
    # Active list helper
    # ------------------------------------------------------------------

    def _active_list(self) -> QListWidget:
        return self._cmd_list if self._active_tab == _TAB_COMMANDS else self._app_list

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute(self, item: QListWidgetItem = None) -> None:
        if item is None:
            item = self._active_list().currentItem()
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        self.hide()

        if self._active_tab == _TAB_COMMANDS:
            self._palette._services.execute(
                data["label"],
                data["command"],
                data.get("confirm", False),
                data.get("showOutput", False),
                data.get("prompt"),
            )
        else:
            self._launch_app(data)

    def _launch_app(self, entry) -> None:
        """Launch an installed application from its AppEntry."""
        from modules.app_discovery import AppDiscovery

        # Windows: .lnk shortcuts are launched via os.startfile() which lets
        # the shell resolve the shortcut target, file associations, and UAC.
        if AppDiscovery.is_windows_lnk_entry(entry):
            try:
                os.startfile(entry.exec_cmd)  # noqa: S606 — intentional: Windows .lnk shortcuts require os.startfile; exec_cmd is user-configured, not external input
                logger.info("Launched app (Windows): %s", entry.name)
            except OSError as exc:
                logger.warning("Failed to launch %s: %s", entry.name, exc)
            return

        args = AppDiscovery.build_launch_args(entry)
        if not args:
            logger.warning("Could not build launch args for app: %s", entry.name)
            return
        try:
            popen_kwargs: dict = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform != "win32":
                popen_kwargs["close_fds"] = True
                popen_kwargs["start_new_session"] = True
            else:
                popen_kwargs["creationflags"] = (
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            subprocess.Popen(args, **popen_kwargs)  # noqa: S603 — intentional: fixed arg list built from user config, no string interpolation
            logger.info("Launched app: %s", entry.name)
        except OSError as exc:
            logger.warning("Failed to launch %s: %s", entry.name, exc)
            try:
                self._palette._services.notify_user(
                    "Launch failed",
                    f"Could not start {entry.name}: {exc}",
                )
            except Exception:  # best-effort notification
                logger.debug("Failed to show launch failure notification", exc_info=True)

    # ------------------------------------------------------------------
    # Keyboard navigation
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if (
            obj is self._search
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
        ):
            key = event.key()
            active = self._active_list()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._execute()
                return True
            elif key == Qt.Key.Key_Down:
                row = active.currentRow()
                if row < active.count() - 1:
                    active.setCurrentRow(row + 1)
                return True
            elif key == Qt.Key.Key_Up:
                row = active.currentRow()
                if row > 0:
                    active.setCurrentRow(row - 1)
                return True
            elif key == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------

    def show_on_tab(self, tab: str) -> None:
        """Show the palette, switching to *tab* first."""
        if self._active_tab != tab:
            self._active_tab = tab
            self._stack.setCurrentIndex(0 if tab == _TAB_COMMANDS else 1)
            if tab == _TAB_COMMANDS:
                self._cmd_tab_btn.setObjectName("PaletteTabActive")
                self._app_tab_btn.setObjectName("PaletteTab")
                self._search.setPlaceholderText("Run a command…")
            else:
                self._cmd_tab_btn.setObjectName("PaletteTab")
                self._app_tab_btn.setObjectName("PaletteTabActive")
                self._search.setPlaceholderText("Search apps…")
            for btn in (self._cmd_tab_btn, self._app_tab_btn):
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        self._show_centered()

    def _screen_for_cursor(self) -> QScreen | None:
        """Return the screen containing the cursor, falling back to the primary screen."""
        screen = QGuiApplication.screenAt(QCursor.pos())
        return screen if screen is not None else QApplication.primaryScreen()

    def _show_centered(self) -> None:
        """Show the palette on the display containing the cursor, clamped to its geometry."""
        screen = self._screen_for_cursor()
        if screen is None:
            # No screen is available (should not happen on a desktop); show the window
            # without an explicit anchor rather than blocking the hotkey.
            self._search.clear()
            self._search_timer.stop()  # cancel any pending timer from clear()
            self._populate("")
            self.show()
            self.raise_()
            self.activateWindow()
            self._search.setFocus()
            return

        geo = screen.availableGeometry()
        # Width: keep a 520 px floor on large displays; shrink that floor to the display's
        # width on a narrow display. Height: cap at 460 px, or the display's height if it
        # is shorter, so the window always fits.
        self.setMinimumWidth(min(520, geo.width()))
        self.setMaximumWidth(geo.width())
        self.setMaximumHeight(min(460, geo.height()))
        self.adjustSize()
        width = self.width()
        height = self.height()
        # Centre horizontally; honour the historical 1/4 vertical offset.
        x = geo.center().x() - width // 2
        y = geo.top() + geo.height() // 4
        # Clamp both coordinates so the window rectangle is fully inside geo.
        x = max(geo.x(), min(x, geo.x() + geo.width() - width))
        y = max(geo.y(), min(y, geo.y() + geo.height() - height))
        self.move(x, y)

        self._search.clear()
        self._search_timer.stop()  # cancel any pending timer from clear()
        self._populate("")
        self.show()
        self.raise_()
        self.activateWindow()
        self._search.setFocus()

    def show_centered(self) -> None:
        """Backward-compatible alias for _show_centered."""
        self._show_centered()


class CommandPalette:
    """Manages the global command palette overlay and hotkey registration."""

    def __init__(self, services):
        self._services = services
        self._window: _PaletteWindow | None = None
        self._hotkey_listener = None
        self._cmd_hotkey: str = ""
        self._app_hotkey: str = ""
        self._trigger = _HotkeyTrigger()
        self._trigger.cmd_triggered.connect(self.show_palette, Qt.ConnectionType.QueuedConnection)
        self._trigger.app_triggered.connect(
            self.show_app_launcher, Qt.ConnectionType.QueuedConnection
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def show_palette(self) -> None:
        """Show (or raise) the palette on the Commands tab."""
        self.show_on_tab(_TAB_COMMANDS)

    def show_app_launcher(self) -> None:
        """Show (or raise) the palette on the Apps tab."""
        self.show_on_tab(_TAB_APPS)

    def show_on_tab(self, tab: str) -> None:
        """Show the palette on *tab* — safe to call from any thread via signal."""
        if self._window is None:
            self._window = _PaletteWindow(self)
        self._window.show_on_tab(tab)

    def register_hotkeys(self, cmd_hotkey: str, app_hotkey: str) -> bool:
        """Register both global hotkeys in a single pynput listener.

        Uses pynput's GlobalHotKeys (no root required on X11/Linux).
        Returns ``True`` on success; degrades gracefully when pynput is
        unavailable or the hotkey strings are empty.
        """
        self.unregister_hotkey()
        self._cmd_hotkey = cmd_hotkey
        self._app_hotkey = app_hotkey

        hotkey_map = {}
        if cmd_hotkey:
            hotkey_map[to_pynput_str(cmd_hotkey)] = self._trigger.cmd_triggered.emit
        if app_hotkey:
            hotkey_map[to_pynput_str(app_hotkey)] = self._trigger.app_triggered.emit

        if not hotkey_map:
            return False

        try:
            from pynput import keyboard as _kb

            self._hotkey_listener = _kb.GlobalHotKeys(hotkey_map)
            self._hotkey_listener.start()
            logger.info(
                "Palette hotkeys registered — cmd: %s  app: %s",
                cmd_hotkey or "(none)",
                app_hotkey or "(none)",
            )
            return True
        except ImportError:
            logger.warning("pynput not available — palette hotkeys disabled")
        except Exception as exc:
            logger.warning("Failed to register palette hotkeys: %s", exc)
        return False

    def register_hotkey(self, hotkey: str) -> bool:
        """Register only the command palette hotkey (backward-compatible)."""
        return self.register_hotkeys(hotkey, self._app_hotkey)

    def update_app_launcher_hotkey(self, hotkey: str) -> bool:
        """Re-register with a new app launcher hotkey, keeping the cmd hotkey."""
        return self.register_hotkeys(self._cmd_hotkey, hotkey)

    def unregister_hotkey(self) -> None:
        """Remove all registered global hotkeys."""
        self._hotkey_listener = safe_unregister(self._hotkey_listener, timeout=2.0)
