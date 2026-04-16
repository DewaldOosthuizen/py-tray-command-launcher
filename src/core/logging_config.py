# SPDX-License-Identifier: GPL-3.0-or-later

"""Centralized logging configuration for py-tray-command-launcher."""

import logging
import os
from typing import Optional

LOG_LEVEL_ENV_VAR = "PY_TRAY_LOG_LEVEL"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def _parse_log_level(level_name: Optional[str]) -> int:
    """Parse a textual log level into a logging module integer level."""
    if not level_name:
        return getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO)

    normalized = str(level_name).strip().upper()
    level = getattr(logging, normalized, None)
    if isinstance(level, int):
        return level
    return getattr(logging, DEFAULT_LOG_LEVEL, logging.INFO)


def resolve_log_level(config_level: Optional[str] = None) -> int:
    """Resolve effective log level using config default and env override."""
    env_level = os.getenv(LOG_LEVEL_ENV_VAR)
    if env_level:
        return _parse_log_level(env_level)
    return _parse_log_level(config_level)


def configure_logging(config_level: Optional[str] = None) -> int:
    """Configure root logging once and return the resolved log level."""
    resolved_level = resolve_log_level(config_level)
    root_logger = logging.getLogger()

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT))
        root_logger.addHandler(handler)

    root_logger.setLevel(resolved_level)
    return resolved_level
