# SPDX-License-Identifier: GPL-3.0-or-later
"""Application shutdown routing helpers."""


def cleanup_application(tray_app, instance_checker) -> None:
    """Clean up the tray app when available, or its lock during startup."""
    if tray_app is not None:
        tray_app.cleanup()
    else:
        instance_checker.cleanup()
