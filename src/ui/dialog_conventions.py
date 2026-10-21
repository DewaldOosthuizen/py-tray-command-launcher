# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared layout and available-screen sizing conventions for retained dialogs."""

from PyQt6.QtWidgets import QApplication

DIALOG_CONTENT_MARGIN = 12
DIALOG_LAYOUT_SPACING = 12


def configure_dialog_layout(layout) -> None:
    """Apply the shared content margins and spacing to a dialog layout.

    Args:
        layout: A Qt layout owned by the dialog.

    Returns:
        None.
    """
    layout.setContentsMargins(
        DIALOG_CONTENT_MARGIN,
        DIALOG_CONTENT_MARGIN,
        DIALOG_CONTENT_MARGIN,
        DIALOG_CONTENT_MARGIN,
    )
    layout.setSpacing(DIALOG_LAYOUT_SPACING)


def responsive_dialog_size(dialog, preferred: tuple[int, int], minimum: tuple[int, int]) -> None:
    """Set a dialog's preferred and minimum size within the primary screen bounds.

    When Qt has no usable screen geometry (for example, under a lightweight test
    stub), the supplied sizes are retained. A real screen reserves a small edge
    margin so the dialog never starts larger than its available display area.

    Args:
        dialog: Dialog to size.
        preferred: Preferred (width, height) in logical pixels.
        minimum: Minimum (width, height) in logical pixels before screen clamping.

    Returns:
        None.
    """
    screen = QApplication.primaryScreen()
    geometry = screen.availableGeometry() if screen is not None else None
    width = geometry.width() if geometry is not None else None
    height = geometry.height() if geometry is not None else None
    if not isinstance(width, int) or not isinstance(height, int):
        dialog.setMinimumSize(*minimum)
        dialog.resize(*preferred)
        return

    available_width = max(1, width - 24)
    available_height = max(1, height - 24)
    minimum_size = (
        min(minimum[0], available_width),
        min(minimum[1], available_height),
    )
    preferred_size = (
        max(minimum_size[0], min(preferred[0], available_width)),
        max(minimum_size[1], min(preferred[1], available_height)),
    )
    dialog.setMinimumSize(*minimum_size)
    dialog.resize(*preferred_size)


def responsive_minimum_width(dialog, preferred_width: int) -> None:
    """Clamp a dialog's minimum width so it remains reachable on narrow displays."""
    screen = QApplication.primaryScreen()
    geometry = screen.availableGeometry() if screen is not None else None
    width = geometry.width() if geometry is not None else None
    if isinstance(width, int):
        preferred_width = min(preferred_width, max(1, width - 24))
    dialog.setMinimumWidth(preferred_width)
