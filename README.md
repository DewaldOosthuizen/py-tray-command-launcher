# py-tray-command-launcher

A simple tray application to launch predefined commands.

## Installation

### Install missing system packages

```sh
sudo bash install_packages.sh
```

### Clone the repository

```sh
git clone <repository_url>
cd py-tray-command-launcher
```

### Create a virtual environment

```sh
python3 -m venv venv
```

### Activate the virtual environment

- On Windows:

    ```sh
    venv\Scripts\activate
    ```

- On Unix or MacOS:

    ```sh
    source venv/bin/activate
    ```

### Install dependencies

```sh
pip install -r requirements.txt
```

## Running the App

1. Ensure the virtual environment is activated.

2. Create `commands.json` file in the config directory and define your content. For example:

    ```json
    {
    "System": {
        "Open Terminal": {
            "command": "terminator",
            "showOutput": false,
            "confirm": false
        },
        "System Update": {
            "command": "terminator --command 'bash -c \"sudo apt update; sudo apt upgrade -y; exec bash\"'",
            "showOutput": false,
            "confirm": true
        },
        "xkill": {
            "command": "xkill",
            "showOutput": false,
            "confirm": false
        },
        "Disk Usage": {
            "command": "df -h",
            "showOutput": true,
            "confirm": false
        },
        "Memory Usage": {
            "command": "free -h",
            "showOutput": true,
            "confirm": false
        },
        "System Info": {
            "command": "uname -a",
            "showOutput": true,
            "confirm": false
        },
        "Reboot": {
            "command": "pkexec reboot",
            "showOutput": false,
            "confirm": true
        },
        "Shutdown": {
            "command": "pkexec shutdown now",
            "showOutput": false,
            "confirm": true
        },
        "Cinnamon Reload": {
            "command": "killall -HUP cinnamon",
            "showOutput": false,
            "confirm": true
        },
        "System Report": {
            "command": "mintreport",
            "showOutput": false,
            "confirm": false
        },
        "Kill Process on Port": {
            "command": "pkexec fuser -k {promptInput}/tcp",
            "showOutput": false,
            "confirm": true,
            "prompt": "Enter the port number:"
        }
    },
    "Media": {
        "Youtube Music": {
            "command": "/opt/brave.com/brave/brave-browser --profile-directory=Default --app-id=111",
            "showOutput": false,
            "confirm": false
        }
    },
    "Studies": {
        "Anki": {
            "command": "~/Programs/anki-25.02-linux-qt6/anki",
            "icon": "~/Programs/anki-25.02-linux-qt6/anki.png",
            "showOutput": false,
            "confirm": false
        }
    },
    "Utilities": {
        "Screenshot": {
            "command": "gnome-screenshot -i",
            "showOutput": false,
            "confirm": false
        },
        "CPU-X": {
            "command": "cpu-x",
            "showOutput": false,
            "confirm": false
        },
        "Disk Usage Analyzer": {
            "command": "baobab",
            "showOutput": false,
            "confirm": false
        },
        "System Monitor": {
            "command": "gnome-system-monitor",
            "showOutput": false,
            "confirm": false
        },
        "Text Editor": {
            "command": "geany",
            "showOutput": false,
            "confirm": false
        }
    },
    "Development": {
        "VSCode": {
            "command": "code",
            "showOutput": false,
            "confirm": false
        },
        "Geany": {
            "command": "geany",
            "showOutput": false,
            "confirm": false
        },
        "DBeaver": {
            "command": "dbeaver",
            "icon": "/usr/share/dbeaver-ce/dbeaver.png",
            "showOutput": false,
            "confirm": false
        },
        "Postman": {
            "command": "~/Programs/Postman/Postman",
            "icon": "~/Programs/Postman/app/icons/icon_128x128.png",
            "showOutput": false,
            "confirm": false
        },
        "Docker PS": {
            "command": "terminator --command 'bash -c \"sudo docker ps; exec bash\"'",
            "showOutput": true,
            "confirm": false
        },
        "Docker Images": {
            "command": "terminator --command 'bash -c \"sudo docker images; exec bash\"'",
            "showOutput": true,
            "confirm": false
        }
    },
    "Networking": {
        "Tailscale": {
   "Tailscale Connect": {
    "command": "pkexec tailscale up; tailscale status;",
    "showOutput": true,
    "confirm": false
   },
   "Tailscale Disconnect": {
    "command": "pkexec tailscale down; tailscale status;",
    "showOutput": true,
    "confirm": false
   },
   "Tailscale Status": {
    "command": "systemctl status tailscaled; tailscale status;",
    "showOutput": true,
    "confirm": false
   }
        },
        "Show IP Routes": {
            "command": "ip route show",
            "showOutput": true,
            "confirm": false
        },
        "Show Interfaces": {
            "command": "ip link show",
            "showOutput": true,
            "confirm": false
        },
        "Ping Google": {
            "command": "ping -c 4 google.com",
            "showOutput": true,
            "confirm": false
        },
        "Network Status": {
            "command": "nmcli general status",
            "showOutput": true,
            "confirm": false
        },
        "WiFi Networks": {
            "command": "nmcli device wifi list",
            "showOutput": true,
            "confirm": false
        }
    }
    ```

3. Run the application:

    ```sh
    python3 src/main.py
    ```

    If you are having trouble with your virtual environment not being used, then try:

    ```sh
    venv/bin/python3 src/main.py
    ```

    If you want to run it while not hogging the terminal then:

    - Method 1: Using nohup Command
    You can use the nohup command to run the script in the background and detach it from the terminal.

    ```sh
    nohup python3 src/main.py
    ```

    - Method 2: Using & to Run in Background
    You can simply add & at the end of the command to run the script in the background.

    ```sh
    python3 src/main.py &
    ```

4. Features:

    - Launch applications
    - Launch custom commands
    - Optional confirmation dialog before executing commands
    - Output display for commands that show output (Either through terminal or new window depending on command configuration)
    - Tray icon with menu to launch commands
    - Tray icon with menu to quit the application
    - Tray icon with menu to open the `commands.json` file for editing
    - Ability to reload the app after editing the `commands.json` file
    - App will automatically validate the `commands.json` file structure and prompt the user if there are any issues
  
![Screenshot from 2025-02-12 19-58-12](https://github.com/user-attachments/assets/834e778d-5905-4523-a77b-c533ffb152e9)
