---
name: work-with-themes
description: How to add, modify, and apply QSS themes in py-tray-command-launcher. Covers QSS file structure, ThemeManager usage, widget-level overrides, and adding new themes.
license: MIT
metadata:
  author: project
  version: "1.0"
---

# Working with Themes

Themes are QSS (Qt Style Sheets) files stored in `resources/themes/`.
`ThemeManager` in `src/core/theme_manager.py` loads and applies them to the
`QApplication` instance.

---

## Theme files

```
resources/themes/
├── dark.qss    # Dark theme (default)
└── light.qss   # Light theme
```

Both are full application-level QSS stylesheets targeting Qt widget classes.

---

## How ThemeManager works

```python
# Applied at startup in TrayApp.__init__
services.theme_manager.apply_theme("dark")   # or "light"

# Get the currently active stylesheet (for dialogs)
sheet = services.theme_manager.current_stylesheet()
self.setStyleSheet(sheet)
```

---

## Adding a new theme

1. Create `resources/themes/<name>.qss`
2. Add the name to the theme selector in `src/ui/settings_dialog.py`
3. ThemeManager discovers themes by scanning `resources/themes/*.qss` — no code
   changes needed in ThemeManager itself

---

## QSS conventions for this project

- All QSS lives in theme files — avoid `widget.setStyleSheet("...")` inline calls
- Widget-level `setStyleSheet()` is acceptable only for dynamic/runtime state
  (e.g., highlighting a selected command)
- Use Qt widget class selectors, not object names where possible:
  ```css
  QMenu { background-color: #2b2b2b; }
  QMenu::item:selected { background-color: #4e9aff; }
  ```
- Colours should be defined as QSS variables where supported, or clearly commented

---

## Applying a theme to a new dialog

In any new `QDialog` subclass:
```python
class MyDialog(QDialog):
    def __init__(self, services: AppServices, parent=None):
        super().__init__(parent)
        self.setStyleSheet(services.theme_manager.current_stylesheet())
```

---

## Testing theme changes

No display server needed to validate QSS syntax:
```bash
# Validate QSS loads without error
QT_QPA_PLATFORM=offscreen python3 -c "
import sys
sys.path.append('src')
from core.theme_manager import ThemeManager
tm = ThemeManager()
tm.apply_theme('dark')
print('dark OK')
tm.apply_theme('light')
print('light OK')
"
```

For visual testing, run the full app:
```bash
source venv/bin/activate && python3 src/main.py
```

Then switch themes via the Settings dialog.
