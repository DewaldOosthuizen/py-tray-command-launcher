---
name: debug-tray-app
description: Debug and troubleshoot the py-tray-command-launcher application — startup failures, tray icon not appearing, commands not executing, config issues, and single-instance lock problems.
license: MIT
metadata:
  author: project
  version: "1.0"
---

# Debugging py-tray-command-launcher

---

## Application won't start

### Check 1: Stale single-instance lock

```bash
# Force release the lock
source venv/bin/activate
python3 src/main.py --force-unlock
```

If that clears it, the previous process crashed without cleanup.

### Check 2: Config file is invalid JSON

```bash
python3 -c "import json; json.load(open('config/commands.json')); print('valid')"
# or for user config:
python3 -c "import json; json.load(open(os.path.expanduser('~/.config/py-tray-launcher/commands.json'))); print('valid')"
```

### Check 3: PyQt6 / Qt platform issues

```bash
# Test with offscreen platform
QT_QPA_PLATFORM=offscreen timeout 5 python3 src/main.py
```

Error `could not connect to display` means no display server — use offscreen or
connect via VNC/X forwarding.

Error `qt.qpa.plugin: Could not load platform plugin` — missing Qt platform libs:
```bash
sudo bash scripts/install_packages.sh
```

### Check 4: Import errors

```bash
source venv/bin/activate
python3 -c "import sys; sys.path.append('src'); from core.tray_app import TrayApp"
```

---

## Tray icon not visible

- Some desktop environments hide tray icons by default (GNOME requires an extension
  like AppIndicator or KStatusNotifierItem support)
- Try KDE Plasma, XFCE, or LXDE for full tray support
- On GNOME: install `gnome-shell-extension-appindicator`

---

## Command not executing

### Check execution mode

In `config/commands.json`:
- `"showOutput": true` → runs via `subprocess.Popen`, output window appears
- `"showOutput": false` → runs via `QProcess`, silent

If the command seems to do nothing with `showOutput: false`, try setting it to
`true` temporarily to see stderr.

### Test command manually

```bash
# Copy the command string and run it directly in a terminal
bash -c "your command here"
```

### QProcess silent failure

Ensure `QProcess.start()` is called before the method returns — this was a known
bug that has been fixed. If you see commands silently dropped, check
`src/modules/command_executor.py` to confirm `proc.start()` is called.

---

## Config changes not reflected in menu

The menu is built at startup. After editing `commands.json`:
1. Right-click the tray icon
2. Select "Reload Config" (if available), OR
3. Quit and restart the app

---

## Favorites not saving

Favorites are stored as dot-path keys: `"group.label"`. If a command has a dot in
its group or label name, encoding may collide. Check:

```python
from modules.favorites import _build_command_path
print(_build_command_path("My Group", "My Command"))
# should output: "My Group.My Command"
```

Favorites file location: `~/.config/py-tray-launcher/favorites.json`

---

## Icon not loading

Icons are resolved in this order:
1. `resources/icons/<name>.png` (bundled)
2. XDG icon theme (`/usr/share/icons/...`)
3. URL download → cached at `/tmp/py-tray-launcher-icons/<md5>.<ext>`

If a URL icon fails silently, check `/tmp/py-tray-launcher-icons/` for the cached
file and verify the URL is reachable.

TTL: when `cache_ttl_seconds=0`, cached icons never expire.

---

## Tests failing

### Most common cause: PyQt6 not found

Ensure every test file has the PyQt6 stub at the top:
```python
from unittest.mock import MagicMock
import sys
for mod in ["PyQt6", "PyQt6.QtWidgets", "PyQt6.QtCore", "PyQt6.QtGui"]:
    sys.modules[mod] = MagicMock()
```

### Patching resource_roots

Patch on the CLASS, not the instance:
```python
with patch.object(IconResolver, "resource_roots", return_value=[tmp_path]):
```

---

## Logging

Application logs are written to:
```
~/.local/share/py-tray-launcher/app.log
```

Tail it while running:
```bash
tail -f ~/.local/share/py-tray-launcher/app.log
```

For verbose output during debugging:
```bash
source venv/bin/activate
PYTHONUNBUFFERED=1 python3 src/main.py 2>&1 | tee /tmp/tray-debug.log
```
