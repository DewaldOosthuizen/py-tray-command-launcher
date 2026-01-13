#  SPDX-License-Identifier: GPL-3.0-or-later

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
import atexit
import signal

if __name__ == "__main__":
    import os
    import getpass
    username = getpass.getuser()
    key = f"py-tray-command-launcher-single-instance-{username}"
    pidfile = os.path.expanduser(f"/tmp/py-tray-command-launcher-{username}.pid")
    app = QApplication(sys.argv)

    # Support --force-unlock argument
    force_unlock = "--force-unlock" in sys.argv
    instance_checker = SingleInstanceChecker(key=key, pidfile=pidfile)

    def cleanup():
        instance_checker.cleanup()

    # Register cleanup for normal exit
    atexit.register(cleanup)

    # Register cleanup for signals (SIGINT, SIGTERM)
    def handle_signal(signum, frame):
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    if force_unlock:
        instance_checker.force_unlock()

    # Retry logic for force unlock from GUI
    while True:
        if instance_checker.is_another_instance_running():
            retry = not instance_checker.show_already_running_message()
            if retry:
                continue
            sys.exit(0)
        if not instance_checker.acquire_lock():
            retry = not instance_checker.show_already_running_message()
            if retry:
                continue
            sys.exit(0)
        break

    # Proceed with normal startup
    tray_app = TrayApp(app, instance_checker)
    tray_app.run()
