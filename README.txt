# py-tray

## Installation


# install missing system packages
```sh
sudo bash install_packages.sh
```

Then:

1. Clone the repository:
    ```sh
    git clone <repository_url>
    cd py-tray
    ```

2. Create a virtual environment:
    ```sh
    python3 -m venv venv
    ```

3. Activate the virtual environment:
    - On Windows:
        ```sh
        venv\Scripts\activate
        ```
    - On Unix or MacOS:
        ```sh
        source venv/bin/activate
        ```

4. Install dependencies:
    ```sh
    pip install -r requirements.txt
    ```

## Running the App

1. Ensure the virtual environment is activated.

2. Create commands.json file in root directory and define your content. e.g.
```json
{
    "System": {
        "Open Terminal": "terminator"
    },
    "Media": {
        "Youtube Music": "/opt/brave.com/brave/brave-browser --profile-directory=Default --app-id=123"
    },
    "Utilities": {
        "Connect Tailscale": "terminator --command 'bash -c \"sudo tailscale up; exec bash\"'"
    }
}

```

3. Run the application:
    ```sh
    python3 main.py
    ```