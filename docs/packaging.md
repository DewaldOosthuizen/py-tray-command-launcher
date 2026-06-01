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

## Automated Releases (CI/CD)

The project ships a GitHub Actions workflow (`.github/workflows/release.yml`) that
builds the AppImage automatically and publishes it as a GitHub Release asset whenever
a version tag is pushed.

### How it works

Trigger: push a tag that matches `v*.*.*` (semantic version, e.g. `v1.2.0`).

The workflow:
1. Checks out the repository.
2. Installs all required system and Python dependencies on an `ubuntu-latest` runner.
3. Builds the Linux executable with PyInstaller.
4. Downloads `appimagetool`, assembles `AppDir/`, and produces the AppImage.
5. Creates a GitHub Release named after the tag with auto-generated release notes.
6. Uploads `py-tray-command-launcher-<tag>-x86_64.AppImage` as a downloadable asset.

Pre-release detection: if the tag contains a hyphen (e.g. `v1.2.0-beta.1`) the release
is automatically marked as a pre-release. Clean tags (`v1.2.0`) are full releases.

### Publishing a release

```bash
# 1. Ensure main is up to date
git push origin main

# 2. Create and push the version tag
git tag v1.2.0 -m "Release v1.2.0"
git push origin v1.2.0
```

That is all. Go to the GitHub Actions tab to watch the build, and the Releases page
to download the finished AppImage.

### Version naming

The AppImage is named using the tag directly:

    py-tray-command-launcher-v1.2.0-x86_64.AppImage

The tag is the single source of truth for the release version. No manual edits to
`pyproject.toml` or any other file are required before tagging.

### Re-building a release

If you need to rebuild an existing release (e.g. after a bad tag), delete the release
on GitHub first, then force-push the tag:

```bash
git tag -f v1.2.0 -m "Re-release v1.2.0"
git push origin v1.2.0 --force
```

The workflow will not overwrite an existing release — the old one must be deleted first.

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
