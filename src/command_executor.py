import subprocess
from PyQt6.QtCore import QProcess

def execute_command(command):
    """Execute a shell command."""
    print(f"Executing shell command: {command}")
    subprocess.Popen(command, shell=True)
    
def execute_command_process(app, command):
    """Execute a shell command."""
    print(f"Executing shell command: {command}")
    process = QProcess(app)
    process.setProgram("bash")
    process.setArguments(["-c", command])
    return process

def execute_command_process_silently(app, command):
    """Execute a command without showing the output."""
    process = execute_command_process(app, command)
    process.start()