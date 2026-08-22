# Features

A detailed guide to all user-facing features of py-tray-command-launcher.

---

## Hierarchical Command Menu

Commands are organised into categories and displayed as submenus in the system tray. Each category can have a custom icon and contain any number of named command entries.

- Categories appear as submenus when you right-click (or left-click, depending on desktop environment) the tray icon.
- Commands can be nested one level deep (category → command).
- Category and command icons are loaded from the paths specified in `commands.json`.

---

## Command Execution

### Basic execution

Click any command in the menu to run it. The command is executed via the system shell.

### Output display

Set `"showOutput": true` on a command to capture its stdout/stderr and display results in a scrollable output window after execution. Useful for diagnostic commands such as `df -h` or `uname -a`.

### Confirmation dialogs

Set `"confirm": true` on a command to require the user to confirm before execution. Recommended for destructive or irreversible commands such as reboot or shutdown.

### User input prompts

Use `{promptInput}` anywhere in a command string to request user input at runtime. An input dialog appears first; whatever the user types replaces `{promptInput}` before the command runs.

```json
"SSH to Host": {
  "command": "ssh user@{promptInput}",
  "prompt": "Enter hostname:"
}
```

---

## Command Search

Open the command search dialog from the tray menu to find any command by name across all categories. Select a result and press Enter (or double-click) to execute immediately.

- Fuzzy-style filtering: results narrow as you type.
- Works across all categories and nested submenus.
- Accessible from the tray menu without scrolling through long category lists.

---

## Favorites

Mark any command as a favorite to pin it to the Favorites section at the top of the tray menu for quick access.

- Access "Add to Favorites" from the command's context menu or from the Command Creator.
- Favorites persist between sessions in `favorites.json`.
- Remove a favorite from the Favorites section or from the command's context menu.

---

## Recent Commands

The **Recent Commands** submenu shows the last commands you ran, ordered by most recent. Click any entry to re-run it immediately.

- History depth is configurable.
- History persists between sessions in `history.json`.

---

## Command Creator

Create new commands through a graphical dialog without editing JSON directly.

1. Open **Create Command** from the tray menu.
2. Choose or create a category.
3. Fill in the command name, shell command, icon path, and toggle options (showOutput, confirm).
4. Click **Save** — the command appears in the tray immediately.

---

## Backup and Restore

### Create a backup

Select **Backup Commands** from the tray menu to save a timestamped copy of `commands.json` to the `backups/` subdirectory inside your config directory.

### Restore from backup

Select **Restore Commands** to choose a previous backup and replace the current configuration.

### Import / Export

- **Export**: Save the current command set (or a selected category) to a `.json` file anywhere on disk—useful for sharing configurations.
- **Import**: Load a `.json` file into the current command set, merging or replacing categories as needed.

---

## File Encryption

Encrypt and decrypt files or entire folders using a password-derived key (PBKDF2 + Fernet/AES).

### How it works

1. Open **File Encryption** from the tray menu.
2. Select a file or folder to encrypt.
3. Enter (and confirm) a password.
4. The original file is replaced by a `.enc` encrypted version. A `.salt` file is stored alongside it to enable decryption.

### Decryption

1. Open **File Encryption** and switch to **Decrypt**.
2. Select the `.enc` file and enter the same password.
3. The original file is restored and the `.enc` file is removed.

Encryption runs in a background thread so the UI stays responsive on large files or directories. Progress is shown via a progress bar.

### Salt Format and Migration

Each encrypted file is accompanied by a `.salt` file that stores the parameters needed for decryption.

**Current format (20 bytes):** a 4-byte big-endian `uint32` holding the PBKDF2 iteration count (currently 600 000) followed by 16 bytes of random salt.

**Legacy format (16 bytes):** files encrypted before the iteration-count upgrade contain only the 16-byte salt. The application automatically recognises this format and uses the original 100 000 iteration count for decryption.

**In-app upgrade path:** after successfully decrypting a legacy file, the application offers to re-encrypt it using the current standard (600 000 iterations). Accepting the prompt opens a password dialog; the re-encryption is performed atomically — new encrypted and salt files are written to temporary files first, then renamed into place, so the original plaintext is never removed unless both writes succeed.

---

## Command Scheduling

Schedule any command to run automatically at a specific time on selected days of the week using the system cron daemon.

### Create a schedule

1. Open **Schedule Command** from the tray menu.
2. Select a command from the dropdown (all categories are listed).
3. Choose the time (HH:MM) and tick the days of the week.
4. Click **Schedule** — a cron entry is added for your user.

### View / manage schedules

Open **View Schedules** to see a list of all scheduled commands. Remove a schedule from this dialog to delete the corresponding cron entry.

---

## Single-Instance Enforcement

Only one instance of the application can run at a time.

- On launch, the app checks for an existing instance using a shared memory key.
- If another instance is detected and its PID is still alive, a dialog informs the user and the new instance exits.
- If a stale lock is detected (the recorded PID is no longer running), the user may be prompted to confirm **Force Unlock** before the lock is cleared and the new instance can start. You can also use `--force-unlock` to clear the stale lock.

---

## JSON Editor

Open the raw `commands.json` in your system's default text editor directly from the tray menu. After saving the file, use **Restart App** to reload the configuration.

---

## App Restart

Select **Restart App** from the tray menu to reload the application process. Use this after manually editing `commands.json` or `settings.json`.

---

## App Launcher

The App Launcher palette lists all installed applications discovered from XDG `.desktop` files on Linux, or from Windows Start Menu `.lnk` shortcuts on Windows. It is powered by the `AppDiscovery` module (`src/modules/app_discovery.py`).

### Default search directories (Linux)

On Linux, AppDiscovery scans the following directories for `.desktop` files by default:

1. `~/.local/share/applications` — derived from `$XDG_DATA_HOME` (default: `~/.local/share`)
2. `/usr/local/share/applications` — first entry from `$XDG_DATA_DIRS` (default: `/usr/local/share:/usr/share`)
3. `/usr/share/applications` — second entry from `$XDG_DATA_DIRS`

These defaults match the XDG Base Directory Specification. The search path is constructed at `src/modules/app_discovery.py` lines 130-136 by reading `$XDG_DATA_HOME` and `$XDG_DATA_DIRS`.

### Customising the search path

Users on non-standard distributions (NixOS, Guix, Flatpak-heavy setups) or those who install applications to custom locations can extend the search path by setting `$XDG_DATA_DIRS` before launching the application:

```bash
XDG_DATA_DIRS=/usr/local/share:/usr/share:/home/user/my-apps python3 src/main.py
```

The variable is a colon-separated list of base directories; each is suffixed with `/applications` and scanned for `.desktop` files. `$XDG_DATA_HOME` can also be set to override the per-user applications directory.

### Excluded entries

`.desktop` entries with the following fields are intentionally skipped and do not appear in the palette:

- `NoDisplay=true` — the application exists but the desktop entry author indicates it should not be shown in menus (checked at `src/modules/app_discovery.py` lines 219-220)
- `Hidden=true` — the entry has been marked as hidden/disabled (checked at lines 221-222)
- `Type` not equal to `Application` — launchers, links, and other non-application entry types are skipped (line 217)

### Diagnosing missing applications

If an installed application does not appear in the App Launcher palette, use the following steps to diagnose:

1. **Increase the log level** to DEBUG by either:
   - Setting `"logging.level": "DEBUG"` in `settings.json` (`docs/configuration.md`), or
   - Using the environment variable override: `PY_TRAY_LOG_LEVEL=DEBUG python3 src/main.py`

2. **Check the application load summary** — look for a log line like:
   ```
   AppDiscovery (Linux): loaded N applications
   ```
   (logged at `src/modules/app_discovery.py` line 152). This confirms how many applications were found in total.

3. **Check for parsing warnings** — malformed `.desktop` files that fail to parse produce warnings like:
   ```
   Skipping malformed .desktop file /path/to/bad.desktop: <error>
   ```
   (logged at line 201). These files are silently skipped.

4. **Verify the file is in a scanned directory** — confirm the `.desktop` file lives under one of the directories listed above (or under a custom `$XDG_DATA_DIRS` path you have configured).

5. **Check for exclusion flags** — open the `.desktop` file and confirm it does not contain `NoDisplay=true` or `Hidden=true`, and that `Type=Application` is present.
