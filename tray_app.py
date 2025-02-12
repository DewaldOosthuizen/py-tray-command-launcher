import os
import sys
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QMessageBox
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QProcess
from output_window import OutputWindow
from command_executor import execute_command
from utils import load_commands

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_FILE = os.path.join(BASE_DIR, "icons/icon.png")

class TrayApp:
    def __init__(self, app):
        self.app = app
        self.app.aboutToQuit.connect(self.cleanup)
        # Keep the app running even if all windows are closed
        self.app.setQuitOnLastWindowClosed(False)
        self.tray_icon = QSystemTrayIcon(QIcon(ICON_FILE))
        self.tray_icon.setVisible(True)
        self.menu = QMenu()
        self.load_tray_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        self.output_windows = []

    def cleanup(self):
        """Perform any cleanup before quitting."""
        print("Cleaning up before exit...")
        for window in self.output_windows:
            window.close()

    def load_tray_menu(self):
        """Load commands into the tray menu."""
        commands = load_commands()
        for group, items in commands.items():
            submenu = QMenu(group, self.menu)
            for label, item in items.items():
                if isinstance(item, dict):
                    command = item.get("command")
                    icon_path = os.path.join(BASE_DIR, item.get("icon", ICON_FILE))
                    show_output = item.get("showOutput", False)
                    confirm = item.get("confirm", False)
                    action = QAction(QIcon(icon_path), label, self.menu)
                    if show_output:
                        action.triggered.connect(lambda _, cmd=command, lbl=label, conf=confirm: self.execute_with_confirmation(lbl, cmd, conf, show_output=True))
                    else:
                        action.triggered.connect(lambda _, cmd=command, conf=confirm: self.execute_with_confirmation(None, cmd, conf, show_output=False))
                    submenu.addAction(action)
                else:
                    action = QAction(label, self.menu)
                    action.triggered.connect(lambda _, cmd=item: execute_command(cmd))
                    submenu.addAction(action)
            self.menu.addMenu(submenu)
        self.menu.addSeparator()
        self.menu.addAction("Exit", self.confirm_exit)
        self.menu.addAction("Force Quit", self.confirm_force_quit)

    def execute_with_confirmation(self, title, command, confirm, show_output):
        """Execute a command with optional confirmation."""
        if confirm:
            reply = QMessageBox.question(None, 'Confirmation',
                                        f'Are you sure you want to execute "{command}"?',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        if show_output:
            self.show_command_output(title, command)
        else:
            execute_command(command)
    
    def show_command_output(self, title, command):
        """Execute a command and show the output in a new window."""
        process = QProcess(self.app)  # Use self.app as the parent
        process.setProgram("bash")
        process.setArguments(["-c", command])
        
        def handle_finished(exit_code, exit_status):
            stdout = process.readAllStandardOutput().data().decode()
            stderr = process.readAllStandardError().data().decode()
            output = stdout if stdout else stderr

            output_window = OutputWindow(title, output, parent=self.app.activeWindow())  # Ensure app stays alive
            self.output_windows.append(output_window)

            # Ensure it is removed when closed
            output_window.destroyed.connect(lambda: self.output_windows.remove(output_window) if output_window in self.output_windows else None)
            output_window.show()

        process.finished.connect(handle_finished)
        process.start()

    def confirm_exit(self):
        """Show confirmation dialog for exiting the application."""
        reply = QMessageBox.question(None, 'Exit Confirmation',
                                     'Are you sure you want to exit?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.app.quit()

    def confirm_force_quit(self):
        """Show confirmation dialog for force quitting the application."""
        reply = QMessageBox.question(None, 'Force Quit Confirmation',
                                     'Are you sure you want to force quit?',
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.force_quit()

    def force_quit(self):
        """Force quit the application."""
        self.cleanup()
        sys.exit()
        QCoreApplication.exit()

    def run(self):
        sys.exit(self.app.exec())