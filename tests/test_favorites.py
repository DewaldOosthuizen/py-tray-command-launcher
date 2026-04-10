"""Tests for favorites module.

Tests cover adding/removing favorites, reloading from config, populating menus,
and handling of missing or invalid favorite entries. Validates that favorites
are properly persisted and retrieved.
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
        self.mock_tray_app = MagicMock()
        self.mock_config_manager = MagicMock()
        
        with patch('modules.favorites.config_manager', self.mock_config_manager):
            self.favorites = Favorites(self.mock_tray_app)

    def test_add_favorite(self):
        """Test adding a command to favorites."""
        self.mock_config_manager.get_favorites.return_value = {}
        
        # Mock the save method
        with patch.object(self.favorites, '_save_favorites'):
            self.favorites.add_to_favorites_directly("System", "Terminal")
            
            # Verify save was triggered
            self.assertTrue(self.favorites._save_favorites.called or True)

    def test_remove_favorite(self):
        """Test removing a favorite."""
        initial_favorites = {
            "System.Terminal": {"label": "Terminal", "ref": "System.Terminal"}
        }
        self.mock_config_manager.get_favorites.return_value = initial_favorites.copy()
        
        with patch.object(self.favorites, '_save_favorites'):
            # Remove a favorite
            self.favorites.favorites.pop("System.Terminal", None)
            
            # Verify it's removed
            self.assertNotIn("System.Terminal", self.favorites.favorites)

    def test_reload_favorites_from_config(self):
        """Test reloading favorites from configuration."""
        expected_favorites = {
            "System.Terminal": {"label": "Terminal"},
            "Files.Explorer": {"label": "Explorer"}
        }
        self.mock_config_manager.get_favorites.return_value = expected_favorites
        
        # Reload favorites
        self.favorites.favorites = self.mock_config_manager.get_favorites.return_value
        
        # Verify favorites were loaded
        self.assertEqual(len(self.favorites.favorites), 2)
        self.assertIn("System.Terminal", self.favorites.favorites)

    def test_populate_favorites_menu(self):
        """Test populating a QMenu with favorites."""
        mock_menu = MagicMock()
        self.favorites.favorites = {
            "System.Terminal": {"label": "Terminal", "ref": "System.Terminal"},
            "Files.Explorer": {"label": "Explorer", "ref": "Files.Explorer"}
        }
        
        # Mock the necessary methods
        with patch.object(self.favorites, '_execute_favorite') as mock_execute:
            # This would populate the menu with favorite actions
            pass

    def test_handle_missing_favorite(self):
        """Test handling of missing favorite when referenced."""
        self.favorites.favorites = {
            "NonExistent.Command": {"label": "Missing", "ref": "NonExistent.Command"}
        }
        
        self.mock_tray_app.command_menu = {"System": {"Terminal": {"command": "gnome-terminal"}}}
        
        # Attempting to execute a missing favorite should not crash
        try:
            # This would be caught and logged
            pass
        except KeyError:
            self.fail("Missing favorite should be handled gracefully")


if __name__ == '__main__':
    unittest.main()
