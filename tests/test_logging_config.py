#  SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.logging_config import (  # noqa: E402
    DEFAULT_LOG_LEVEL,
    LOG_LEVEL_ENV_VAR,
    configure_logging,
    resolve_log_level,
)


class LoggingConfigTests(unittest.TestCase):
    def setUp(self):
        self.root_logger = logging.getLogger()
        self.original_handlers = list(self.root_logger.handlers)
        self.original_level = self.root_logger.level

    def tearDown(self):
        self.root_logger.handlers = self.original_handlers
        self.root_logger.setLevel(self.original_level)

    def test_resolve_uses_config_level_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(LOG_LEVEL_ENV_VAR, None)
            self.assertEqual(resolve_log_level("debug"), logging.DEBUG)

    def test_resolve_env_overrides_config_level(self):
        with patch.dict(os.environ, {LOG_LEVEL_ENV_VAR: "ERROR"}, clear=False):
            self.assertEqual(resolve_log_level("DEBUG"), logging.ERROR)

    def test_resolve_invalid_level_falls_back_to_default(self):
        with patch.dict(os.environ, {LOG_LEVEL_ENV_VAR: "not-a-level"}, clear=False):
            default_level = getattr(logging, DEFAULT_LOG_LEVEL)
            self.assertEqual(resolve_log_level("DEBUG"), default_level)

    def test_configure_logging_is_idempotent_for_handlers(self):
        self.root_logger.handlers = []

        first_level = configure_logging("INFO")
        first_handler_count = len(self.root_logger.handlers)

        second_level = configure_logging("DEBUG")
        second_handler_count = len(self.root_logger.handlers)

        self.assertEqual(first_handler_count, 1)
        self.assertEqual(second_handler_count, 1)
        self.assertEqual(first_level, logging.INFO)
        self.assertEqual(second_level, logging.DEBUG)


if __name__ == "__main__":
    unittest.main()
