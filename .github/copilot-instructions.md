# py-tray-command-launcher

py-tray-command-launcher is a Python-based system tray application that allows users to execute custom commands and scripts directly from the system tray. Built with PyQt6, it provides a hierarchical menu system, command search, favorites, backup/restore functionality, and extensive customization options.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Code Exploration and Token Efficiency

- If `.codegraph/` exists in the project, use CodeGraph tools first for symbol lookup, context gathering, and call tracing.
- Prefer CodeGraph over manual grep/file-scanning to reduce token usage and speed up exploration.
- Use shell/file search as a fallback only when CodeGraph is unavailable or does not return needed results.

## Working Effectively

### Bootstrap, Build, and Test the Repository

**NEVER CANCEL any of these commands - all operations complete within reasonable timeframes:**

- Install system dependencies:
  ```bash
  sudo bash scripts/install_packages.sh
  ```
  **TIMING: 20-30 seconds. NEVER CANCEL - set timeout to 60+ seconds.**

- Create and activate Python virtual environment:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
  **TIMING: 3-5 seconds.**

- Install Python dependencies:
  ```bash
  pip install -r requirements.txt
  ```
  **TIMING: 4-6 seconds. NEVER CANCEL - set timeout to 120+ seconds.**

- Validate installation (imports and configuration):
  ```bash
  python3 -c "import sys; sys.path.append('src'); from core.tray_app import TrayApp; print('Import successful')"
  ```
  **TIMING: <1 second.**

### Running the Application

- **GUI Mode (requires display server):**
  ```bash
  source venv/bin/activate
  python3 src/main.py
  ```

- **Headless validation (for CI/testing):**
  ```bash
  source venv/bin/activate
  QT_QPA_PLATFORM=offscreen python3 src/main.py
  ```

- **Background execution:**
  ```bash
  source venv/bin/activate
  nohup python3 src/main.py &
  ```

### Code Quality and Validation

- Install development tools:
  ```bash
  source venv/bin/activate
  pip install pylint flake8 black
  ```

- Run linting (ALWAYS do this before committing):
  ```bash
  source venv/bin/activate
  flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics
  ```
  **TIMING: <1 second.**

- Format code:
  ```bash
  source venv/bin/activate
  black src/
  ```

- Check for syntax errors across all Python files:
  ```bash
  find src -name "*.py" -exec python3 -m py_compile {} \;
  ```

## Repository Structure

### Key Directories and Files
```
├── src/                         # Main source code
│   ├── main.py                  # Application entry point
│   ├── core/                    # Core services and app orchestration
│   │   ├── tray_app.py
│   │   ├── menu_builder.py
│   │   ├── services.py
│   │   ├── theme_manager.py
│   │   ├── config_manager.py
│   │   ├── logging_config.py
│   │   └── output_window.py
│   ├── modules/                 # Feature modules (commands, schedules, backup, etc.)
│   │   ├── command_executor.py
│   │   ├── command_search.py
│   │   ├── command_creator.py
│   │   ├── command_history.py
│   │   ├── favorites.py
│   │   ├── backup_restore.py
│   │   ├── import_export.py
│   │   ├── file_encryptor.py
│   │   ├── schedule_creator.py
│   │   └── schedule_viewer.py
│   ├── ui/                      # Modern UI widgets and dialogs
│   │   ├── command_palette.py
│   │   ├── quick_launch_bar.py
│   │   ├── command_manager.py
│   │   ├── settings_dialog.py
│   │   └── output_window.py
│   └── utils/                   # Utility functions and helpers
├── config/                      # Command configuration files
├── resources/                   # Icons and themes
├── tests/                       # Unit/integration tests
├── docs/                        # Project documentation
├── openspec/                    # Change proposals/specs/tasks
├── scripts/                     # Build and setup scripts
├── requirements.txt             # Runtime dependencies
└── requirements-build.txt       # Packaging/build dependencies
```

### Important File Locations
- **Main application:** `src/main.py`
- **Configuration:** `config/commands.json`
- **Icons:** `resources/icons/` (icon.png is the main tray icon)
- **Themes:** `resources/themes/` (`light.qss` and `dark.qss`)
- **UI layer:** `src/ui/`
- **Tests:** `tests/`
- **OpenSpec artifacts:** `openspec/changes/` and `openspec/specs/`
- **System setup:** `scripts/install_packages.sh`

## Validation

### Manual Testing Requirements
Since this is a GUI application, you MUST perform manual validation after making changes:

1. **Configuration validation:**

  ```bash
  source venv/bin/activate
  python3 -c "
  import sys; sys.path.append('src')
  from core.config_manager import config_manager
  commands = config_manager.get_commands()
  print('Categories:', list(commands.keys()))
  "
  ```

2. **Application startup validation:**
  ```bash
  source venv/bin/activate
  QT_QPA_PLATFORM=offscreen timeout 5 python3 src/main.py
  ```
  Should start without errors and show config loading messages.

3. **Code quality validation:**
  - ALWAYS run `flake8 src/` before committing
  - Check that all Python files compile: `find src -name "*.py" -exec python3 -m py_compile {} \;`

### GUI Testing Limitations
- You CANNOT interact with the GUI in headless environments
- Use `QT_QPA_PLATFORM=offscreen` for validation testing
- GUI functionality requires a display server or VNC for full testing

## Dependencies and System Requirements

### System Dependencies (automatically installed by scripts/install_packages.sh)
- `python3` - Python 3.x runtime
- `python3-pip` - Python package manager
- `libxcb-xinerama0` - X11 extension library
- `libxcb-cursor0` - X11 cursor library
- `policykit-1` - Policy management
- `libegl1` - EGL library (may be needed for Qt)

### Python Dependencies (installed by pip)
- `PyQt6` - GUI framework (only dependency in requirements.txt)

### Development Dependencies (optional)
- `pylint` - Code analysis
- `flake8` - Style checking
- `black` - Code formatting

## Common Tasks

### Working with Configuration
- Main config file: `config/commands.json`
- JSON structure defines command categories and individual commands
- Each command can specify: `command`, `showOutput`, `confirm`, `icon`
- Use `{promptInput}` placeholder for user input prompts

### Adding New Commands
- Edit `config/commands.json` directly, OR
- Use the built-in command creator (GUI feature)
- Always validate JSON syntax after manual edits

### Debugging Command Execution
- Check `src/modules/command_executor.py` for execution logic
- Commands run via `subprocess.Popen()` or `QProcess`
- Output handling controlled by `showOutput` flag

### Testing Changes
```bash
# Quick validation workflow
source venv/bin/activate
python3 -m py_compile src/main.py
flake8 src/ --count --select=E9,F63,F7,F82
QT_QPA_PLATFORM=offscreen timeout 3 python3 src/main.py
```

## Known Limitations

### GUI Requirements
- Application requires a display server for full GUI functionality
- System tray integration needs a compatible desktop environment
- Headless testing is limited to import and configuration validation

### Platform Support
- Primary target: Linux desktop environments
- Windows support available via `win-commands.json`
- Requires Qt platform plugins for proper display

### Testing Infrastructure
- Unit tests exist under `tests/` (currently 6 Python test files)
- Manual validation is still required for GUI behavior
- Headless startup checks remain important for CI and local verification

## Timing Expectations

**NEVER CANCEL these operations - they complete within expected timeframes:**
- System package installation: 20-30 seconds
- Virtual environment creation: 3-5 seconds
- Python dependency installation: 4-6 seconds
- Application import validation: <1 second
- Linting operations: <1 second

Set timeouts generously (60+ seconds for installs, 30+ seconds for tests) to avoid premature cancellation.

## Frequent Commands Output

### Repository Root Contents
```bash
ls -la
```
```
.git/
.gitignore
LICENSE
AppDir/
README.md
build/
config/
docs/
openspec/
packaging/
py-tray-command-launcher.spec
requirements-build.txt
requirements.txt
resources/
scripts/
src/
tests/
tools/
```

### Source Code Statistics
- 27 Python files in `src/`
- 6 Python test files in `tests/`
- Main application layers: core, modules, ui, and utils

### Requirements File
```bash
cat requirements.txt
```
```
PyQt6
```

### Configuration Categories
Available command categories in `config/commands.json`:
- System (terminal, updates, system info)
- Media (music, video applications)
- Studies (educational tools)
- Utilities (file management, etc.)
- Development (coding tools)
- Networking (network utilities)
- Favorites (user-defined favorites)