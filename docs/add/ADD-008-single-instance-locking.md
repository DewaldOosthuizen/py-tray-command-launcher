# ADD-008 — Single-instance locking — QSharedMemory + PID file

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2024-01-01 |
| Deciders | Project author |
| Tags | single-instance, ipc, locking |

---

## Context

The application manages a single system tray icon and a single set of open
dialogs.  Running two instances simultaneously would produce two tray icons,
conflicting writes to `commands.json`, and confusing duplicate output windows.
A mechanism to detect and prevent a second instance was needed.

---

## Decision

`SingleInstanceChecker` (in `utils/single_instance.py`) uses a two-layer
locking strategy:

### Layer 1 — QSharedMemory

`QSharedMemory` (from `PyQt6.QtCore`) creates a named region in the OS shared
memory pool.  The key is derived from the application name:

- If `acquire_lock()` successfully calls `create()`, this is the first
  instance.
- If `attach()` succeeds, another instance already created the region and is
  running — `acquire_lock()` returns `False`.

`QSharedMemory` segments are automatically released when the `QApplication`
object is destroyed, making cleanup reliable even on unclean exits.

### Layer 2 — PID file

On successful lock, the current PID is written to a platform-appropriate PID
file path (e.g. `/tmp/py-tray-launcher.pid`).  On startup failure detection,
the PID is read back and validated with `is_pid_running(pid)` (sends signal 0)
to detect stale locks left by a crashed prior instance.

Write errors on the PID file are logged at WARNING level and do not prevent
the application from starting — the `QSharedMemory` lock is sufficient for
correctness.

### `--force-unlock` CLI flag

`main.py` exposes `--force-unlock` which calls `SingleInstanceChecker.force_unlock()`
to delete the PID file and detach the shared memory segment.  This is a
recovery escape hatch for situations where the OS did not clean up the
shared memory region automatically (can happen with some virtualised
environments).

### Headless / display-less detection

Before showing the "already running" error dialog, `SingleInstanceChecker`
checks whether a display is available:

```python
is_headless = qt_platform == 'offscreen' or (
    not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY')
)
```

Both `DISPLAY` (X11) and `WAYLAND_DISPLAY` (Wayland native sessions) are
checked so that pure-Wayland sessions are correctly identified as having a
display available.

---

## Alternatives considered

**File lock only (fcntl / LockFileEx)** — platform-specific APIs; `QSharedMemory`
is already available and cross-platform.

**D-Bus activation** — the canonical Linux approach for single-instance
applications.  Rejected: adds a D-Bus dependency and does not work on Windows
or macOS without additional libraries.

**Socket-based lock (bind to a known port)** — simple but reserves a port
number and fails in restricted network environments.

---

## Consequences

+ Works across X11 and Wayland without change; the display detection correctly
  suppresses the GUI error dialog in headless/CI environments.
+ `--force-unlock` gives users a self-service recovery path without needing to
  use `ipcrm` or reboot.
+ OSError on PID file cleanup is logged at DEBUG rather than silently swallowed,
  making diagnostics easier.
- `QSharedMemory` segment names are global on macOS (kernel-level); a name
  collision with another application using the same key string is theoretically
  possible.
- The two-layer approach adds complexity; in practice the PID file layer is
  mostly useful for diagnostics rather than locking correctness.
