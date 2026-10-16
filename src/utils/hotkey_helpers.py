# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared hotkey-to-pynput conversion helpers."""

_PYNPUT_WRAP = {
    "ctrl",
    "shift",
    "alt",
    "altgr",
    "cmd",
    "win",
    "super",
    "meta",
    "space",
    "enter",
    "return",
    "tab",
    "esc",
    "escape",
    "backspace",
    "delete",
    "insert",
    "home",
    "end",
    "page_up",
    "page_down",
    "up",
    "down",
    "left",
    "right",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "f6",
    "f7",
    "f8",
    "f9",
    "f10",
    "f11",
    "f12",
}


def to_pynput_str(hotkey: str) -> str:
    """Convert 'ctrl+shift+space' to '<ctrl>+<shift>+<space>' for pynput."""
    parts = []
    for k in hotkey.lower().split("+"):
        k = k.strip()
        parts.append(f"<{k}>" if (k in _PYNPUT_WRAP or len(k) > 1) else k)
    return "+".join(parts)


def safe_unregister(handle, timeout: float = 2.0):
    """Stop *handle* (if any), attempt a bounded join, then return None."""
    if handle is None:
        return None
    try:
        handle.stop()
    except Exception:  # noqa: S110 — best-effort cleanup; stop failure must not raise during deregistration
        pass
    try:
        join = getattr(handle, "join", None)
        if callable(join):
            join(timeout=timeout)
    except Exception:  # noqa: S110 — best-effort cleanup; a failing stop must not raise during deregistration
        pass
    return None


def safe_register(existing_handle, factory, timeout: float = 2.0):
    """Stop existing handle (if any) then call factory() to create a new one.

    Returns the new handle returned by factory().
    """
    safe_unregister(existing_handle, timeout=timeout)
    return factory()
