#  SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import subprocess
from PyQt6.QtCore import QProcess

logger = logging.getLogger(__name__)


class CommandExecutor:
    def __init__(self, services):
        """Initialize with an AppServices instance."""
        self.services = services

    def execute_command(self, command):
        """Execute a shell command."""
        logger.info("Executing shell command: %s", command)
        subprocess.Popen(command, shell=True)

    def execute_command_process(self, app, command):
        """Execute a shell command."""
        logger.info("Executing shell command process: %s", command)
        process = QProcess(app)
        process.setProgram("bash")
        process.setArguments(["-c", command])
        return process

    def execute_command_process_silently(self, app, command):
        """Execute a command without showing the output."""
        process = self.execute_command_process(app, command)
        process.start()
