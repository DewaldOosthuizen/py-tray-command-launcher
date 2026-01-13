# py-tray-command-launcher

A simple and lightweight tray application developed in Python. It allows users to easily launch custom commands or scripts directly from the system tray, enhancing productivity and quick access to frequently used operations. The application is designed with flexibility and user convenience in mind, supporting a variety of use cases such as script execution, command shortcuts, and task automation.

---

## Table of Contents

- [py-tray-command-launcher](#py-tray-command-launcher)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Installation and Packaging](#installation-and-packaging)
    - [Pre-built Packages](#pre-built-packages)
    - [Quick Package Build](#quick-package-build)
    - [Development Installation](#development-installation)
  - [Installation](#installation)
    - [1. Install Required System Packages](#1-install-required-system-packages)
    - [2. Clone the Repository](#2-clone-the-repository)
    - [3. Create and Activate a Virtual Environment](#3-create-and-activate-a-virtual-environment)
    - [4. Install Python Dependencies](#4-install-python-dependencies)
  - [Configuration](#configuration)
  - [Running the App](#running-the-app)
  - [Screenshots](#screenshots)
  - [Contributing](#contributing)
  - [Issues](#issues)
  - [License](#license)
  - [Detailed Features](#detailed-features)
  - [Future Enhancements](#future-enhancements)

---

## Features

- **System Tray Integration:** Seamlessly integrates with your system's notification area.
- **Hierarchical Command Menu:** Organizes commands in categories and subcategories.
- **Custom Icons:** Support for custom icons for each category and command.
- **Command Execution:** Execute shell commands directly from the tray menu.
- **Multi-platform Support:** Works on Linux, with Windows support via `win-commands.json`.
- **Confirmation Dialogs:** Optionally require confirmation before executing potentially dangerous commands.
- **Output Display:** Show command output in a dedicated window when needed.
- **Input Prompts:** Prompt for user input with customizable messages using the `{promptInput}` placeholder.
- **Command Search:** Quickly find and execute any command using the search dialog.
- **Recent Commands:** Access recently executed commands from the "Recent Commands" menu.
- **Command Creator:** Create new commands via a user-friendly dialog without editing JSON directly.
- **JSON Editor:** Direct access to edit the `commands.json` configuration file.
- **App Restart:** Reload the application after making changes to the configuration.
- **Backup and Restore:** Create timestamped backups and restore or import/export command groups.
- **Favorites:** Add frequently used commands to a Favorites section.
- **Clean UI:** Well-organized menu structure with icons, output, confirmation, and input dialogs.
- **Robust Configuration:** Simple, human-readable JSON format with automatic validation.
- **Process Management:** Proper handling of command execution and output capture.
- **Error Handling:** Graceful error handling with informative messages.
- **Virtual Environment Support:** Works within Python virtual environments.
- **Easy Packaging:** Available as standalone executables, .deb packages, AppImages, and Windows .exe

---

## Installation and Packaging

### Pre-built Packages

For easy installation, you can build ready-to-use packages:

- **Linux Executable**: Standalone executable (63MB) - no installation required
- **Debian Package (.deb)**: For Ubuntu/Debian systems with desktop integration
- **AppImage**: Universal Linux format that works on most distributions
- **Windows Executable (.exe)**: For Windows systems - no installation required

### Quick Package Build

```sh
# Build all package formats (Linux)
./scripts/build-all.sh

# Build specific formats
./scripts/build-linux.sh      # Linux executable
./scripts/build-deb.sh        # Debian package  
./scripts/build-appimage.sh   # AppImage
scripts\build-windows.bat     # Windows (run on Windows)
```

See [BUILD.md](BUILD.md) for detailed build instructions and troubleshooting.

### Development Installation

- **Output Display:** Show command output in a dedicated window when needed.
- **Input Prompts:** Prompt for user input with customizable messages using the `{promptInput}` placeholder.
- **Command Search:** Quickly find and execute any command using the search dialog.
- **Recent Commands:** Access recently executed commands from the "Recent Commands" menu.
- **Command Creator:** Create new commands via a user-friendly dialog without editing JSON directly.
- **JSON Editor:** Direct access to edit the `commands.json` configuration file.
- **App Restart:** Reload the application after making changes to the configuration.
- **Backup and Restore:** Create timestamped backups and restore or import/export command groups.
- **Favorites:** Add frequently used commands to a Favorites section.
- **Clean UI:** Well-organized menu structure with icons, output, confirmation, and input dialogs.
- **Robust Configuration:** Simple, human-readable JSON format with automatic validation.
- **Process Management:** Proper handling of command execution and output capture.
- **Error Handling:** Graceful error handling with informative messages.
- **Virtual Environment Support:** Works within Python virtual environments.

---

## Installation

### 1. Clone the Repository

```sh
git clone <repository_url>
cd py-tray-command-launcher
```

### 2. Install Required System Packages

```sh
sudo bash ./scripts/install_packages.sh
```

### 3. Create and Activate a Virtual Environment

```sh
python3 -m venv venv
```

- **On Windows:**

    ```sh
    venv\Scripts\activate
    ```

- **On Unix or macOS:**

    ```sh
    source venv/bin/activate
    ```

### 4. Install Python Dependencies

```sh
pip install -r requirements.txt
```

---

## Configuration

Create a `commands.json` file in the `config` directory to define your commands. Example structure:

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
        }
        // ... more commands
    },
    "Media": {
        "Youtube Music": {
            "command": "/opt/brave.com/brave/brave-browser --profile-directory=Default --app-id=111",
            "showOutput": false,
            "confirm": false
        }
    }
    // ... more categories
}
```

- Use `{promptInput}` in commands to prompt for user input.
- Specify `"icon"` for custom icons.
- Specify `"showOutput"` if the output should be displayed in a separate window.
- Set `"confirm": true` for commands that require confirmation.

---

## Running the App

1. **Activate the virtual environment.**
2. **Run the application:**

    ```sh
    python3 src/main.py
    ```

    If you encounter issues with the virtual environment, try:

    ```sh
    venv/bin/python3 src/main.py
    ```

3. **Run in the background:**
    - Using `nohup`:

        ```sh
        nohup python3 src/main.py &
        ```

    - Using `&`:

        ```sh
        python3 src/main.py &
        ```

---

## Screenshots

![Screenshot from 2025-02-12 19-58-12](https://github.com/user-attachments/assets/834e778d-5905-4523-a77b-c533ffb152e9)

---

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository.
2. Create a new branch:

    ```sh
    git checkout -b feature-name
    ```

3. Make your changes and commit:

    ```sh
    git commit -m "Add feature-name: description of changes"
    ```

4. Push to your fork:

    ```sh
    git push origin feature-name
    ```

5. Open a pull request with a detailed description.

---

## Issues

If you encounter issues or have feature requests, open an issue in the [GitHub Issues](https://github.com/user/repository/issues) section. Please provide as much detail as possible.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Detailed Features

The py-tray-command-launcher currently provides the following capabilities:

- Launch custom shell commands and scripts directly from the system tray.
- Organize commands into hierarchical categories and subcategories.
- Assign custom icons to categories and individual commands.
- Search for commands using a built-in search dialog.
- Prompt for user input using `{promptInput}` placeholders in commands.
- Display command output in a dedicated window when required.
- Require confirmation before executing sensitive commands.
- Track and access recently executed commands.
- Add commands to a Favorites section for quick access.
- Create new commands via a graphical command creator dialog.
- Edit the configuration JSON directly from the UI.
- Backup and restore command configurations with timestamped backups.
- Import/export command groups for sharing or migration.
- Reload the application to apply configuration changes instantly.
- Robust error handling and informative messages.
- Works within Python virtual environments.
- Supports Linux and Windows (via separate config).
- Clean, organized UI with icons and dialogs.
- Encrypt/decrypt files/folder
- Single instance enforcement
- Packaging for easy installation (e.g., DEB, RPM, EXE)

---

## Future Enhancements

- Global keyboard shortcuts for frequently used commands
- Auto-start on system boot
- Command scheduling and automation
- Themes and appearance customization
- Scripting support for advanced command sequences
- AI Search Integration for command suggestions

Stay tuned for updates, and feel free to suggest additional features!
