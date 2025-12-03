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
        # --- DEFINITIVE FIX: Perform a safe read-modify-write operation ---
        # 1. Load the most recent settings from the file to avoid overwriting data from other apps.
        self.load()

        dock_assets_to_save = []
        if hasattr(window_instance, 'image_manager'):
            dock_assets_to_save = [{'path': asset.image_path, 'is_border': asset.is_border_asset} for asset in window_instance.image_manager.dock_assets if asset.image_path]

        # Start with the current settings to avoid losing keys
        settings_to_save = self.settings.copy()

        # Safely update values if the window instance has them
        if hasattr(window_instance, 'current_theme_index'):
            settings_to_save["theme_index"] = window_instance.current_theme_index
        if hasattr(window_instance, 'stacked_widget'):
            settings_to_save["last_tab_index"] = window_instance.stacked_widget.currentIndex()
        if hasattr(window_instance, 'character_load_manager'):
            settings_to_save["character_path"] = window_instance.character_load_manager.character_path
        if hasattr(window_instance, 'automation_manager'):
            settings_to_save["message_hotkeys"] = window_instance.automation_manager.message_hotkeys
            settings_to_save["automation"] = window_instance.get_automation_settings_from_ui()
        if hasattr(window_instance, 'image_manager'):
            settings_to_save["dock_assets"] = dock_assets_to_save
        if hasattr(window_instance, 'lobby_manager'):
            settings_to_save["watchlist"] = window_instance.lobby_manager.watchlist
            settings_to_save["play_sound_on_found"] = window_instance.lobby_manager.play_sound_on_found
            settings_to_save["selected_sound"] = window_instance.lobby_manager.selected_sound
            settings_to_save["volume"] = window_instance.lobby_manager.volume
        if hasattr(window_instance, 'font_family'):
            settings_to_save["font_family"] = window_instance.font_family
        if hasattr(window_instance, 'font_size'):
            settings_to_save["font_size"] = window_instance.font_size


        with open(self.settings_path, 'w') as f:
            json.dump(settings_to_save, f, indent=4)

    def get(self, key, default=None):
        """Gets a setting value by key, with an optional default."""
        return self.settings.get(key, default)