import json
import os
from utils import get_base_path

class SettingsManager:
    """Handles loading and saving application settings to a JSON file."""

    def __init__(self):
        self.settings_path = os.path.join(get_base_path(), "settings.json")
        self.defaults = {
            "theme_index": 0,
            "last_tab_index": 0,
            "character_path": os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG"),
            "message_hotkeys": {},
            "custom_theme": {"bg": "#121212", "fg": "#F0F0F0", "accent": "#FF7F50"},
            "custom_title_image_path": "",
            "in_progress_recipes": [],
            "keybinds": {},
            "automation": {},
            "watchlist": ["hellfire", "rpg"],
            "play_sound_on_found": False,
            "selected_sound": "ping1.mp3",
            "volume": 100,            
            "font_family": "Segoe UI", # This is part of the PySide6 app, not the Tkinter one
            "font_size": 11,
            "dock_assets": [] # NEW: To store paths of loaded dock images
        }
        self.settings = self.defaults.copy()
        self.load()

    def load(self):
        """Loads settings from the JSON file, falling back to defaults for missing keys."""
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, 'r') as f:
                    loaded_settings = json.load(f)
                    # Merge loaded settings with defaults to ensure all keys are present
                    self.settings.update(loaded_settings)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Could not load settings, using defaults. Error: {e}")
            self.settings = self.defaults.copy()

    def save(self, window_instance):
        """Gathers current state from the UI and saves it to the JSON file."""
        # --- DEFINITIVE FIX: Safely handle dock_assets saving ---
        # Check for image_manager before trying to access it to prevent AttributeError
        # when saving from the main PySide6 application.
        dock_assets_to_save = []
        if hasattr(window_instance, 'image_manager'):
            dock_assets_to_save = [{'path': asset.image_path, 'is_border': asset.is_border_asset} for asset in window_instance.image_manager.dock_assets if asset.image_path]

        settings_to_save = {
            "theme_index": window_instance.current_theme_index,
            "last_tab_index": window_instance.stacked_widget.currentIndex(),
            "character_path": window_instance.character_load_manager.character_path, # type: ignore
            "message_hotkeys": window_instance.automation_manager.message_hotkeys,
            "custom_theme": window_instance.custom_theme,
            "custom_title_image_path": window_instance.custom_title_image_path,
            "in_progress_recipes": [window_instance.items_tab.in_progress_recipes_list.item(i).text() for i in range(window_instance.items_tab.in_progress_recipes_list.count())],
            "keybinds": {},
            "dock_assets": dock_assets_to_save,
            "automation": window_instance.get_automation_settings_from_ui(),
            "watchlist": window_instance.lobby_manager.watchlist,
            "play_sound_on_found": window_instance.lobby_manager.lobbies_tab.lobby_placeholder_checkbox.isChecked(),
            "selected_sound": window_instance.lobby_manager.selected_sound,
            "volume": window_instance.lobby_manager.volume,
            "font_family": window_instance.font_family,
            "font_size": window_instance.font_size
        }
        with open(self.settings_path, 'w') as f:
            json.dump(settings_to_save, f, indent=4)

    def get(self, key, default=None):
        """Gets a setting value by key, with an optional default."""
        return self.settings.get(key, default)