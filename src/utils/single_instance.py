"""
Single instance detection utility for py-tray-command-launcher.

This module provides functionality to ensure only one instance of the application
runs at a time using Qt's QSharedMemory mechanism.
"""

import os
from PyQt6.QtCore import QSharedMemory
from PyQt6.QtWidgets import QMessageBox



class SingleInstanceChecker:
    """
    Utility class to check and prevent multiple instances of the application.
    
    Uses QSharedMemory to create a unique shared memory segment that serves
    as a lock to detect if another instance is already running.
    """

    def __init__(self, key="py-tray-command-launcher-single-instance-final", pidfile=None):
        """
        Initialize the single instance checker.
        Args:
            key (str): Unique identifier for the shared memory segment
            pidfile (str, optional): Path to a file to store the PID of the running instance
        """
        self.key = key
        self.shared_memory = QSharedMemory(key)
        self.pidfile = pidfile

    def is_pid_running(self, pid):
        """
        Check if a process with the given PID is running.
        """
        try:
            pid = int(pid)
            if pid <= 0:
                return False
        except Exception:
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True

    def force_unlock(self):
        """
        Remove the PID file and detach shared memory (force unlock).
        """
        if self.shared_memory.isAttached():
            self.shared_memory.detach()
        if self.pidfile:
            try:
                os.remove(self.pidfile)
            except Exception:
                pass
    
    def is_another_instance_running(self):
        """
        Check if another instance of the application is already running.
        
        Returns:
            bool: True if another instance is running, False otherwise
        """
        # Try to attach to existing shared memory
        if self.shared_memory.attach():
            # Another instance is already running, detach and return True
            self.shared_memory.detach()
            return True
        
        # No existing shared memory found - no other instance running
        return False
    
    def acquire_lock(self):
        """
        Acquire the single instance lock by creating shared memory.
        
        Returns:
            bool: True if lock was acquired (first instance), False otherwise
        """
        # First check if another instance is running
        if self.is_another_instance_running():
            return False
        
        # Try to create new shared memory segment
        if self.shared_memory.create(1):
            # Successfully created - we are the first instance
            if self.pidfile:
                try:
                    with open(self.pidfile, 'w') as f:
                        f.write(str(os.getpid()))
                except Exception:
                    pass
            return True
        # Failed to create - another instance is running
        return False
    
    def show_already_running_message(self):
        """
        Show a message dialog informing user that another instance is running.
        
        Returns:
            bool: True if user clicked OK to close, False otherwise
        """
        # Check if running in headless mode
        qt_platform = os.environ.get('QT_QPA_PLATFORM', '').lower()
        is_headless = qt_platform == 'offscreen' or not os.environ.get('DISPLAY')
        
        pid_info = ""
        stale_lock = False
        existing_pid = None
        if self.pidfile:
            try:
                with open(self.pidfile, 'r') as f:
                    existing_pid = f.read().strip()
                if existing_pid:
                    if self.is_pid_running(existing_pid):
                        pid_info = f" (PID: {existing_pid})"
                    else:
                        pid_info = f" (stale lock, PID: {existing_pid})"
                        stale_lock = True
            except Exception:
                pass
        message = f"Another instance of py-tray-command-launcher is already running{pid_info}."
        if is_headless:
            print(message)
            if stale_lock:
                print("Stale lock detected. Run with --force-unlock to clear the lock.")
            print("Only one instance can run at a time. Exiting...")
            return True
        
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Application Already Running")
            msg_box.setText(message)
            if stale_lock:
                msg_box.setInformativeText("A stale lock was detected. Click 'Force Unlock' to clear the lock and start a new instance, or 'OK' to exit.")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Retry)
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
                msg_box.setInformativeText("Only one instance of the application can run at a time.")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
                result = msg_box.exec()
                return result == QMessageBox.StandardButton.Ok
        except Exception:
            print(message)
            if stale_lock:
                print("Stale lock detected. Run with --force-unlock to clear the lock.")
            print("Only one instance can run at a time. Exiting...")
            return True
    
    def cleanup(self):
        """
        Clean up shared memory resources.
        
        Note: QSharedMemory automatically handles cleanup when the process exits,
        but this method can be called for explicit cleanup if needed.
        """
        if self.shared_memory.isAttached():
            self.shared_memory.detach()
        if self.pidfile:
            try:
                os.remove(self.pidfile)
            except Exception:
                pass