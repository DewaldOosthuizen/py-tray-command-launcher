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
