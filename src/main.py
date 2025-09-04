# Attempt to import required modules for the application.
try:
    # Import QApplication for GUI, TrayApp for tray logic, and SingleInstanceChecker for instance control.
    from PyQt6.QtWidgets import QApplication
    from core.tray_app import TrayApp
    from utils.single_instance import SingleInstanceChecker
except ImportError as e:
    # If an import fails, print a helpful error message to stderr.
    import sys
    print(
        f"Missing dependency: {e}. Please run 'pip install -r requirements.txt' and try again.",
        file=sys.stderr
    )
    # Try to show a GUI error dialog if possible.
    try:
        from PyQt6.QtWidgets import QMessageBox, QApplication
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Missing Dependency",
            f"{e}\n\nPlease run:\n\npip install -r requirements.txt"
        )
    except Exception:
        # If even the error dialog fails, silently ignore.
        pass
    # Exit the program with error status.
    sys.exit(1)

import sys

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
