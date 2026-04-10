"""Tests for favorites module.

Tests call the real public methods (add_to_favorites_directly,
remove_from_favorites, populate_favorites_menu) while patching
modules.favorites.config_manager and QMessageBox so that no filesystem I/O
or GUI dialogs appear.
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock, call

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from modules.favorites import Favorites


class TestFavorites(unittest.TestCase):
    """Test suite for Favorites module."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_services = MagicMock()
        self.mock_config_manager = MagicMock()
        self.mock_config_manager.get_favorites.return_value = {}

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            self.favorites = Favorites(self.mock_services)

    # ------------------------------------------------------------------
    # add_to_favorites_directly
    # ------------------------------------------------------------------

    def test_add_favorite_directly_success(self):
        """add_to_favorites_directly should call config_manager.add_to_favorites."""
        self.mock_config_manager.add_to_favorites.return_value = True

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QMessageBox'):
                self.favorites.add_to_favorites_directly("System", "Terminal")

        self.mock_config_manager.add_to_favorites.assert_called_once_with(
            "System.Terminal", "Terminal"
        )

    def test_add_favorite_directly_reloads_on_success(self):
        """add_to_favorites_directly should trigger reload when addition succeeds."""
        self.mock_config_manager.add_to_favorites.return_value = True

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QMessageBox'):
                self.favorites.add_to_favorites_directly("System", "Terminal")

        self.mock_services.reload_favorites_commands.assert_called_once()

    def test_add_favorite_directly_no_reload_on_failure(self):
        """add_to_favorites_directly should not reload when config_manager returns False."""
        self.mock_config_manager.add_to_favorites.return_value = False

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QMessageBox'):
                self.favorites.add_to_favorites_directly("System", "Terminal")

        self.mock_services.reload_favorites_commands.assert_not_called()

    # ------------------------------------------------------------------
    # remove_from_favorites
    # ------------------------------------------------------------------

    def test_remove_favorite_success(self):
        """remove_from_favorites should call config_manager.remove_from_favorites."""
        self.mock_config_manager.remove_from_favorites.return_value = True

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QMessageBox'):
                self.favorites.remove_from_favorites("Terminal")

        self.mock_config_manager.remove_from_favorites.assert_called_once_with("Terminal")

    def test_remove_favorite_reloads_on_success(self):
        """remove_from_favorites should trigger reload when removal succeeds."""
        self.mock_config_manager.remove_from_favorites.return_value = True

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QMessageBox'):
                self.favorites.remove_from_favorites("Terminal")

        self.mock_services.reload_favorites_commands.assert_called_once()

    def test_remove_favorite_no_reload_on_failure(self):
        """remove_from_favorites should not reload when removal fails."""
        self.mock_config_manager.remove_from_favorites.return_value = False

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QMessageBox'):
                self.favorites.remove_from_favorites("NonExistent")

        self.mock_services.reload_favorites_commands.assert_not_called()

    # ------------------------------------------------------------------
    # populate_favorites_menu
    # ------------------------------------------------------------------

    def test_populate_favorites_menu_with_entries(self):
        """populate_favorites_menu should add actions for each favorite."""
        mock_menu = MagicMock()
        self.mock_config_manager.get_favorites.return_value = {
            "Terminal": {"command": "gnome-terminal"},
            "Editor": {"command": "gedit"},
        }
        self.mock_services.resolve_command_reference.side_effect = lambda g, l, item: item
        self.mock_services.resolve_icon_path.return_value = None
        self.mock_config_manager.get_base_dir.return_value = str(PROJECT_ROOT)

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QIcon', return_value=MagicMock()):
                with patch('modules.favorites.QAction', return_value=MagicMock()):
                    with patch('modules.favorites.os.path.isfile', return_value=False):
                        self.favorites.populate_favorites_menu(mock_menu)

        # At least one addAction call per favorite entry
        self.assertGreaterEqual(mock_menu.addAction.call_count, 2)

    def test_populate_favorites_menu_empty(self):
        """populate_favorites_menu should show placeholder when no favorites exist."""
        mock_menu = MagicMock()
        self.mock_config_manager.get_favorites.return_value = {}

        with patch('modules.favorites.config_manager', self.mock_config_manager):
            with patch('modules.favorites.QAction') as mock_qaction_cls:
                mock_qaction = MagicMock()
                mock_qaction_cls.return_value = mock_qaction
                self.favorites.populate_favorites_menu(mock_menu)

        self.mock_config_manager.get_favorites.assert_called()
        # "No Favorites" should be the first QAction created
        mock_qaction_cls.assert_any_call("No Favorites", mock_menu)


if __name__ == '__main__':
    unittest.main()
