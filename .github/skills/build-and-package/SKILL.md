---
name: build-and-package
description: How to build and package py-tray-command-launcher as a standalone Linux AppImage using PyInstaller and appimagetool. Covers the full build pipeline, packaging structure, and troubleshooting.
license: MIT
metadata:
  author: project
  version: "1.0"
---

# Build and Package

This project builds to a standalone Linux AppImage using PyInstaller + appimagetool.

---

## Prerequisites

```bash
# Install build dependencies
pip install -r requirements-build.txt

# Install system packaging tools
sudo bash scripts/install_packages.sh
```

`requirements-build.txt` includes PyInstaller and any packaging utilities.

---

## Build the AppImage

```bash
# Full build pipeline
bash scripts/build.sh
```

This script:
1. Runs PyInstaller using `py-tray-command-launcher.spec`
2. Assembles the `AppDir/` layout
3. Calls `appimagetool` to produce the final `.AppImage`

Output: `dist/py-tray-command-launcher-x86_64.AppImage` (or similar)

---

## PyInstaller spec file

`py-tray-command-launcher.spec` defines:
- Entry point: `src/main.py`
- Bundled data: `config/`, `resources/`
- Hidden imports for PyQt6 plugins

If you add new resource directories, update the `datas` list in the spec:
```python
datas=[
    ('config', 'config'),
    ('resources', 'resources'),
    ('your-new-dir', 'your-new-dir'),   # add this line
],
```

---

## AppDir layout

```
AppDir/
├── AppRun                    # launcher script
├── py-tray-command-launcher.desktop
├── icon.png
└── usr/
    └── bin/
        └── py-tray-command-launcher   # PyInstaller bundle
```

---

## Validate the build

```bash
# Test the built binary directly
./dist/py-tray-command-launcher-x86_64.AppImage

# Headless smoke test
QT_QPA_PLATFORM=offscreen timeout 5 ./dist/py-tray-command-launcher-x86_64.AppImage
```

---

## Troubleshooting

### Missing Qt platform plugins at runtime
The AppImage may need `libxcb-*` on the host system even when bundled:
```bash
sudo apt install libxcb-xinerama0 libxcb-cursor0
```

### PyInstaller misses a hidden import
Add it to the spec:
```python
hiddenimports=['PyQt6.QtPrintSupport', 'your.missing.module'],
```

### Resources not found at runtime
Check that the `datas` list in the spec includes all resource directories.
At runtime, use:
```python
import sys, os
base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
resource_path = os.path.join(base, 'resources', 'icons', 'icon.png')
```

---

## Clean build

```bash
rm -rf build/ dist/
bash scripts/build.sh
```
