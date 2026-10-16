# SPDX-License-Identifier: GPL-3.0-or-later

"""
Single instance detection utility for py-tray-command-launcher.

This module provides functionality to ensure only one instance of the application
runs at a time using Qt's QSharedMemory mechanism.
"""

import errno
import logging
import os
import tempfile

from PyQt6.QtCore import QSharedMemory
from PyQt6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


class SingleInstanceChecker:
    """
    Utility class to check and prevent multiple instances of the application.

    Uses QSharedMemory to create a unique shared memory segment that serves
    as a lock to detect if another instance is already running.
    """

    def __init__(self, key="py-tray-command-launcher-single-instance-final", pidfile=None):
        """Initialize a checker for a shared-memory instance key.

        Args:
            key (str): Unique identifier for the shared-memory segment.
            pidfile (str, optional): Path for owner PID metadata.

        Returns:
            None

        Raises:
            Exceptions from the Qt shared-memory constructor are propagated.
        """
        self.key = key
        self.shared_memory = QSharedMemory(key)
        self.pidfile = pidfile

    def is_pid_running(self, pid):
        """Return whether a PID is running or cannot be proven absent.

        Args:
            pid: Process identifier to probe.

        Returns:
            bool: False only for an invalid identifier or a confirmed missing process.
                Permission and other probe errors are treated as running.
        """
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return False
        if pid <= 0:
            return False

        try:
            os.kill(pid, 0)
        except OSError as exc:
            return exc.errno != errno.ESRCH
        except Exception:
            return True
        return True

    def _is_stale_lock(self):
        """Return whether attached shared-memory metadata names a dead process.

        A PID is stale only when it is readable, syntactically valid, and the OS
        confirms that the process does not exist. Missing, malformed, and
        unreadable metadata is inconclusive and therefore remains live.
        """
        if not self.shared_memory.isAttached() or not self.pidfile:
            return False
        try:
            with open(self.pidfile, encoding="utf-8") as pid_file:
                pid = pid_file.read().strip()
            parsed_pid = int(pid)
        except (OSError, TypeError, ValueError):
            return False
        if parsed_pid <= 0:
            return False
        return not self.is_pid_running(parsed_pid)

    def _publish_pid_atomically(self, pid):
        """Publish a PID after lock acquisition without exposing partial data.

        The temporary file is created beside the destination so ``os.replace``
        remains atomic on the filesystem containing the PID file.

        Args:
            pid (int): PID of the process that acquired the shared-memory lock.

        Returns:
            None

        Raises:
            No exception is raised for filesystem errors; they are logged and
            the acquired shared-memory lock remains authoritative.
        """
        if not self.pidfile:
            return

        temporary_path = None
        directory = os.path.dirname(os.path.abspath(self.pidfile))
        prefix = f".{os.path.basename(self.pidfile)}."
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=directory, prefix=prefix, delete=False
            ) as pid_file:
                temporary_path = pid_file.name
                pid_file.write(str(pid))
                pid_file.flush()
            os.replace(temporary_path, self.pidfile)
            temporary_path = None
        except OSError as exc:
            logger.warning("Could not write PID file %s: %s", self.pidfile, exc)
        finally:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except OSError as exc:
                    logger.debug("Could not remove temporary PID file %s: %s", temporary_path, exc)

    def force_unlock(self):
        """Release this checker's shared-memory reference, if one can be attached.

        Attaching and detaching removes an orphaned segment when this is the
        final reference, but leaves a segment used by a live owner untouched.
        PID metadata is intentionally retained until a new owner wins creation.

        Returns:
            None

        Raises:
            Exceptions from Qt shared-memory operations are propagated.
        """
        if not self.shared_memory.isAttached():
            self.shared_memory.attach()
        if self.shared_memory.isAttached():
            self.shared_memory.detach()

    def is_another_instance_running(self):
        """Check existing lock metadata while attached to its shared segment.

        This is an observation only; it never grants ownership. Call
        :meth:`acquire_lock` to arbitrate ownership through exclusive creation.

        Returns:
            bool: True when the segment has a live or inconclusive owner, False
                when absent or confirmed stale.

        Raises:
            Exceptions from Qt shared-memory operations are propagated.
        """
        if not self.shared_memory.attach():
            return False
        try:
            stale = self._is_stale_lock()
        finally:
            self.shared_memory.detach()

        if stale:
            logger.warning("Recovered stale single-instance lock left by a crashed process")
            return False
        return True

    def acquire_lock(self):
        """Acquire the lock using shared-memory creation as the sole authority.

        Creation is attempted before PID metadata is consulted. If an existing
        segment is confirmed stale while attached, it is detached before one
        exclusive retry; losing that retry leaves the winner's metadata intact.

        Returns:
            bool: True if this checker created the segment, otherwise False.

        Raises:
            Exceptions from Qt shared-memory operations are propagated.
        """
        if self.shared_memory.create(1):
            self._publish_pid_atomically(os.getpid())
            return True

        if not self.shared_memory.attach():
            return False
        try:
            stale = self._is_stale_lock()
        finally:
            self.shared_memory.detach()

        if not stale:
            return False

        if not self.shared_memory.create(1):
            return False

        logger.warning("Recovered stale single-instance lock left by a crashed process")
        self._publish_pid_atomically(os.getpid())
        return True

    def show_already_running_message(self):
        """
        Show a message dialog informing user that another instance is running.

        Returns:
            bool: True when the caller should exit, False when the caller should retry.

        Raises:
            Qt shared-memory errors are propagated; dialog errors are logged and
            treated as a request to exit.
        """
        # Check if running in headless mode
        qt_platform = os.environ.get("QT_QPA_PLATFORM", "").lower()
        is_headless = qt_platform == "offscreen" or (
            not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")
        )

        pid_info = ""
        stale_lock = False
        existing_pid = None
        if self.pidfile and self.shared_memory.attach():
            try:
                try:
                    with open(self.pidfile, encoding="utf-8") as pid_file:
                        existing_pid = pid_file.read().strip()
                    if existing_pid:
                        stale_lock = self._is_stale_lock()
                        if stale_lock:
                            pid_info = f" (stale lock, PID: {existing_pid})"
                        elif self.is_pid_running(existing_pid):
                            pid_info = f" (PID: {existing_pid})"
                except OSError:
                    pass
            finally:
                self.shared_memory.detach()
        message = f"Another instance of py-tray-command-launcher is already running{pid_info}."
        if is_headless:
            logger.warning(message)
            if stale_lock:
                logger.warning("Stale lock detected. Run with --force-unlock to clear the lock.")
            logger.warning("Only one instance can run at a time. Exiting...")
            return True

        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Application Already Running")
            msg_box.setText(message)
            if stale_lock:
                msg_box.setInformativeText(
                    "A stale lock was detected. Click 'Force Unlock' to clear the lock and start a new instance, or 'OK' to exit."
                )
                msg_box.setStandardButtons(
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Retry
                )
                msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
                # Set button text for Retry (Force Unlock)
                retry_button = msg_box.button(QMessageBox.StandardButton.Retry)
                if retry_button:
                    retry_button.setText("Force Unlock")
                result = msg_box.exec()
                if result == QMessageBox.StandardButton.Retry:
                    self.force_unlock()
                    return False  # Indicate to caller to retry instance check
                return True
            else:
                msg_box.setInformativeText(
                    "Only one instance of the application can run at a time."
                )
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
                result = msg_box.exec()
                return result == QMessageBox.StandardButton.Ok
        except Exception:
            logger.warning(message)
            if stale_lock:
                logger.warning("Stale lock detected. Run with --force-unlock to clear the lock.")
            logger.warning("Only one instance can run at a time. Exiting...")
            return True

    def cleanup(self):
        """Detach this checker's shared-memory reference during shutdown.

        The PID file is retained because it is non-authoritative without a
        segment and removing it could race with a replacement owner.

        Returns:
            None

        Raises:
            Exceptions from Qt shared-memory operations are propagated.
        """
        if self.shared_memory.isAttached():
            self.shared_memory.detach()
