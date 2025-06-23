import os
import subprocess
from PyQt6.QtCore import QProcess


class CommandExecutor:
    def __init__(self, app):
        """Initialize with reference to the main app."""
        self.app = app
        self.BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def execute_command(self, command):
        """Execute a shell command."""
        print(f"Executing shell command: {command}")
        subprocess.Popen(command, shell=True)

    def execute_command_process(self, app, command):
        """Execute a shell command."""
        print(f"Executing shell command: {command}")
        process = QProcess(app)
        process.setProgram("bash")
        process.setArguments(["-c", command])
        return process

    def execute_command_process_silently(self, app, command):
        """Execute a command without showing the output."""
        process = self.execute_command_process(app, command)
        process.start()
