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
    
    def __init__(self, key="py-tray-command-launcher-single-instance-final"):
        """
        Initialize the single instance checker.
        
        Args:
            key (str): Unique identifier for the shared memory segment
        """
        self.key = key
        self.shared_memory = QSharedMemory(key)
    
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
        
        if is_headless:
            # In headless mode, just print the message
            print("Another instance of py-tray-command-launcher is already running.")
            print("Only one instance can run at a time. Exiting...")
            return True
        
        try:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Application Already Running")
            msg_box.setText("Another instance of py-tray-command-launcher is already running.")
            msg_box.setInformativeText("Only one instance of the application can run at a time.")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)
            
            # Show the dialog and return True when OK is clicked
            result = msg_box.exec()
            return result == QMessageBox.StandardButton.Ok
        except Exception as e:
            # In case of any GUI issues, print message and return True
            print(f"Another instance of py-tray-command-launcher is already running.")
            print(f"Only one instance can run at a time. Exiting...")
            return True
    
    def cleanup(self):
        """
        Clean up shared memory resources.
        
        Note: QSharedMemory automatically handles cleanup when the process exits,
        but this method can be called for explicit cleanup if needed.
        """
        if self.shared_memory.isAttached():
            self.shared_memory.detach()