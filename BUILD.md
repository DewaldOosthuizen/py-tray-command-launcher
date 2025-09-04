# Building and Packaging py-tray-command-launcher

This document explains how to build and package py-tray-command-launcher into different executable formats.

## Supported Package Formats

- **Linux Executable**: Standalone executable for Linux systems
- **Debian Package (.deb)**: For Debian-based Linux distributions
- **AppImage**: Universal Linux application format
- **Windows Executable (.exe)**: For Windows systems

## Prerequisites

### For Linux builds:
- Python 3.8 or higher
- pip (Python package manager)
- System packages (will be installed automatically by scripts)

### For Windows builds:
- Windows machine with Python 3.8 or higher
- All dependencies are handled by the build script

## Quick Start

### Build All Linux Formats

```bash
# Build all supported formats (Linux executable, DEB, AppImage)
./scripts/build-all.sh
```

### Build Individual Formats

```bash
# Linux executable only
./scripts/build-linux.sh

# Debian package only
./scripts/build-deb.sh

# AppImage only
./scripts/build-appimage.sh

# Windows executable (run on Windows)
scripts\build-windows.bat
```

## Build Scripts Overview

### `scripts/build-linux.sh`
Creates a standalone Linux executable using PyInstaller.
- Output: `dist/py-tray-command-launcher` (63MB)
- Self-contained with all dependencies
- No installation required

### `scripts/build-deb.sh`
Creates a Debian package for easy installation on Debian-based systems.
- Output: `dist/py-tray-command-launcher_*.deb`
- Includes desktop integration
- Installs to `/usr/bin/`

### `scripts/build-appimage.sh`
Creates an AppImage for universal Linux compatibility.
- Output: `dist/py-tray-command-launcher-x86_64.AppImage` (63MB)
- Portable application format
- Works on most Linux distributions

### `scripts/build-windows.bat`
Creates a Windows executable (requires Windows environment).
- Output: `dist/py-tray-command-launcher.exe`
- Self-contained Windows application
- No installation required

### `scripts/build-all.sh`
Coordinating script that builds all supported formats.

## Build Options

The main build script supports several options:

```bash
# Build specific formats
./scripts/build-all.sh --linux-only     # Linux executable only
./scripts/build-all.sh --deb-only       # Debian package only
./scripts/build-all.sh --appimage-only  # AppImage only

# Clean previous builds
./scripts/build-all.sh --clean

# Show help
./scripts/build-all.sh --help
```

## Requirements Files

- `requirements.txt`: Runtime dependencies (PyQt6, cryptography)
- `requirements-build.txt`: Build-time dependencies (PyInstaller, etc.)

## Build Configuration

### PyInstaller Specification
The build process uses `py-tray-command-launcher.spec` which includes:
- Application entry point (`src/main.py`)
- Resource files (`config/`, `resources/`)
- Hidden imports for proper packaging
- Platform-specific optimizations

### Debian Packaging
Debian package configuration is in `packaging/debian/`:
- `control`: Package metadata and dependencies
- `rules`: Build rules for the package
- `changelog`: Package version history
- `compat`: Compatibility level

## Output Files

After building, packages are placed in the `dist/` directory:

```
dist/
├── py-tray-command-launcher                 # Linux executable
├── py-tray-command-launcher-x86_64.AppImage # AppImage
├── py-tray-command-launcher_*.deb          # Debian package
└── py-tray-command-launcher.exe            # Windows executable (if built)
```

## Cross-Platform Notes

### Linux
- Builds work on most modern Linux distributions
- Requires X11 libraries for GUI support
- AppImage provides best compatibility across distributions

### Windows
- Must be built on a Windows machine
- Cross-compilation from Linux is not currently supported
- All dependencies are bundled in the executable

### Dependencies
The built executables include all necessary dependencies:
- Python runtime
- PyQt6 GUI framework
- Cryptography library
- All application modules

## Troubleshooting

### Common Issues

1. **Missing system packages**: Run the install script first
   ```bash
   sudo bash scripts/install_packages.sh
   ```

2. **Virtual environment issues**: Clean and rebuild
   ```bash
   rm -rf venv
   ./scripts/build-linux.sh
   ```

3. **AppImage FUSE errors**: AppImages require FUSE to run on some systems
   ```bash
   # Install FUSE (Ubuntu/Debian)
   sudo apt-get install fuse
   
   # Or extract and run without FUSE
   ./py-tray-command-launcher-x86_64.AppImage --appimage-extract
   ./squashfs-root/AppRun
   ```

### Build Logs
Build logs and warnings are saved in:
- `build/py-tray-command-launcher/warn-py-tray-command-launcher.txt`

## Distribution

### Installation Instructions

**Linux Executable:**
```bash
# Make executable and run
chmod +x py-tray-command-launcher
./py-tray-command-launcher
```

**Debian Package:**
```bash
# Install the package
sudo dpkg -i py-tray-command-launcher_*.deb

# Install dependencies if needed
sudo apt-get install -f

# Run from command line or applications menu
py-tray-command-launcher
```

**AppImage:**
```bash
# Make executable and run
chmod +x py-tray-command-launcher-x86_64.AppImage
./py-tray-command-launcher-x86_64.AppImage
```

**Windows Executable:**
- Double-click the .exe file to run
- No installation required
- May trigger antivirus warnings (false positive)

## Development

To modify the packaging configuration:
1. Edit `py-tray-command-launcher.spec` for PyInstaller settings
2. Update `packaging/debian/` files for Debian packaging
3. Modify build scripts in `scripts/` directory
4. Test builds with `./scripts/build-all.sh --clean`

## Size Optimization

Current package sizes (~63MB) include:
- Python runtime
- Qt6 libraries
- All dependencies

To reduce size:
- Remove unused Qt modules in the spec file
- Exclude unnecessary libraries
- Use UPX compression (Linux/Windows)