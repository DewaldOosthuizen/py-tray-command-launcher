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

2. Create `commands.json` file in the root directory and define your content. For example:

    ```json
    {
        "System": {
            "Open Terminal": {
                "command": "terminator",
                "showOutput": false
            },
            "System Update": {
                "command": "terminator --command 'bash -c \"sudo apt update; sudo apt upgrade -y; exec bash\"'",
                "showOutput": false
            },
            "xkill": {
                "command": "xkill",
                "showOutput": false
            }
        },
        "Media": {
            "Youtube Music": {
                "command": "/opt/brave.com/brave/brave-browser --profile-directory=Default --app-id=111",
                "showOutput": false
            }
        },
        "Utilities": {
            "Screenshot": {
                "command": "gnome-screenshot -i",
                "icon": "org.gnome.Screenshot",
                "showOutput": false
            }
        },
        "Development": {
            "VSCode": {
                "command": "code",
                "showOutput": false
            },
            "DBeaver": {
                "command": "dbeaver",
                "icon": "/usr/share/dbeaver-ce/dbeaver.png",
                "showOutput": false
            }
        },
        "Networking": {
            "Tailscale Status": {
                "command": "tailscale status",
                "showOutput": true
            },
            "Show IP Routes": {
                "command": "ip route show",
                "showOutput": true
            },
            "Show Interfaces": {
                "command": "ip link show",
                "showOutput": true
            }
        }
    }
    ```

3. Run the application:

    ```sh
    python3 main.py
    ```

    If you are having trouble with your virtual environment not being used, then try:

    ```sh
    .venv/bin/python3 main.py
    ```
