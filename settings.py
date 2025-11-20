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
            "in_progress_recipes": [],
            "automation": {},
            "watchlist": ["hellfire", "rpg"],
            "play_sound_on_found": False,
            "selected_sound": "ping1.mp3",
            "volume": 100
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
        settings_to_save = {
            "theme_index": window_instance.current_theme_index,
            "last_tab_index": window_instance.stacked_widget.currentIndex(),
            "character_path": window_instance.character_path,
            "message_hotkeys": window_instance.message_hotkeys,
            "custom_theme": window_instance.custom_theme,
            "in_progress_recipes": [window_instance.recipes_tab.in_progress_recipes_list.item(i).text() for i in range(window_instance.recipes_tab.in_progress_recipes_list.count())],
            "automation": window_instance.get_automation_settings_from_ui(),
            "watchlist": window_instance.watchlist,
            "play_sound_on_found": window_instance.lobby_placeholder_checkbox.isChecked(),
            "selected_sound": window_instance.selected_sound,
            "volume": window_instance.volume
        }
        with open(self.settings_path, 'w') as f:
            json.dump(settings_to_save, f, indent=4)

    def get(self, key, default=None):
        """Gets a setting value by key, with an optional default."""
        return self.settings.get(key, default)