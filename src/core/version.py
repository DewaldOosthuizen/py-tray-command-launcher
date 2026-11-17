# SPDX-License-Identifier: GPL-3.0-or-later
"""Application version discovery and CalVer validation."""

from __future__ import annotations

import datetime
import logging
import re
from importlib import metadata

logger = logging.getLogger(__name__)
_CALVER_PATTERN = re.compile(r"^([0-9]{4})\.([0-9]{2})\.([0-9]{2})(?:\.([1-9][0-9]*))?$")


def get_current_version() -> str:
    """Return the bundled version, installed package version, or a safe fallback.

    Returns:
        The version string resolved for this running application.
    """
    try:
        from _version import __version__

        if isinstance(__version__, str) and __version__:
            return __version__
    except (ImportError, AttributeError):
        logger.debug("No bundled version module is available")

    try:
        return metadata.version("py-tray-command-launcher")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def parse_calver(version: str) -> tuple[int, ...] | None:
    """Parse a valid YYYY.MM.DD[.N] release tag into an integer tuple.

    Args:
        version: Candidate release version string.

    Returns:
        A sortable tuple for a valid date and optional positive same-day release
        number; ``None`` for development versions or invalid calendar values.
    """
    if not isinstance(version, str):
        return None
    match = _CALVER_PATTERN.fullmatch(version)
    if match is None:
        return None

    year, month, day, release_number = match.groups()
    try:
        datetime.date(int(year), int(month), int(day))
        date_tuple = (int(year), int(month), int(day))
        if release_number:
            date_tuple += (int(release_number),)
    except ValueError:
        return None
    return date_tuple


VERSION = get_current_version()
