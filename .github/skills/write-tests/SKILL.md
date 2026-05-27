---
name: write-tests
description: How to write unit tests for py-tray-command-launcher. Covers the PyQt6 stub pattern, fixture conventions, mocking AppServices, and test file structure.
license: MIT
metadata:
  author: project
  version: "1.0"
---

# Writing Tests

All tests live in `tests/`. Run with:
```bash
source venv/bin/activate
pytest tests/ -v
```

Expected: **50 tests, all passing.**

---

## Critical: PyQt6 stub pattern

The host system may have PyQt5, not PyQt6. Every test file that touches src modules
MUST stub PyQt6 at the top, BEFORE any src imports:

```python
from unittest.mock import MagicMock, patch
import sys

# Stub ALL PyQt6 submodules your src code imports
_mock_qt = MagicMock()
for mod in [
    "PyQt6",
    "PyQt6.QtWidgets",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtNetwork",
]:
    sys.modules[mod] = _mock_qt

import pytest
# Only NOW import src modules
from core.config_manager import ConfigManager
```

Skipping this causes `ModuleNotFoundError: No module named 'PyQt6'` on systems
with only PyQt5 installed.

---

## Fixture conventions

Use `conftest.py` for shared fixtures:

```python
# tests/conftest.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock

@pytest.fixture
def tmp_config(tmp_path):
    """A temp commands.json file with minimal valid content."""
    cfg = tmp_path / "commands.json"
    cfg.write_text('{"System": {"Echo": {"command": "echo hello"}}}')
    return cfg

@pytest.fixture
def mock_services():
    """A minimal AppServices mock."""
    svc = MagicMock()
    svc.config_manager.get_commands.return_value = {
        "System": {"Echo": {"command": "echo hello"}}
    }
    return svc
```

---

## Patching instance methods that aren't properties

`resource_roots()` in `IconResolver` is a regular method. Patch on the CLASS:

```python
with patch.object(IconResolver, "resource_roots", return_value=[tmp_path]):
    resolver = IconResolver()
    result = resolver.resolve("myicon")
```

Do NOT patch `instance.resource_roots` — it won't work.

---

## Testing ConfigManager with a custom path

```python
def test_custom_config(tmp_path):
    cfg_file = tmp_path / "commands.json"
    cfg_file.write_text('{"A": {"B": {"command": "echo b"}}}')
    cm = ConfigManager(config_path=str(cfg_file))
    assert "A" in cm.get_commands()
```

---

## Mocking QProcess / subprocess

```python
from unittest.mock import MagicMock, patch

def test_silent_execute(mock_services):
    with patch("modules.command_executor.QProcess") as MockQP:
        proc = MockQP.return_value
        executor = CommandExecutor(mock_services)
        executor.execute_command_silently("echo hi")
        proc.start.assert_called_once()
```

---

## IconResolver TTL behaviour

When `_cache_ttl_seconds == 0`, TTL check is skipped entirely (no expiry).
Test accordingly:
```python
resolver = IconResolver(cache_ttl_seconds=0)
# cached file should never be treated as expired
```

---

## File structure

```
tests/
├── __init__.py
├── conftest.py                    # shared fixtures
├── test_config_manager.py
├── test_favorites_path.py
├── test_icon_resolver.py
├── test_single_instance.py
└── test_command_executor.py
```

Add new files as `test_<module_name>.py`.

---

## Checklist

- [ ] PyQt6 stubs injected before any src imports
- [ ] Fixtures in conftest.py, not inline
- [ ] No real filesystem side effects — use `tmp_path`
- [ ] No real QProcess/subprocess spawned — mock it
- [ ] `pytest tests/ -v` — all tests passing after your additions
