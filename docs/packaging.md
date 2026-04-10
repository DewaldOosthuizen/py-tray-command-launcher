# Packaging and Building

How to build py-tray-command-launcher into distributable packages.

---

## Prerequisites

### All Linux builds

- Python 3.8 or higher (`python3 --version`)
- `pip` (Python package manager)
- System libraries — install with:

  ```bash
  sudo bash scripts/install_packages.sh
  ```

  This installs: `libxcb-xinerama0`, `libxcb-cursor0`, `policykit-1`, `libegl1`.

### Windows builds

Requires a Windows machine with Python 3.8+. All dependencies are handled by the build script.

---

## Supported Package Formats

| Format | Script | Output | Notes |
|---|---|---|---|
| Linux executable | `scripts/build-linux.sh` | `dist/py-tray-command-launcher` | ~63 MB, no install needed |
| Debian package (.deb) | `scripts/build-deb.sh` | `dist/py-tray-command-launcher_*.deb` | Installs to `/usr/bin/`, includes desktop entry |
| AppImage | `scripts/build-appimage.sh` | `dist/py-tray-command-launcher-x86_64.AppImage` | ~63 MB, portable, works on most distros |
| Windows executable | `scripts/build-windows.bat` | `dist/py-tray-command-launcher.exe` | Run on a Windows machine |

All scripts must be run from the **project root**:

```bash
cd /path/to/py-tray-command-launcher
./scripts/build-linux.sh
```

---

## Build All Linux Formats

```bash
./scripts/build-all.sh
```

Optional flags:

```bash
./scripts/build-all.sh --linux-only
./scripts/build-all.sh --deb-only
./scripts/build-all.sh --appimage-only
./scripts/build-all.sh --clean
./scripts/build-all.sh --help
```

---

## Build Steps

### Linux executable

```bash
./scripts/build-linux.sh
```

1. Creates/activates a `venv/` virtual environment.
2. Installs `requirements.txt` and `requirements-build.txt` (includes PyInstaller).
3. Runs `pyinstaller py-tray-command-launcher.spec`.
4. Runs a headless smoke test.
5. Output: `dist/py-tray-command-launcher`

### Debian package

```bash
./scripts/build-deb.sh
```

Builds the Linux executable first, then creates a `.deb` using `dpkg-deb`. Desktop integration file is sourced from `packaging/py-tray-command-launcher.desktop`. Output: `dist/py-tray-command-launcher_*.deb`.

Install the `.deb`:

```bash
sudo dpkg -i dist/py-tray-command-launcher_*.deb
```

### AppImage

```bash
./scripts/build-appimage.sh
```

1. Downloads `appimagetool` to `tools/` if not already present.
2. Builds the Linux executable.
3. Assembles `AppDir/` with the binary, desktop file, and icon.
4. Runs `appimagetool` to produce the AppImage.
5. Output: `dist/py-tray-command-launcher-x86_64.AppImage`

Make executable and run:

```bash
chmod +x dist/py-tray-command-launcher-x86_64.AppImage
./dist/py-tray-command-launcher-x86_64.AppImage
```

**Config path for AppImage:** `~/.config/py-tray-command-launcher/` (or `$XDG_CONFIG_HOME/py-tray-command-launcher/`).

### Windows executable

On a Windows machine:

```bat
scripts\build-windows.bat
```

Output: `dist\py-tray-command-launcher.exe`

---

## Build Artifacts

```
project_root/
├── dist/                                          # Final output
│   ├── py-tray-command-launcher                   # Linux executable
│   ├── py-tray-command-launcher-x86_64.AppImage
│   ├── py-tray-command-launcher_*.deb
│   └── py-tray-command-launcher.exe
├── build/                                         # PyInstaller intermediates
├── AppDir/                                        # AppImage staging (auto-created)
└── tools/                                         # appimagetool download cache
```

---

## Requirements Files

| File | Purpose |
|---|---|
| `requirements.txt` | Runtime dependencies: `PyQt6`, `cryptography` |
| `requirements-build.txt` | Build-time: `PyInstaller`, `setuptools`, `wheel` |

---

## Troubleshooting

### Permission denied when cleaning build artifacts

**Symptom:** `rm: cannot remove 'build/...' Permission denied` or `dist/py-tray-command-launcher: Permission denied`

**Cause:** A previous build was run with `sudo`, leaving `build/` and `dist/` owned by root.

**Fix:**

```bash
sudo chown -R $USER:$USER build/ dist/
```

Then re-run the build script. The build scripts include an automatic fallback: if `rm -rf` fails they will retry with `sudo rm -rf` and prompt for your password once.

### AppImage not produced / appimagetool fails

Verify that `tools/appimagetool` exists and is executable:

```bash
ls -lh tools/appimagetool
chmod +x tools/appimagetool
```

If the download was corrupted, delete `tools/appimagetool` and let the script re-download it.

### PyInstaller missing modules at runtime

Add the missing import to the `hiddenimports` list in `py-tray-command-launcher.spec` and rebuild.

### Headless smoke test fails with display errors

The build scripts run a short `QT_QPA_PLATFORM=offscreen` smoke test. This is expected to exit with a timeout message. A genuine failure prints a Python traceback — check for missing system libraries with:

```bash
ldd dist/py-tray-command-launcher | grep "not found"
```
