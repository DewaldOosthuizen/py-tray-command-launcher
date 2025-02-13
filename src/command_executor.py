import subprocess
from PyQt6.QtCore import QProcess

def execute_command(command):
    """Execute a shell command."""
    print(f"Executing shell command: {command}")
    subprocess.Popen(command, shell=True)
    
def execute_command_process(self, command):
    """Execute a shell command."""
    print(f"Executing shell command: {command}")
    process = QProcess(self.app)
    process.setProgram("bash")
    process.setArguments(["-c", command])
    return process;

def execute_command_process_silently(self, command):
    """Execute a command without showing the output."""
    process = self.execute_command_process(command)
    process.start()