# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import subprocess

from PyQt6.QtCore import QProcess

logger = logging.getLogger(__name__)


class CommandExecutor:
    def __init__(self, services):
        """Initialize with an AppServices instance."""
        self.services = services

    def execute_command(self, command):
        """Execute a shell command via subprocess.

        NOTE: shell=True is intentional — this is a user-defined command
        launcher whose commands are authored by the user in commands.json.
        The {promptInput} placeholder is substituted before this call by
        tray_app.execute(), which guarantees the value is sanitised with
        shlex.quote() before reaching this method.  Do not pass untrusted
        external input here.
        """
        logger.info("Executing shell command: %s", command)
        proc = subprocess.Popen(command, shell=True)  # noqa: S602 — intentional: user-authored command, see method docstring
        logger.debug("Process started (PID %d)", proc.pid)

    def execute_command_process(self, app, command):
        """Start a shell command as a tracked QProcess and return the running handle.

        NOTE: Any {promptInput} placeholder in `command` is guaranteed to have
        been substituted with a shlex.quote()-sanitised value by tray_app.execute()
        before this method is called.
        """
        logger.info("Starting QProcess for command: %s", command)
        process = QProcess(app)
        process.setProgram("bash")
        process.setArguments(["-c", command])
        process.start()
        logger.debug("QProcess started (program: bash -c %s)", command)
        return process

    def execute_command_process_silently(self, app, command):
        """Execute a command without showing the output.

        Delegates to execute_command_process, which starts the QProcess
        internally.  Do NOT call process.start() here again.
        """
        self.execute_command_process(app, command)
        # process.start() is already called inside execute_command_process.
        logger.debug("QProcess started silently for command: %s", command)
