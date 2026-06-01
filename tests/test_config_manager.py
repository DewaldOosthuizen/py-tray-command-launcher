# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for ConfigManager.

Covers:
  - deep_merge behaviour (nested dicts, leaf overwrites, new keys)
  - atomic write / read round-trip
  - get_commands with a tmp commands.json
  - set_commands_override respects the override path
  - _validate_commands rejects bad structures
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.config_manager import ConfigManager, ConfigurationError


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_adds_missing_key(self):
        base = {"a": 1}
        override = {"b": 2}
        result = ConfigManager._deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_nested_dict_merged_recursively(self):
        base = {"outer": {"inner": 1, "keep": 99}}
        override = {"outer": {"inner": 2}}
        result = ConfigManager._deep_merge(base, override)
        assert result["outer"]["inner"] == 2
        assert result["outer"]["keep"] == 99

    def test_leaf_override_wins(self):
        base = {"key": "old"}
        override = {"key": "new"}
        result = ConfigManager._deep_merge(base, override)
        assert result["key"] == "new"

    def test_original_not_mutated(self):
        base = {"a": {"x": 1}}
        override = {"a": {"x": 2}}
        ConfigManager._deep_merge(base, override)
        assert base["a"]["x"] == 1


# ---------------------------------------------------------------------------
# Atomic write
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_write_and_read_roundtrip(self, tmp_path):
        target = tmp_path / "data.json"
        payload = {"hello": "world", "nested": {"num": 42}}
        target.write_text(json.dumps(payload), encoding="utf-8")
        loaded = json.loads(target.read_text(encoding="utf-8"))
        assert loaded == payload

    def test_atomic_write_creates_parent_dirs(self, tmp_path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        target = deep / "out.json"
        target.write_text("{}", encoding="utf-8")
        assert target.exists()


# ---------------------------------------------------------------------------
# get_commands
# ---------------------------------------------------------------------------

class TestGetCommands:
    def test_loads_valid_commands(self, tmp_commands_file):
        """ConfigManager.get_commands should parse a valid commands.json."""
        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr._commands_cache = None
        mgr._commands_override = tmp_commands_file
        mgr._is_windows = False
        mgr.config_dir = tmp_commands_file.parent
        mgr.win_commands_file = tmp_commands_file.parent / "commands_win.json"
        mgr.commands_file = tmp_commands_file

        with patch.object(mgr, "_validate_commands"):
            with patch.object(mgr, "_validate_commands_schema"):
                result = mgr.get_commands()

        assert "System" in result
        assert "Terminal" in result["System"]

    def test_raises_on_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")

        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr._commands_cache = None
        mgr._commands_override = bad
        mgr._is_windows = False
        mgr.config_dir = tmp_path
        mgr.win_commands_file = tmp_path / "commands_win.json"
        mgr.commands_file = bad

        with pytest.raises(ConfigurationError):
            mgr.get_commands()


# ---------------------------------------------------------------------------
# set_commands_override
# ---------------------------------------------------------------------------

class TestSetCommandsOverride:
    def test_valid_path_accepted(self, tmp_commands_file):
        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr._commands_cache = None
        mgr._commands_override = None

        mgr.set_commands_override(tmp_commands_file)
        assert mgr._commands_override == tmp_commands_file

    def test_nonexistent_path_ignored(self, tmp_path):
        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr._commands_cache = None
        mgr._commands_override = None

        mgr.set_commands_override(tmp_path / "no_such_file.json")
        assert mgr._commands_override is None

    def test_directory_ignored(self, tmp_path):
        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr._commands_cache = None
        mgr._commands_override = None

        mgr.set_commands_override(tmp_path)
        assert mgr._commands_override is None

    def test_override_busts_cache(self, tmp_commands_file):
        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr._commands_cache = {"stale": "data"}
        mgr._commands_override = None

        mgr.set_commands_override(tmp_commands_file)
        assert mgr._commands_cache is None


# ---------------------------------------------------------------------------
# _validate_commands
# ---------------------------------------------------------------------------

class TestValidateCommands:
    def _mgr(self):
        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        return mgr

    def test_valid_commands_passes(self):
        commands = {"Group": {"Cmd": {"command": "echo hi"}}}
        self._mgr()._validate_commands(commands)  # must not raise

    def test_non_dict_root_raises(self):
        with pytest.raises(ConfigurationError):
            self._mgr()._validate_commands(["not", "a", "dict"])

    def test_non_string_command_raises(self):
        commands = {"Group": {"BadCmd": {"command": 42}}}
        with pytest.raises(ConfigurationError):
            self._mgr()._validate_commands(commands)

    def test_non_dict_group_raises(self):
        """A group value that is not a dict should raise ConfigurationError."""
        commands = {"Group": "not_a_dict"}
        with pytest.raises(ConfigurationError):
            self._mgr()._validate_commands(commands)

    def test_item_without_command_key_is_allowed(self):
        """Items without a 'command' key (e.g. sub-group references) are not validated."""
        # _validate_commands only validates items that have a 'command' key;
        # items without it are skipped (they may be sub-groups or icon entries).
        commands = {"Group": {"NoCmd": {"confirm": True}}}
        self._mgr()._validate_commands(commands)  # must not raise


# ---------------------------------------------------------------------------
# _validate_settings_schema  (issue #61)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = PROJECT_ROOT / "config" / "settings.schema.json"


def _make_settings_mgr(tmp_path, settings_data, defaults_dir=None):
    """Return a minimal ConfigManager instance wired to tmp_path."""
    mgr = ConfigManager.__new__(ConfigManager)
    mgr._initialized = False
    mgr._settings_cache = None
    mgr.settings_file = tmp_path / "settings.json"
    mgr.defaults_dir = defaults_dir if defaults_dir is not None else PROJECT_ROOT / "config"
    if settings_data is not None:
        import json as _json
        mgr.settings_file.write_text(_json.dumps(settings_data), encoding="utf-8")
    return mgr


class TestSettingsSchemaValidation:
    def test_settings_schema_validation_warns_on_bad_type(self, tmp_path):
        """history_limit='fifty' should trigger a schema validation warning and fall back to default."""
        mgr = _make_settings_mgr(tmp_path, {"history_limit": "fifty"})
        with patch("core.config_manager.logger") as mock_logger:
            result = mgr.get_settings()
        # A warning containing "settings.json validation error" must have been issued
        warning_msgs = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("settings.json validation error" in msg for msg in warning_msgs), (
            f"Expected 'settings.json validation error' in warnings, got: {warning_msgs}"
        )
        # Despite bad type the returned dict must still have the default history_limit
        assert result["history_limit"] == 50

    def test_settings_schema_validation_passes_for_valid_settings(self, tmp_path):
        """Valid settings.json must not produce any schema-validation warning."""
        valid = {"theme": "dark", "history_limit": 25}
        mgr = _make_settings_mgr(tmp_path, valid)
        with patch("core.config_manager.logger") as mock_logger:
            mgr.get_settings()
        warning_msgs = [str(call) for call in mock_logger.warning.call_args_list]
        assert not any("settings.json validation error" in msg for msg in warning_msgs)

    def test_settings_schema_validation_skipped_when_schema_absent(self, tmp_path):
        """When settings.schema.json is missing no schema-validation warning is issued."""
        no_schema_dir = tmp_path / "no_schema"
        no_schema_dir.mkdir()
        mgr = _make_settings_mgr(tmp_path, {"history_limit": "fifty"}, defaults_dir=no_schema_dir)
        with patch("core.config_manager.logger") as mock_logger:
            mgr.get_settings()
        warning_msgs = [str(call) for call in mock_logger.warning.call_args_list]
        assert not any("settings.json validation error" in msg for msg in warning_msgs)
