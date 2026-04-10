# py-tray-command-launcher

A Python system tray application for launching custom commands and scripts from a hierarchical menu. Supports file encryption, command scheduling, backup/restore, favorites, command search, and packaging for Linux and Windows.

---

## Table of Contents

- [py-tray-command-launcher](#py-tray-command-launcher)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Installation](#installation)
    - [1. Clone the repository](#1-clone-the-repository)
    - [2. Install system dependencies](#2-install-system-dependencies)
    - [3. Create and activate a virtual environment](#3-create-and-activate-a-virtual-environment)
    - [4. Install Python dependencies](#4-install-python-dependencies)
  - [Configuration](#configuration)
  - [Running the App](#running-the-app)
  - [Packaging](#packaging)
  - [Documentation](#documentation)
  - [Screenshots](#screenshots)
  - [Contributing](#contributing)
  - [License](#license)

---

## Features

- **Hierarchical Command Menu** — Organise commands into categories, each with a custom icon
- **Command Execution** — Run shell commands with optional output display, confirmation dialogs, and user-input prompts (`{promptInput}`)
- **Command Search** — Find and execute any command by name across all categories
- **Favorites** — Pin frequently used commands for one-click access
- **Recent Commands** — Re-run previously executed commands from the history submenu
- **Command Creator** — Add new commands through a GUI dialog (no JSON editing required)
- **Backup and Restore** — Timestamped backups of your command set; restore or import/export configurations
- **File Encryption** — Password-based encryption and decryption of files and folders (PBKDF2 + Fernet/AES)
- **Command Scheduling** — Schedule commands to run at specific times via the system cron daemon
- **Single-Instance Enforcement** — Only one running instance allowed; stale locks are cleared automatically
- **JSON Editor** — Open `commands.json` directly from the tray for manual edits
- **Multi-platform** — Linux (binary, .deb, AppImage) and Windows (.exe)

---

## Installation

### 1. Clone the repository

```sh
git clone https://github.com/DewaldOosthuizen/py-tray-command-launcher.git
cd py-tray-command-launcher
```

### 2. Install system dependencies

```sh
sudo bash scripts/install_packages.sh
```

### 3. Create and activate a virtual environment

```sh
python3 -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows
```

### 4. Install Python dependencies

```sh
pip install -r requirements.txt
```

---

## Configuration

Commands are defined in `commands.json` inside your user config directory (`~/.config/py-tray-command-launcher/` on Linux). A working copy is created automatically on first launch from the bundled `config/commands.json`.

Quick example:

```json
{
  "System": {
    "icon": "icons/system.jpeg",
    "Disk Usage": {
      "command": "df -h",
      "showOutput": true,
      "confirm": false
    },
    "Reboot": {
      "command": "pkexec reboot",
      "showOutput": false,
      "confirm": true
    },
    "Kill Port": {
      "command": "pkexec fuser -k {promptInput}/tcp",
      "confirm": true,
      "prompt": "Enter port number:"
    }
  }
}
```

See [docs/configuration.md](docs/configuration.md) for the full field reference and examples.

---

## Running the App

```sh
source venv/bin/activate
python3 src/main.py
```

**Background:**

```sh
nohup python3 src/main.py &
```

---

## Packaging

Pre-built packages can be built with the scripts in `scripts/`:

```sh
./scripts/build-all.sh          # all formats
./scripts/build-linux.sh        # Linux executable
./scripts/build-deb.sh          # Debian package
./scripts/build-appimage.sh     # AppImage
scripts\build-windows.bat       # Windows .exe (run on Windows)
```

See [docs/packaging.md](docs/packaging.md) for prerequisites, output locations, and troubleshooting.

---

## Documentation

| Document | Description |
|---|---|
| [docs/configuration.md](docs/configuration.md) | Full `commands.json` and `settings.json` field reference |
| [docs/features.md](docs/features.md) | Detailed guide to all application features |
| [docs/architecture.md](docs/architecture.md) | Module structure, responsibilities, and data flow |
| [docs/packaging.md](docs/packaging.md) | Build instructions for all package formats |
| [docs/contributing.md](docs/contributing.md) | Development setup, code standards, and PR process |

---

## Screenshots

<img width="629" height="359" alt="Screenshot from 2026-01-13 20-21-56" src="https://github.com/user-attachments/assets/9ef2015e-7685-4826-919a-6bbe591b6472" />

---

## Contributing

Contributions are welcome! See [docs/contributing.md](docs/contributing.md) for setup instructions, code quality requirements, and documentation policy.

---

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.

