# SPDX-License-Identifier: GPL-3.0-or-later
"""Contract tests: every ``services.<name>`` used by feature code must exist.

Regression: ``Favorites`` called ``services.resolve_command_reference`` after the
AppServices refactor dropped it. The AttributeError was raised inside a Qt slot,
which aborts the whole application.
"""

import dataclasses
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
for _mod in ("PyQt6", "PyQt6.QtCore", "PyQt6.QtGui", "PyQt6.QtWidgets"):
    sys.modules.setdefault(_mod, MagicMock())

from core.services import AppServices  # noqa: E402  # after Qt stubs and src path setup


def test_every_services_attribute_used_in_src_is_declared():
    declared = {f.name for f in dataclasses.fields(AppServices)}
    used = {}
    for path in SRC.rglob("*.py"):
        for name in re.findall(r"\bservices\.([A-Za-z_]\w*)", path.read_text()):
            used.setdefault(name, path.name)
    missing = {n: f for n, f in used.items() if n not in declared}
    assert not missing, f"services attributes used but not on AppServices: {missing}"
