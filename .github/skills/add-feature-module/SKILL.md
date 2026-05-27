---
name: add-feature-module
description: Step-by-step guide for adding a new feature module to py-tray-command-launcher. Covers module creation, AppServices wiring, menu integration, testing, and symbol index update.
license: MIT
metadata:
  author: project
  version: "1.0"
---

# Add a Feature Module

Use this skill when adding a new self-contained feature to the application
(e.g., a new command type, a new data manager, a new integration).

---

## Steps

### 1. Create the module file

```bash
touch src/modules/<feature>.py
```

Minimal scaffold:
```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.services import AppServices


class MyFeature:
    """Short description of what this module does."""

    def __init__(self, services: AppServices) -> None:
        self._services = services
        self._config = services.config_manager

    # Public methods here
```

### 2. Register in AppServices

Edit `src/core/services.py` — add a field to the `AppServices` dataclass:

```python
@dataclass
class AppServices:
    # existing fields ...
    my_feature: MyFeature
```

Then instantiate it in the factory method / `TrayApp.__init__` where services
are built.

### 3. Wire into TrayApp or MenuBuilder (if it needs a menu entry)

In `src/core/menu_builder.py`:
```python
action = QAction("My Feature", self._tray)
action.triggered.connect(self._services.my_feature.open)
menu.addAction(action)
```

### 4. Write tests

```bash
touch tests/test_<feature>.py
```

Always use the PyQt6 stub pattern at the top of the file:
```python
from unittest.mock import MagicMock, patch
import sys

# Stub PyQt6 before importing any src modules
for mod in ["PyQt6", "PyQt6.QtWidgets", "PyQt6.QtCore", "PyQt6.QtGui"]:
    sys.modules[mod] = MagicMock()

import pytest
# now import your module
```

Run: `pytest tests/test_<feature>.py -v`

### 5. Update the symbol index

```bash
codegraph sync .
```

### 6. Document significant design decisions

If this module introduces a non-obvious design choice, add a record:
```
docs/add/ADD-0XX-<short-title>.md
```

Use existing ADD docs as a template.

---

## Checklist

- [ ] Module file created in `src/modules/`
- [ ] AppServices field added in `services.py`
- [ ] Menu or trigger wired in `tray_app.py` / `menu_builder.py`
- [ ] Tests written using PyQt6 stub pattern
- [ ] `pytest tests/ -v` — all tests passing
- [ ] `flake8 src/ --count --select=E9,F63,F7,F82` — no errors
- [ ] `codegraph sync .` run
- [ ] ADD doc written (if architectural decision was made)
