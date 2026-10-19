# py-tray-command-launcher

[![Release](https://github.com/DewaldOosthuizen/py-tray-command-launcher/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/DewaldOosthuizen/py-tray-command-launcher/actions/workflows/release.yml?query=branch%3Amain)

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/paypalme/DewaldOosthuizen1)

A Python system tray application for launching custom commands and scripts from a hierarchical menu. Supports file encryption, command scheduling, backup/restore, favorites, command search, and packaging for Linux and Windows.

---

## Documentation

All project documentation lives in [docs/](docs/index.md).

| Document | Description |
|---|---|
| [Features](docs/features.md) | Detailed guide to all application features |
| [Configuration](docs/configuration.md) | Full `commands.json` and `settings.json` field reference |
| [Installation & Usage](docs/contributing.md) | Development setup and running the app |
| [Architecture](docs/architecture.md) | Module structure and data flow |
| [Packaging](docs/packaging.md) | Build instructions for all package formats |
| [AI Agent Guide](docs/ai-agent-guide.md) | Code exploration and design decisions |
| [Architecture Design Decisions](docs/add/README.md) | ADD records |

---

## Quick Start

```bash
git clone https://github.com/DewaldOosthuizen/py-tray-command-launcher.git
cd py-tray-command-launcher
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
python3 src/main.py
```

---

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
