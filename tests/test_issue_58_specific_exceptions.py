# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for issue #58 - specific exception types in ConfigManager.

Verifies that broad `except Exception` handlers have been replaced with
specific exception types, so unexpected exception types propagate properly.
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


def _bare_mgr(tmp_path):
    """Return a ConfigManager instance bypassing __init__ with tmp_path config."""
    mgr = ConfigManager.__new__(ConfigManager)
    mgr._initialized = False
    mgr._commands_cache = None
    mgr._history_cache = None
    mgr._favorites_cache = None
    mgr._settings_cache = None
    mgr._is_windows = False
    mgr._commands_override = None
    mgr.config_dir = tmp_path
    mgr.backup_dir = tmp_path / "backups"
    mgr.backup_dir.mkdir(exist_ok=True)
    mgr.commands_file = tmp_path / "commands.json"
    mgr.win_commands_file = tmp_path / "win-commands.json"
    mgr.history_file = tmp_path / "history.json"
    mgr.favorites_file = tmp_path / "favorites.json"
    mgr.settings_file = tmp_path / "settings.json"
    mgr.defaults_dir = tmp_path / "defaults"
    return mgr


class TestWriteJsonAtomicSpecificExceptions:
    """_write_json_atomic should catch (OSError, TypeError, ValueError), not broad Exception."""

    def test_oserror_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        target = tmp_path / "out.json"
        with patch("os.replace", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                mgr._write_json_atomic(target, {"key": "val"})

    def test_typeerror_propagates(self, tmp_path):
        """TypeError from json.dump (non-serializable) should propagate."""
        mgr = _bare_mgr(tmp_path)
        target = tmp_path / "out.json"
        # object() is not JSON-serializable → TypeError
        with pytest.raises(TypeError):
            mgr._write_json_atomic(target, {"key": object()})

    def test_unexpected_exception_not_swallowed(self, tmp_path):
        """A RuntimeError (not in the catch list) must propagate through."""
        mgr = _bare_mgr(tmp_path)
        target = tmp_path / "out.json"
        with patch("os.replace", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr._write_json_atomic(target, {"key": "val"})


class TestGetSettingsSpecificExceptions:
    """get_settings second except should be OSError, not broad Exception."""

    def test_oserror_on_open_falls_back_to_defaults(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        # Create the settings file so .exists() returns True
        mgr.settings_file.write_text("{}", encoding="utf-8")
        with patch("builtins.open", side_effect=OSError("permission denied")):
            result = mgr.get_settings()
        # Should return defaults, not raise
        assert isinstance(result, dict)
        assert "theme" in result

    def test_runtime_error_on_open_propagates(self, tmp_path):
        """RuntimeError should NOT be caught by the specific OSError handler."""
        mgr = _bare_mgr(tmp_path)
        mgr.settings_file.write_text("{}", encoding="utf-8")
        with patch("builtins.open", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.get_settings()


class TestSaveSettingsSpecificExceptions:
    """save_settings should catch (OSError, TypeError, ValueError), re-raise ConfigurationError."""

    def test_oserror_raises_configuration_error(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_write_json_atomic", side_effect=OSError("disk full")):
            with pytest.raises(ConfigurationError, match="Failed to save settings"):
                mgr.save_settings({"theme": "dark"})

    def test_configuration_error_reraises_directly(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_write_json_atomic", side_effect=ConfigurationError("inner")):
            with pytest.raises(ConfigurationError, match="inner"):
                mgr.save_settings({"theme": "dark"})

    def test_runtime_error_not_swallowed(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_write_json_atomic", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.save_settings({"theme": "dark"})


class TestGetCommandsSpecificExceptions:
    """get_commands second except should be (OSError, ConfigurationError)."""

    def test_oserror_raises_configuration_error(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.commands_file.write_text('{"Group": {}}', encoding="utf-8")
        with patch("builtins.open", side_effect=OSError("perm denied")):
            with pytest.raises(ConfigurationError):
                mgr.get_commands()

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.commands_file.write_text('{"Group": {}}', encoding="utf-8")
        with patch("builtins.open", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.get_commands()


class TestSaveCommandsSpecificExceptions:
    """save_commands except should be (OSError, TypeError, ValueError)."""

    def test_oserror_raises_configuration_error(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_validate_commands"):
            with patch.object(mgr, "backup_commands"):
                with patch.object(mgr, "_write_json_atomic", side_effect=OSError("disk")):
                    with pytest.raises(ConfigurationError):
                        mgr.save_commands({"Group": {}})

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_validate_commands"):
            with patch.object(mgr, "backup_commands"):
                with patch.object(mgr, "_write_json_atomic", side_effect=RuntimeError("unexpected")):
                    with pytest.raises(RuntimeError):
                        mgr.save_commands({"Group": {}})


class TestGetHistorySpecificExceptions:
    """get_history except should be (OSError, json.JSONDecodeError, ValueError)."""

    def test_oserror_returns_empty(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.history_file.write_text("[]", encoding="utf-8")
        with patch("builtins.open", side_effect=OSError("perm")):
            result = mgr.get_history()
        assert result == []

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.history_file.write_text("[]", encoding="utf-8")
        with patch("builtins.open", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.get_history()


class TestSaveHistorySpecificExceptions:
    """save_history except should be (OSError, TypeError, ValueError)."""

    def test_oserror_logged_not_raised(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_write_json_atomic", side_effect=OSError("disk")):
            # Should not raise
            mgr.save_history([])

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_write_json_atomic", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.save_history([])


class TestGetFavoritesSpecificExceptions:
    """get_favorites except should be (OSError, json.JSONDecodeError, ValueError)."""

    def test_oserror_returns_empty(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.favorites_file.write_text("{}", encoding="utf-8")
        with patch("builtins.open", side_effect=OSError("perm")):
            result = mgr.get_favorites()
        assert result == {}

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.favorites_file.write_text("{}", encoding="utf-8")
        with patch("builtins.open", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.get_favorites()


class TestSaveFavoritesSpecificExceptions:
    """save_favorites except should be (OSError, TypeError, ValueError)."""

    def test_oserror_logged_not_raised(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_write_json_atomic", side_effect=OSError("disk")):
            mgr.save_favorites({})  # should not raise

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "_write_json_atomic", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.save_favorites({})


class TestBackupCommandsSpecificExceptions:
    """backup_commands except should be OSError."""

    def test_oserror_returns_empty_string(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.commands_file.write_text("{}", encoding="utf-8")
        with patch("shutil.copy2", side_effect=OSError("disk")):
            result = mgr.backup_commands()
        assert result == ""

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.commands_file.write_text("{}", encoding="utf-8")
        with patch("shutil.copy2", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.backup_commands()


class TestListBackupsSpecificExceptions:
    """list_backups except should be OSError."""

    def test_oserror_returns_empty_list(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch("os.listdir", side_effect=OSError("perm")):
            result = mgr.list_backups()
        assert result == []

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch("os.listdir", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.list_backups()


class TestRestoreFromBackupSpecificExceptions:
    """restore_from_backup except should be OSError."""

    def test_oserror_returns_false(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        backup = tmp_path / "backup.json"
        backup.write_text("{}", encoding="utf-8")
        with patch.object(mgr, "backup_commands"):
            with patch("shutil.copy2", side_effect=OSError("disk")):
                result = mgr.restore_from_backup(str(backup))
        assert result is False

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        backup = tmp_path / "backup.json"
        backup.write_text("{}", encoding="utf-8")
        with patch.object(mgr, "backup_commands"):
            with patch("shutil.copy2", side_effect=RuntimeError("unexpected")):
                with pytest.raises(RuntimeError):
                    mgr.restore_from_backup(str(backup))


class TestImportCommandGroupSpecificExceptions:
    """import_command_group except should be (OSError, json.JSONDecodeError, ConfigurationError)."""

    def test_oserror_returns_false(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch("builtins.open", side_effect=OSError("perm")):
            result = mgr.import_command_group(str(tmp_path / "import.json"))
        assert result is False

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch("builtins.open", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.import_command_group(str(tmp_path / "import.json"))


class TestExportCommandGroupSpecificExceptions:
    """export_command_group except should be (OSError, TypeError, ConfigurationError)."""

    def test_oserror_returns_false(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "get_commands", return_value={"MyGroup": {}}):
            with patch("builtins.open", side_effect=OSError("perm")):
                result = mgr.export_command_group("MyGroup", str(tmp_path / "out.json"))
        assert result is False

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "get_commands", return_value={"MyGroup": {}}):
            with patch("builtins.open", side_effect=RuntimeError("unexpected")):
                with pytest.raises(RuntimeError):
                    mgr.export_command_group("MyGroup", str(tmp_path / "out.json"))


class TestAddToFavoritesSpecificExceptions:
    """add_to_favorites except should be (OSError, ConfigurationError, TypeError, ValueError)."""

    def test_oserror_returns_false(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        commands = {"Group": {"Cmd": {"command": "echo hi"}}}
        with patch.object(mgr, "get_commands", return_value=commands):
            with patch.object(mgr, "get_favorites", side_effect=OSError("perm")):
                result = mgr.add_to_favorites("Group.Cmd")
        assert result is False

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        commands = {"Group": {"Cmd": {"command": "echo hi"}}}
        with patch.object(mgr, "get_commands", return_value=commands):
            with patch.object(mgr, "get_favorites", side_effect=RuntimeError("unexpected")):
                with pytest.raises(RuntimeError):
                    mgr.add_to_favorites("Group.Cmd")


class TestRemoveFromFavoritesSpecificExceptions:
    """remove_from_favorites except should be (OSError, ConfigurationError)."""

    def test_oserror_returns_false(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "get_favorites", side_effect=OSError("perm")):
            result = mgr.remove_from_favorites("label")
        assert result is False

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "get_favorites", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.remove_from_favorites("label")


class TestMigrateFavoritesSpecificExceptions:
    """migrate_favorites_from_commands except should be (OSError, json.JSONDecodeError, ConfigurationError)."""

    def test_oserror_returns_false(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "get_commands", side_effect=OSError("perm")):
            result = mgr.migrate_favorites_from_commands()
        assert result is False

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch.object(mgr, "get_commands", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr.migrate_favorites_from_commands()


class TestCreateDefaultCommandsSpecificExceptions:
    """_create_default_commands except should be (OSError, TypeError, ValueError)."""

    def test_oserror_logged_not_raised(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.defaults_dir = tmp_path / "defaults"
        with patch.object(mgr, "_write_json_atomic", side_effect=OSError("disk")):
            mgr._create_default_commands(tmp_path / "cmds.json")  # should not raise

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        mgr.defaults_dir = tmp_path / "defaults"
        with patch.object(mgr, "_write_json_atomic", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr._create_default_commands(tmp_path / "cmds.json")


class TestLoadCommandsFromFileSpecificExceptions:
    """_load_commands_from_file except should be (OSError, json.JSONDecodeError, ValueError)."""

    def test_oserror_returns_empty_dict(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch("builtins.open", side_effect=OSError("perm")):
            result = mgr._load_commands_from_file(tmp_path / "cmds.json")
        assert result == {}

    def test_json_decode_error_returns_empty_dict(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{invalid}", encoding="utf-8")
        mgr = _bare_mgr(tmp_path)
        result = mgr._load_commands_from_file(bad)
        assert result == {}

    def test_runtime_error_propagates(self, tmp_path):
        mgr = _bare_mgr(tmp_path)
        with patch("builtins.open", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                mgr._load_commands_from_file(tmp_path / "cmds.json")
