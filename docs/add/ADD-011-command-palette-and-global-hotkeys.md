# ADD-011 — Command palette and global hotkeys via pynput

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | ui, hotkeys, pynput, command-palette |

---

## Context

Power users need to invoke the command launcher without reaching for the mouse
to click the tray icon.  A global hotkey that works regardless of which
application currently has focus is a standard expectation for launcher
applications (cf. Alfred, Spotlight, Rofi).

Qt's `QShortcut` only fires when a Qt window has focus — it cannot intercept
key combinations from other applications.  A native keyboard hook was needed.

---

## Decision

### pynput listener

Global hotkey listening is implemented via `pynput.keyboard.Listener` running
in a background daemon thread inside a `_HotkeyTrigger` `QObject` helper class
defined in `ui/command_palette.py`.

When the user presses the configured hotkey combination, the background thread
emits a `pyqtSignal` into the Qt main thread via a queued connection.  This
is the correct pattern for cross-thread GUI updates in PyQt6 — the background
thread never touches any `QWidget` directly.

```
pynput listener thread
    └── hotkey matched
            └── emit trigger_signal (queued)
                    └── Qt main thread
                            └── CommandPalette.show_palette()
```

Two hotkeys are registered in a single `pynput.keyboard.Listener`:

- **Command palette** (`Ctrl+Shift+Space` by default) → opens the Commands tab.
- **App launcher** (configurable) → opens the Apps tab.

Both hotkeys are re-registered atomically on `register_hotkeys()`, which is
called after a hotkey change is saved in `SettingsDialog`.

### Hotkey string format

Hotkeys are stored in `settings.json → hotkey` as a `+`-separated string,
e.g. `ctrl+shift+space`.  `CommandPalette` parses this using a mapping table
that translates common names (`ctrl`, `shift`, `alt`, `space`, etc.) to
`pynput.keyboard.Key` enum members, with single-character keys treated as
`KeyCode.from_char`.

### CommandPalette UI

`CommandPalette` is a frameless `Qt.WindowType.Popup` window (disappears on
focus loss) containing:

- A `QLineEdit` search bar with live filtering on every keystroke.
- A `QListWidget` of matching commands sorted by `rapidfuzz` score.
- A secondary **Apps** tab backed by `AppDiscovery` (see ADD-015) for
  launching installed desktop applications.

The palette is instantiated once and reused across invocations (`show()` /
`hide()`) to avoid the cost of rebuilding the widget tree on every hotkey press.

---

## Alternatives considered

**`keyboard` library** — simpler API but requires root on Linux without
`uinput` group membership; `pynput` works under X11 and Wayland (via
`Wnck` and `XRecord` or the XDG input backend).

**`xdotool` / `xbindkeys` subprocess** — would offload the hotkey to an
external tool, removing the in-process dependency.  Rejected: adds a system
dependency, is Linux-only, and makes hotkey configuration less portable.

**Qt global shortcut via `QAbstractNativeEventFilter`** — low-level and
platform-specific; `pynput` is a higher-level abstraction that supports
multiple platforms.

---

## Consequences

+ Global hotkey works regardless of the focused application on X11 and
  Wayland (with appropriate compositor support).
+ The signal-based cross-thread approach guarantees thread safety; no Qt
  widgets are touched from the pynput thread.
+ Hotkey can be changed at runtime from the Settings dialog without restarting.
- `pynput` on some Wayland compositors requires the application to have
  appropriate permissions (e.g. `sudo` or `input` group); a setup guide is
  provided in the README.
- If two applications register the same hotkey combination, behaviour is
  compositor/OS-dependent; there is no graceful fallback.
- `pynput` listener errors (e.g. display server disconnection) are caught
  and logged but the hotkey silently stops working; the user must restart the
  application.
