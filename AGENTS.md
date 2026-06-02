# DewaldOosthuizen/py-tray-command-launcher

A Python/PyQt6 system tray application for launching custom commands and scripts from a
hierarchical menu. Supports file encryption, command scheduling, backup/restore, favorites,
fuzzy command search, a command palette, a quick-launch bar, and packaging for Linux and Windows.

This file instructs AI agents (Hermes, GitHub Copilot, Codex, etc.) on how to orient themselves
in this repository efficiently.

<!-- graph-tools-start -->

## Code Exploration

### codegraph

.codegraph/ is present. Use it FIRST for any symbol lookup, call tracing, or targeted context
gathering before opening source files.

```bash
codegraph context "<task description>" -p .   # focused file+symbol context
codegraph query "<ClassName or function>" -p . # where is X defined / used
codegraph affected <changed-files> -p .        # which tests are affected
codegraph sync .                               # after any code change
```

Decision order for code tasks:
  1. codegraph context     — which symbols matter?
  2. graphify query        — which files are involved?
  3. understand-anything   — where in the architecture does this live?
  4. Read raw source       — only the 1-2 files that actually matter.

### understand-anything

.understand-anything/knowledge-graph.json is present.
Use it for layered architecture questions (layers, communities, entry points).

```bash
# Launch the interactive dashboard
cd ~/.understand-anything-plugin/packages/dashboard
GRAPH_DIR=$(pwd) npx vite --host 127.0.0.1
```

For prose questions load the skill:
```
skill: understand-chat
```

### graphify

graphify-out/ not yet generated for this repo.

<!-- graph-tools-end -->

---

## Project Structure

- src/           Application source (main entry point: src/main.py)
- config/        Bundled default commands.json (copied to ~/.config/py-tray-command-launcher/ on first launch)
- docs/          Architecture, configuration, features, packaging, and ADD records
- scripts/       Build and install scripts (build-linux.sh, build-deb.sh, build-appimage.sh, etc.)
- tests/         50 tests; run with pytest
- pyproject.toml Single source of truth for all dependencies (PyQt6 >= 6.11.0)

## Key Features

- Hierarchical command menu with categories and icons
- Fuzzy command search (rapidfuzz) and command palette (Ctrl+Shift+Space)
- Quick-launch bar — floating draggable toolbar of pinned commands
- Settings UI — theme, hotkey, history limit, output font, log level (no JSON editing)
- Dark/Light theming (Catppuccin Mocha / Latte) with live preview
- Rich tabbed output window with ANSI colour support
- Command Manager — full CRUD GUI; changes take effect without restart
- File encryption — PBKDF2-HMAC-SHA256, 600,000 iterations (OWASP 2023) + Fernet/AES
- Command scheduling via user crontab
- Backup/restore and import/export of configurations
- Single-instance enforcement with stale-lock cleanup
- Multi-platform: Linux (binary, .deb, AppImage) and Windows (.exe)

## Development Setup

```bash
# 1. Install system dependencies
sudo bash scripts/install_packages.sh

# 2. Create and activate venv
python3 -m venv venv
source venv/bin/activate

# 3. Install with dev tooling
pip install -e ".[dev]"

# 4. Run
python3 src/main.py

# 5. Test
pytest
```

Dependency rule: add or change deps only in pyproject.toml. requirements.txt is a convenience
shim (-e ".[dev]") and must never declare standalone version pins.

## Architecture & Docs

| Document | Description |
|---|---|
| docs/add/README.md | Architecture Design Decisions (ADD) records |
| docs/configuration.md | Full commands.json and settings.json field reference |
| docs/features.md | Detailed guide to all application features |
| docs/architecture.md | Module structure, responsibilities, and data flow |
| docs/packaging.md | Build instructions for all package formats |
| docs/contributing.md | Development setup, code standards, and PR process |

## Packaging & Releases

```bash
./scripts/build-all.sh          # all formats
./scripts/build-linux.sh        # Linux executable
./scripts/build-deb.sh          # Debian package
./scripts/build-appimage.sh     # AppImage
scripts\build-windows.bat       # Windows .exe (run on Windows)
```

Releases are automated via GitHub Actions. Push a version tag to trigger the build:

```bash
git tag v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0
```

The workflow builds the AppImage and attaches it to a GitHub Release automatically.

## File Encryption — Breaking Change (v2+)

The .salt file written alongside encrypted files is 20 bytes:
4-byte big-endian uint32 iteration count + 16-byte random salt.

Previous versions wrote a 16-byte raw salt only. Old .salt files are handled transparently via
legacy fallback (iteration count assumed 100,000). Do not copy .salt files between machines
running different versions without verifying the file length (16 = legacy, 20 = current).

Migration: decrypt with the current version (legacy fallback applies), then re-encrypt — the
new .salt file is written in the 20-byte format at 600,000 iterations.

## Notes for AI Agents

- PyQt6 >= 6.11.0 is the GUI framework. The system may have PyQt5 installed — do not confuse them.
- Test files must stub PyQt6 at module level via sys.modules injection before importing src modules
  when the host only has PyQt5 (e.g. sys.modules["PyQt6"] = MagicMock()).
- Dependabot manages dependency updates (weekly, Monday). A pip-audit step runs on every push/PR.
- openspec is used for spec-driven change workflow in this repo.
- All architectural decisions are recorded as ADDs in docs/add/.
