# SPDX-License-Identifier: GPL-3.0-or-later
"""Version source and strict CalVer comparison tests."""

import importlib
import sys
from types import ModuleType
from unittest.mock import patch

from core.version import get_current_version, parse_calver


def test_parse_calver_returns_integer_tuple_and_orders_same_day_release():
    assert parse_calver("2026.10.21") == (2026, 10, 21)
    assert parse_calver("2026.10.21.1") == (2026, 10, 21, 1)
    assert parse_calver("2026.10.21") < parse_calver("2026.10.21.1")


def test_parse_calver_rejects_non_calver_and_invalid_dates():
    for value in ("1.0.0", "2026.1.21", "2026.02.30", "2026.10.21.0", "2026.10.21.-1"):
        assert parse_calver(value) is None


def test_bundled_version_has_precedence_over_package_metadata(monkeypatch):
    bundled = ModuleType("_version")
    bundled.__version__ = "2026.10.21"
    monkeypatch.setitem(sys.modules, "_version", bundled)

    assert get_current_version() == "2026.10.21"


def test_installed_metadata_is_used_when_no_bundled_version(monkeypatch):
    monkeypatch.delitem(sys.modules, "_version", raising=False)
    with patch("core.version.metadata.version", return_value="2026.10.22"):
        assert get_current_version() == "2026.10.22"


def test_missing_version_sources_fall_back_to_zero(monkeypatch):
    monkeypatch.delitem(sys.modules, "_version", raising=False)
    with patch(
        "core.version.metadata.version", side_effect=importlib.metadata.PackageNotFoundError
    ):
        assert get_current_version() == "0.0.0"
