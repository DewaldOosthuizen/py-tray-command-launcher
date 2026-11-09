# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import subprocess
import threading

from PyQt6.QtCore import QObject, QProcess, Qt, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)


class _NotificationDispatcher(QObject):
    """Deliver worker-thread notifications on the QObject's Qt thread."""

    notification_requested = pyqtSignal(str, str)

    def __init__(self, services):
        super().__init__()
        self._services = services
        self.notification_requested.connect(self._notify_user, Qt.ConnectionType.QueuedConnection)

    @pyqtSlot(str, str)
    def _notify_user(self, title: str, message: str) -> None:
        try:
            self._services.notify_user(title=title, message=message)
        except Exception:
            logger.exception("Unable to deliver command completion notification")


class CommandExecutor:
    def __init__(self, services):
        """Initialize with an AppServices instance."""
        self.services = services
        self._notification_dispatcher = _NotificationDispatcher(services)

    def execute_command(self, command: str) -> None:
        """Execute a shell command via subprocess.

        Contract: accepts a ``command`` string, returns ``None``, and never
        raises.  Launch or immediate-execution failures are logged at ERROR
        and surfaced to the user through ``self.services.notify_user``.

        NOTE: shell=True is intentional — this is a user-defined command
        launcher whose commands are authored by the user in commands.json.
        The {promptInput} placeholder is substituted before this call by
        tray_app.execute(), which guarantees the value is sanitised with
        shlex.quote() before reaching this method.  Do not pass untrusted
        external input here.
        """
        logger.info("Executing shell command: %s", command)
        try:
            proc = subprocess.Popen(command, shell=True)  # noqa: S602 — intentional: user-authored command, see method docstring
            logger.debug("Process started (PID %d)", proc.pid)
        except OSError as exc:
            logger.error(
                "Failed to start command '%s': %s",
                command,
                exc,
                extra={"command": command, "error": str(exc)},
            )
            self._notify_launch_failure(command, exc)
            return

        # Detect immediate shell-level failures (e.g. missing executable,
        # permission denied) without blocking or sleeping.
        poll_result = proc.poll()
        if poll_result is not None:
            return_code = proc.returncode
            if return_code is None:
                return_code = poll_result
            if return_code != 0:
                self._report_nonzero_exit(command, return_code)
            return

        threading.Thread(
            target=self._wait_for_completion,
            args=(proc, command),
            name=f"command-wait-{proc.pid}",
            daemon=True,
        ).start()

    def _notify_launch_failure(self, command: str, error: OSError) -> None:
        """Notify the user about a process-creation failure without propagating it."""
        self._notify_user("Command failed", f"Failed to start command '{command}': {error}")

    def _notify_user(self, title: str, message: str) -> None:
        try:
            self.services.notify_user(title=title, message=message)
        except Exception:
            logger.exception("Unable to deliver command failure notification")

    def _wait_for_completion(self, process, command: str) -> None:
        """Wait outside the GUI thread and queue a notification for failed exits."""
        try:
            return_code = process.wait()
        except OSError as exc:
            logger.error(
                "Unable to wait for command '%s' (PID %s): %s",
                command,
                process.pid,
                exc,
                extra={"command": command, "pid": process.pid, "error": str(exc)},
            )
            self._notification_dispatcher.notification_requested.emit(
                "Command failed", f"Unable to track command '{command}': {exc}"
            )
            return
        if return_code != 0:
            self._report_nonzero_exit(command, return_code, process.pid)

    def _report_nonzero_exit(self, command: str, return_code: int, pid: int | None = None) -> None:
        """Log and queue a user notification for one non-zero process exit."""
        if pid is None:
            logger.error(
                "Command '%s' exited immediately with code %s",
                command,
                return_code,
                extra={"command": command, "exit_code": return_code},
            )
            message = f"Command '{command}' exited immediately (exit code {return_code})"
        else:
            logger.error(
                "Command '%s' exited with code %s (PID %s)",
                command,
                return_code,
                pid,
                extra={"command": command, "exit_code": return_code, "pid": pid},
            )
            message = f"Command '{command}' exited (exit code {return_code})"
        if pid is None:
            self._notify_user("Command failed", message)
        else:
            self._notification_dispatcher.notification_requested.emit("Command failed", message)

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
        process.errorOccurred.connect(
            lambda err: logger.error("QProcess error for command '%s': %s", command, err)
        )
        process.finished.connect(
            lambda code, status: (
                logger.warning(
                    "QProcess exited with non-zero code for command '%s': exit_code=%d status=%s",
                    command,
                    code,
                    status,
                )
                if code != 0
                else logger.info(
                    "QProcess finished successfully for command '%s': exit_code=%d status=%s",
                    command,
                    code,
                    status,
                )
            )
        )
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
