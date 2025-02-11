import subprocess

def execute_command(command):
    """Execute a shell command."""
    print(f"Executing shell command: {command}")
    subprocess.Popen(command, shell=True)