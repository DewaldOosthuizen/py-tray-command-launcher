# Configuration Reference

This document covers all configuration files used by py-tray-command-launcher.

## Config Directory Location

The application stores user configuration in an OS-appropriate directory:

| Environment | Config directory |
|---|---|
| Linux / source run | `~/.config/py-tray-command-launcher/` |
| Linux / AppImage | `~/.config/py-tray-command-launcher/` (or `$XDG_CONFIG_HOME/py-tray-command-launcher/`) |
| Linux / .deb install | `~/.config/py-tray-command-launcher/` |
| Windows | `%APPDATA%\py-tray-command-launcher\` |

When running from source the bundled `config/commands.json` is copied to the user config directory on first launch. All subsequent reads and writes use the user config directory.

## Configuration Files

| File | Purpose |
|---|---|
| `commands.json` | Command definitions and categories |
| `settings.json` | Application settings (log level, etc.) |
| `history.json` | Recently executed commands (auto-managed) |
| `favorites.json` | Favorite commands (auto-managed) |

---

## commands.json

Defines the command hierarchy shown in the tray menu.

### Top-level structure

```json
{
  "CategoryName": { ... },
  "AnotherCategory": { ... }
}
```

Each top-level key becomes a submenu in the tray.

### Category fields

| Field | Type | Required | Description |
|---|---|---|---|
| `icon` | string | No | Path to an image file used as the category icon. Relative paths resolve from the app's resource directory. |

Any other key inside a category object is treated as a **command entry**.

### Command entry fields

| Field | Type | Default | Description |
|---|---|---|---|
| `command` | string | **required** | The shell command to execute. Supports the `{promptInput}` placeholder. |
| `showOutput` | boolean | `false` | When `true`, command stdout/stderr is captured and displayed in a dedicated output window after execution. |
| `confirm` | boolean | `false` | When `true`, a confirmation dialog is shown before the command runs. Useful for destructive or long-running commands. |
| `icon` | string | `""` | Path to an image file used as this command's menu icon. Overrides the category icon for this entry. |
| `prompt` | string | `""` | Custom prompt label shown in the input dialog when `{promptInput}` is present in `command`. Defaults to a generic prompt if omitted. |

### {promptInput} placeholder

Use `{promptInput}` anywhere in the `command` string to insert user-supplied text at runtime. When the command is triggered, an input dialog appears first; the text entered replaces `{promptInput}` before execution.

```json
"Kill Process on Port": {
  "command": "pkexec fuser -k {promptInput}/tcp",
  "showOutput": false,
  "confirm": true,
  "prompt": "Enter the port number:"
}
```

### Complete example

```json
{
  "System": {
    "icon": "icons/system.jpeg",
    "Open Terminal": {
      "command": "terminator",
      "showOutput": false,
      "confirm": false
    },
    "Disk Usage": {
      "command": "df -h",
      "showOutput": true,
      "confirm": false
    },
    "System Update": {
      "command": "terminator --command 'bash -c \"sudo apt update && sudo apt upgrade -y; exec bash\"'",
      "showOutput": false,
      "confirm": true
    },
    "Reboot": {
      "command": "pkexec reboot",
      "showOutput": false,
      "confirm": true
    },
    "Kill Process on Port": {
      "command": "pkexec fuser -k {promptInput}/tcp",
      "showOutput": false,
      "confirm": true,
      "prompt": "Enter the port number:"
    }
  },
  "Development": {
    "icon": "icons/dev.png",
    "VS Code": {
      "command": "code .",
      "showOutput": false,
      "confirm": false
    },
    "Git Status": {
      "command": "git status",
      "showOutput": true,
      "confirm": false
    }
  },
  "Media": {
    "Youtube Music": {
      "command": "brave --app-id=cinhimbnkkaeohfgghhklpknlkffjgod",
      "icon": "icons/music.png",
      "showOutput": false,
      "confirm": false
    }
  }
}
```

---

## settings.json

 Controls application-level settings. This file is optional: if it is missing, the application uses built-in defaults, and `get_settings()` returns the built-in default settings (with defaults merged in), not an empty dict. The file is not automatically created on first launch.

### Supported fields

| Field | Type | Default | Valid values | Description |
|---|---|---|---|---|
| `logging.level` | string | `"INFO"` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` | Controls the verbosity of application log output to stderr. |

### Example

```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

### Environment variable override

 You can override the configured log level at runtime without editing the file:

```bash
PY_TRAY_LOG_LEVEL=DEBUG python3 src/main.py
```

The environment variable always takes precedence over the value in `settings.json`.

## Safe scheduling

Scheduled command payloads are validated by `ScheduleCreator.validate_command`
before being handed to the scheduler. Shell control operators
(`;`, `&`, `|`, `$`, backticks, `()`, `{}`, `<>`, `*`, `?`, `\`, `!`,
and newlines/CR) are rejected. The command payload is **not** shell-quoted,
so it runs as a normal argv command. Task names and comment markers are the
only scheduler-facing strings escaped with `shlex.quote`.


### Windows (schtasks)

On Windows, `ScheduleCreator` invokes `schtasks /create ... /sc weekly` to
register the command as a weekly task.

Command syntax (`_create_windows_task`):

```text
schtasks /create /tn "<TaskName>" /tr "<command>" /sc weekly /d <DAYS> /st HH:MM /f
```

Examples:

```text
schtasks /create /tn "PyTrayLauncher_Notepad" /tr "notepad.exe" /sc weekly /d MON,TUE,WED,THU,FRI /st 09:00 /f
schtasks /create /tn "PyTrayLauncher_Run_Script" /tr "python script.py" /sc weekly /d MON /st 18:30 /f
```

Day/time variations: `/d` accepts comma-separated day abbreviations (`MON`..`SUN`);
`/st` is 24-hour `HH:MM`. Only weekly schedules (`/sc weekly`) are created.

Placeholders and fields:

- `/tn` — task name derived from the command label (`PyTrayLauncher_<Label>`),
  spaces replaced with underscores; must pass `validate_command`.
- `/tr` — the command string exactly as stored in `commands.json` (must not
  contain rejected shell-control characters; not shell-quoted).
- `/sc weekly` — fixed schedule type.
- `/d` — comma-separated day abbreviations (`MON`..`SUN`).
- `/st` — start time in 24-hour `HH:MM`.
- `/f` — overwrite existing task with the same name.

Limitations:

- Commands cannot use shell operators (`;`, `&`, `|`, etc.); see `ScheduleCreator.validate_command`.
- `{promptInput}` is not expanded for scheduled entries; the command runs verbatim.
- Only weekly schedules are supported.
- Creating tasks may require appropriate privileges depending on system policy.
- Cross-reference: `src/modules/schedule_creator.py` (Linux/cron and Windows paths),
  `src/ui/schedule_dialog.py`, `docs/features.md`, and `config/commands.schema.json`.

