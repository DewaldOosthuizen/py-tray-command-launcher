import sys
from PyQt6.QtWidgets import QApplication
from core.tray_app import TrayApp
from utils.single_instance import SingleInstanceChecker

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Check if another instance is already running
    instance_checker = SingleInstanceChecker()

    if instance_checker.is_another_instance_running():
        # Show message and exit if another instance is running
        instance_checker.show_already_running_message()
        sys.exit(0)

    # Acquire the lock to prevent other instances
    if not instance_checker.acquire_lock():
        # Failed to acquire lock, another instance started concurrently
        instance_checker.show_already_running_message()
        sys.exit(0)

    # Proceed with normal startup
    tray_app = TrayApp(app, instance_checker)
    tray_app.run()
