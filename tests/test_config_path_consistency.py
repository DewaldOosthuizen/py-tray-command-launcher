# SPDX-License-Identifier: GPL-3.0-or-later

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core import config_manager as config_module  # noqa: E402


# [ORCHESTRATOR NOTE] Pre-existing failure — unrelated to issue #37
# Failure: AttributeError: module 'utils' has no attribute 'utils'
# Suggested fix: The 'utils' package inside src/ has a sub-module naming
#   conflict — pkgutil.iter_modules finds a module named 'utils.utils'.
#   Rename src/utils/ to src/app_utils/ (or add an explicit __init__.py
#   that does not re-export itself) and update all imports accordingly.
@unittest.skipIf(
    sys.platform == "win32",
    "Tests rely on XDG/HOME-based config paths which are not used on Windows",
)
class ConfigPathConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        config_module.ConfigManager._instance = None
        self.temp_dir.cleanup()

    def _new_manager(self, base_dir: Path):
        with patch.dict(
            os.environ,
            {
                "XDG_CONFIG_HOME": str(self.tmp_path / "xdg"),
                "HOME": str(self.tmp_path / "home"),
            },
            clear=False,
        ):
            # Reset the singleton and patch the base-dir helper used by
            # ConfigManager during initialization.
            config_module.ConfigManager._instance = None
            with patch.object(
                config_module,
                "_get_base_dir",
                return_value=base_dir,
            ) as mock_get_base_dir:
                manager = config_module.ConfigManager()
                self.assertTrue(
                    mock_get_base_dir.called,
                    "ConfigManager should call core.config_manager._get_base_dir "
                    "when created with a patched base_dir.",
                )
                return manager

    def test_uses_canonical_xdg_config_dir(self):
        manager = self._new_manager(self.tmp_path / "base")

        expected_config_dir = self.tmp_path / "xdg" / "py-tray-command-launcher"
        self.assertEqual(manager.get_config_dir(), expected_config_dir)
        self.assertEqual(
            manager.get_active_commands_file(), expected_config_dir / "commands.json"
        )

    def test_migrates_legacy_commands_into_canonical(self):
        base_dir = self.tmp_path / "base"
        legacy_config_dir = self.tmp_path / "home" / ".py-tray-command-launcher"
        legacy_config_dir.mkdir(parents=True, exist_ok=True)

        legacy_commands = {
            "LegacyGroup": {
                "LegacyCommand": {
                    "command": "echo legacy",
                    "showOutput": False,
                    "confirm": False,
                }
            }
        }

        with open(legacy_config_dir / "commands.json", "w", encoding="utf-8") as f:
            json.dump(legacy_commands, f, indent=4)

        manager = self._new_manager(base_dir)
        with open(manager.get_active_commands_file(), "r", encoding="utf-8") as f:
            migrated = json.load(f)

        self.assertIn("LegacyGroup", migrated)

    def test_merges_legacy_without_overwriting_canonical(self):
        base_dir = self.tmp_path / "base"
        legacy_config_dir = self.tmp_path / "home" / ".py-tray-command-launcher"
        legacy_config_dir.mkdir(parents=True, exist_ok=True)

        canonical_dir = self.tmp_path / "xdg" / "py-tray-command-launcher"
        canonical_dir.mkdir(parents=True, exist_ok=True)

        canonical_commands = {
            "System": {
                "Existing": {
                    "command": "echo canonical",
                    "showOutput": False,
                    "confirm": False,
                }
            }
        }

        legacy_commands = {
            "System": {
                "Existing": {
                    "command": "echo legacy-should-not-overwrite",
                    "showOutput": True,
                    "confirm": True,
                },
                "AddedFromLegacy": {
                    "command": "echo added",
                    "showOutput": False,
                    "confirm": False,
                },
            },
            "LegacyOnlyGroup": {
                "Command": {
                    "command": "echo group",
                    "showOutput": False,
                    "confirm": False,
                }
            },
        }

        with open(canonical_dir / "commands.json", "w", encoding="utf-8") as f:
            json.dump(canonical_commands, f, indent=4)

        with open(legacy_config_dir / "commands.json", "w", encoding="utf-8") as f:
            json.dump(legacy_commands, f, indent=4)

        manager = self._new_manager(base_dir)
        with open(manager.get_active_commands_file(), "r", encoding="utf-8") as f:
            merged = json.load(f)

        self.assertEqual(
            merged["System"]["Existing"]["command"],
            canonical_commands["System"]["Existing"]["command"],
        )
        self.assertIn("AddedFromLegacy", merged["System"])
        self.assertIn("LegacyOnlyGroup", merged)

    def test_import_and_duplicate_detection_use_active_commands_file(self):
        manager = self._new_manager(self.tmp_path / "base")

        initial_commands = {
            "System": {
                "Base": {
                    "command": "echo base",
                    "showOutput": False,
                    "confirm": False,
                }
            }
        }
        manager.save_commands(initial_commands)

        import_file = self.tmp_path / "import.json"
        import_payload = {
            "Imported": {
                "One": {
                    "command": "echo imported",
                    "showOutput": False,
                    "confirm": False,
                }
            }
        }
        with open(import_file, "w", encoding="utf-8") as f:
            json.dump(import_payload, f, indent=4)

        first_import = manager.import_command_group(str(import_file), overwrite=False)
        second_import = manager.import_command_group(str(import_file), overwrite=False)

        self.assertTrue(first_import)
        self.assertFalse(second_import)

        refreshed = manager.get_commands(refresh=True)
        self.assertIn("Imported", refreshed)

        with open(manager.get_active_commands_file(), "r", encoding="utf-8") as f:
            on_disk = json.load(f)
        self.assertIn("Imported", on_disk)

    def test_reads_configured_log_level_from_settings(self):
        manager = self._new_manager(self.tmp_path / "base")

        manager.save_settings({"logging": {"level": "warning"}})

        self.assertEqual(manager.get_configured_log_level(), "WARNING")


if __name__ == "__main__":
    unittest.main()
