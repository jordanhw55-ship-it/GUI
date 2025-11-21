import sys
import json
import os
import re
from typing import List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QGroupBox, QFileDialog,
    QTextEdit, QListWidgetItem, QColorDialog, QCheckBox, QSlider
)
from PySide6.QtCore import Signal, Qt, QThread, QTimer, QUrl, QPoint
from PySide6.QtGui import QMouseEvent, QColor, QIntValidator, QFont, QPalette
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import keyboard   # type: ignore
import pyautogui  # type: ignore

from utils import get_base_path, DARK_STYLE, LIGHT_STYLE, FOREST_STYLE, OCEAN_STYLE
from data import ItemDatabase
from workers import LobbyFetcher, HotkeyCaptureWorker, ChatMessageWorker, LobbyHeartbeatChecker
from settings import SettingsManager
from automation_manager import AutomationManager
from ui_tab_widgets import CharacterLoadTab, AutomationTab, ItemsTab, QuickcastTab, LobbiesTab
from ui_overlay import OverlayStatus

try:
    import win32gui # type: ignore
    import win32api # type: ignore
    import win32con # type: ignore
except ImportError:
    win32gui = None
    win32api = None
    win32con = None


class ThemePreview(QWidget):
    """Clickable theme preview."""
    clicked = Signal()
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class AlignedTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, alignment=Qt.AlignmentFlag.AlignCenter):
        super().__init__(text)
        self.setTextAlignment(alignment)


class CustomTabBar(QWidget):
    tab_selected = Signal(int)
    def __init__(self, tab_names: list[str], tabs_per_row: int = 4):
        super().__init__()
        self.tab_names = tab_names
        self.tabs_per_row = tabs_per_row
        self.buttons: List[QPushButton] = []
        self.current_index = -1
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)
        self.layout.setSpacing(2)
        self._create_buttons()
    def _create_buttons(self):
        for i, name in enumerate(self.tab_names):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))
            self.buttons.append(button)
            row = i // self.tabs_per_row
            col = i % self.tabs_per_row
            self.layout.addWidget(button, row, col)
        if self.buttons:
            self._on_button_clicked(0)
    def _on_button_clicked(self, index: int):
        if self.current_index != index:
            if self.current_index != -1:
                self.buttons[self.current_index].setChecked(False)
            self.buttons[index].setChecked(True)
            self.current_index = index
            self.tab_selected.emit(index)
    def apply_style(self, theme_name: str, dark_mode: bool):
        if theme_name == "Black/Orange":
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2A2A2C;
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 6px;
                    color: #F0F0F0;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #FFA64D; }
                QPushButton:checked {
                    background-color: #FF7F50;
                    color: #F0F0F0;
                    border-color: #FF7F50;
                }
            """)
        elif dark_mode:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #2A2A2C;
                    border: 1px solid #444444;
                    padding: 8px;
                    border-radius: 6px;
                    color: #EAEAEA;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #4682B4; }
                QPushButton:checked {
                    background-color: #1E90FF;
                    color: #EAEAEA;
                    border-color: #4169E1;
                }
            """)
        elif theme_name == "White/Blue":
            self.setStyleSheet("""
                QPushButton {
                    background-color: #87CEEB;
                    border: 1px solid #4682B4;
                    padding: 8px;
                    border-radius: 6px;
                    color: #000080;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #87CEFA; }
                QPushButton:checked {
                    background-color: #4682B4;
                    color: #F0F8FF;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #FFC0CB;
                    border: 1px solid #E6A8B8;
                    padding: 8px;
                    border-radius: 6px;
                    color: #2E3440;
                    font-size: 16px;
                }
                QPushButton:hover { background-color: #F6B3F5; }
                QPushButton:checked {
                    background-color: #DB7093;
                    color: #2E3440;
                }
            """)


class SimpleWindow(QMainWindow):
    start_automation_signal = Signal()
    stop_automation_signal = Signal()
    send_message_signal = Signal(str)
    load_character_signal = Signal()

    def __init__(self):
        super().__init__()

        self.settings_manager = SettingsManager()

        # Theme state
        self.current_theme_index = self.settings_manager.get("theme_index")
        self.last_tab_index = self.settings_manager.get("last_tab_index")
        self.custom_theme = self.settings_manager.get("custom_theme", {
            "bg": "#121212",
            # This attribute is for backward compatibility with old settings files and is no longer used.
            "fg": "#F0F0F0",
            "accent": "#FF7F50"
        })

        self.old_pos = None
        self.all_lobbies = []
        self.thread = None # type: ignore
        self.last_lobby_id = 0 # For heartbeat check
        self.hotkey_ids = {}            # {hotkey_str: id from keyboard.add_hotkey}
        self.is_sending_message = False
        self.game_title = "Warcraft III"

        # Automation state flags
        self.automation_settings = {} # To hold loaded settings
        self.is_capturing_hotkey = False
        self.theme_previews = []
        self.previous_watched_lobbies = set()
        self.dark_mode = True # Initialize with a default
        self.message_hotkeys = {}       # {hotkey_str: message_str}
        self.watchlist = ["hellfire", "rpg"] # Default, will be overwritten by load_settings
        self.play_sound_on_found = False # Default, will be overwritten by load_settings
        self.selected_sound = self.settings_manager.get("selected_sound", "ping1.mp3")
        self.volume = self.settings_manager.get("volume", 100)
        self.custom_theme_enabled = self.settings_manager.get("custom_theme_enabled", False)
        self.keybinds = self.settings_manager.get("keybinds", {})

        # Keybind state
        self.capturing_for_control = None

        # Initialize the automation manager
        self.automation_manager = AutomationManager(self)

        # Initialize the floating status overlay
        self.status_overlay = OverlayStatus()

        # --- Setup Persistent Chat Worker ---
        self.setup_chat_worker()

        # Initialize media player for custom sounds
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(700, 800)

        self.setWindowTitle("Hellfire Helper")
        self.apply_loaded_settings() # Load settings before creating UI elements that depend on them

        # Center the window on the primary screen
        screen = QApplication.primaryScreen()
        if screen:
            center_point = screen.geometry().center()
            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(center_point)
            self.move(frame_geometry.topLeft())

        self.themes = [
            {"name": "Black/Orange", "style": DARK_STYLE, "preview_color": "#FF7F50", "is_dark": True},
            {"name": "White/Pink", "style": LIGHT_STYLE, "preview_color": "#FFC0CB", "is_dark": False},
            {"name": "Black/Blue", "style": FOREST_STYLE, "preview_color": "#1E90FF", "is_dark": True},
            {"name": "White/Blue", "style": OCEAN_STYLE, "preview_color": "#87CEEB", "is_dark": False},
        ]

        self.is_fetching_lobbies = False # Add a flag to prevent concurrent refreshes
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)
        main_widget = QWidget()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Title bar
        self.title_bar = QWidget()
        self.title_bar.setObjectName("CustomTitleBar")
        self.title_bar.setFixedHeight(30)
        title_bar_layout = QGridLayout(self.title_bar)
        title_bar_layout.setContentsMargins(5, 0, 5, 0)
        title_bar_layout.setSpacing(0)

        title_label = QLabel("<span style='color: #FF7F50;'>🔥</span> Hellfire Helper")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_button = QPushButton("_"); min_button.setFixedSize(30, 30); min_button.clicked.connect(self.showMinimized)
        close_button = QPushButton("X"); close_button.setFixedSize(30, 30); close_button.clicked.connect(self.close)

        # Create a separate layout for the buttons (only minimize and close)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        button_layout.addWidget(min_button)
        button_layout.addWidget(close_button)

        title_bar_layout.addWidget(title_label, 0, 0, 1, 1, Qt.AlignmentFlag.AlignCenter) # Title centered
        title_bar_layout.addLayout(button_layout, 0, 0, 1, 1, Qt.AlignmentFlag.AlignRight) # Buttons right-aligned
        main_layout.addWidget(self.title_bar)

        # Tabs
        self.tab_names = ["Load", "Items", "Placeholder", "Automation", "Quickcast(NYI)", "Lobbies", "Settings", "Reset"]
        self.custom_tab_bar = CustomTabBar(self.tab_names, tabs_per_row=4)
        main_layout.addWidget(self.custom_tab_bar)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        self.custom_tab_bar.tab_selected.connect(self.stacked_widget.setCurrentIndex)

        # Load tab
        self.load_tab = CharacterLoadTab(self)
        self.stacked_widget.addWidget(self.load_tab)

        # Connect signals from the new LoadTab
        self.load_tab.load_path_edit.textChanged.connect(self.on_path_changed)
        self.load_tab.browse_btn.clicked.connect(self.select_character_path)
        self.load_tab.reset_path_btn.clicked.connect(self.reset_character_path)
        self.load_tab.load_char_btn.clicked.connect(self.load_selected_character)
        self.load_tab.refresh_chars_btn.clicked.connect(self.load_characters)
        self.load_tab.char_list_box.currentItemChanged.connect(self.show_character_file_contents)

        # Set initial path and load characters
        self.load_tab.load_path_edit.setText(self.settings_manager.get("character_path"))
        # Items tab
        self.item_database = ItemDatabase()
        self.items_tab = ItemsTab(self)
        self.stacked_widget.addWidget(self.items_tab)

        # Connect signals from the new ItemsTab
        self.items_tab.search_box.textChanged.connect(self.on_item_search_changed)
        for i, btn in self.items_tab.item_tab_buttons.items():
            btn.clicked.connect(lambda checked, idx=i: self.switch_items_sub_tab(idx))

        # Set initial state for the items tab
        self.switch_items_sub_tab(0)

        # Placeholder Tab
        placeholder_tab = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_tab)
        placeholder_label = QLabel("This is a placeholder tab.")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        self.stacked_widget.addWidget(placeholder_tab)

        # Recipes tab
        self.in_progress_recipes = {}

        # Connect signals from the new RecipeTrackerTab
        self.items_tab.add_recipe_btn.clicked.connect(self.add_recipe_to_progress) # type: ignore
        self.items_tab.remove_recipe_btn.clicked.connect(self.remove_recipe_from_progress) # type: ignore
        self.items_tab.reset_recipes_btn.clicked.connect(self.reset_recipes) # type: ignore
        self.items_tab.in_progress_recipes_list.itemChanged.connect(self.on_recipe_check_changed) # type: ignore
        self.items_tab.materials_table.itemChanged.connect(self.on_material_checked) # type: ignore

        # Automation tab
        self.automation_tab = AutomationTab(self)
        self.stacked_widget.addWidget(self.automation_tab)

        # Connect signals from the new AutomationTab
        self.automation_tab.start_automation_btn.clicked.connect(self.automation_manager.start_automation)
        self.automation_tab.stop_automation_btn.clicked.connect(self.automation_manager.stop_automation)
        self.automation_tab.reset_automation_btn.clicked.connect(self.reset_automation_settings)
        self.automation_tab.hotkey_capture_btn.clicked.connect(self.capture_message_hotkey)
        self.automation_tab.add_msg_btn.clicked.connect(self.add_message_hotkey)
        self.automation_tab.delete_msg_btn.clicked.connect(self.delete_message_hotkey)
        self.automation_manager.log_message.connect(self.update_automation_log)

        # Add validators to the line edits in the new tab
        int_validator = QIntValidator(50, 600000, self)
        for ctrls in self.automation_tab.automation_key_ctrls.values():
            ctrls["edit"].setValidator(int_validator)
        self.automation_tab.custom_action_edit1.setValidator(int_validator)

        # Apply loaded automation settings after UI is created
        self.apply_automation_settings()

        # Quickcast tab
        self.quickcast_tab = QuickcastTab(self)
        self.stacked_widget.addWidget(self.quickcast_tab)

        # Connect signals for the new QuickcastTab
        for name, button in self.quickcast_tab.key_buttons.items():
            button.clicked.connect(lambda checked, b=button, n=name: self.on_keybind_button_clicked(b, n))
            button.installEventFilter(self) # For right-click
        for name, checkbox in self.quickcast_tab.setting_checkboxes.items():
            checkbox.clicked.connect(lambda checked, n=name: self.on_keybind_setting_changed(n))

        # Lobbies tab
        self.lobbies_tab = LobbiesTab(self)
        self.stacked_widget.addWidget(self.lobbies_tab)

        # Connect signals for the new LobbiesTab
        self.lobbies_tab.lobby_search_bar.textChanged.connect(self.filter_lobbies)
        self.lobbies_tab.refresh_button.clicked.connect(self.refresh_lobbies)
        self.lobbies_tab.toggle_watchlist_btn.clicked.connect(self.toggle_watchlist_visibility)
        self.lobbies_tab.add_watchlist_button.clicked.connect(self.add_to_watchlist)
        self.lobbies_tab.remove_watchlist_button.clicked.connect(self.remove_from_watchlist)

        # Connect sound and volume controls from LobbiesTab
        for sound, btn in self.lobbies_tab.ping_buttons.items():
            btn.clicked.connect(lambda checked=False, s=sound: self.select_ping_sound(s))
        self.lobbies_tab.test_sound_button.clicked.connect(self.play_notification_sound)
        self.lobbies_tab.volume_slider.valueChanged.connect(self.set_volume)

        # Populate initial watchlist
        self.lobbies_tab.watchlist_widget.addItems(self.watchlist)

        # Settings tab (themes + custom theme picker)
        settings_tab_content = QWidget()
        settings_layout = QGridLayout(settings_tab_content)

        # Preset themes grid
        self.create_theme_grid(settings_layout)

        # Custom theme controls below presets
        row_below = (len(self.themes) - 1) // 4 + 1
        custom_box = QGroupBox("Custom theme")
        custom_v_layout = QVBoxLayout(custom_box)

        self.bg_color_btn = QPushButton("Background")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color('bg'))
        self.fg_color_btn = QPushButton("Text")
        self.fg_color_btn.clicked.connect(lambda: self.pick_color('fg'))
        self.accent_color_btn = QPushButton("Accent")
        self.accent_color_btn.clicked.connect(lambda: self.pick_color('accent'))

        pick_buttons_h_layout = QHBoxLayout()
        pick_buttons_h_layout.addWidget(self.bg_color_btn)
        pick_buttons_h_layout.addWidget(self.fg_color_btn)
        pick_buttons_h_layout.addWidget(self.accent_color_btn)

        # Create a live preview widget for the custom theme
        self.custom_theme_preview = QWidget()
        self.custom_theme_preview.setObjectName("CustomThemePreview")
        preview_layout = QVBoxLayout(self.custom_theme_preview)
        self.preview_label = QLabel("Sample Text")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_button = QPushButton("Accent Button")
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.preview_button)

        self.apply_custom_btn = QPushButton("Apply")
        self.apply_custom_btn.clicked.connect(self.apply_custom_theme)
        self.reset_custom_btn = QPushButton("Reset custom")
        self.reset_custom_btn.clicked.connect(self.reset_custom_theme_to_defaults)

        action_buttons_h_layout = QHBoxLayout()
        action_buttons_h_layout.addWidget(self.apply_custom_btn)
        action_buttons_h_layout.addWidget(self.reset_custom_btn)

        custom_v_layout.addLayout(pick_buttons_h_layout)
        custom_v_layout.addWidget(self.custom_theme_preview)
        custom_v_layout.addStretch()
        custom_v_layout.addLayout(action_buttons_h_layout)

        settings_layout.addWidget(custom_box, row_below + 1, 0, 1, 4)

        self.stacked_widget.addWidget(settings_tab_content)

        # Reset tab
        reset_tab_content = QWidget()
        self.reset_layout = QVBoxLayout(reset_tab_content)
        warning_text = QLabel("This will reset the GUI to its default state.\nAre you sure you want to continue?")
        warning_text.setStyleSheet("font-weight: bold;")
        self.reset_layout.addWidget(warning_text, 0, Qt.AlignmentFlag.AlignCenter)
        reset_button = QPushButton("Reset GUI"); reset_button.clicked.connect(self.confirm_reset)
        self.reset_layout.addWidget(reset_button, 0, Qt.AlignmentFlag.AlignCenter)
        self.reset_layout.addStretch()
        self.stacked_widget.addWidget(reset_tab_content)

        # Finalize
        self.custom_tab_bar.tab_selected.connect(self.on_main_tab_selected)

        # Connect the thread-safe signal to the automation toggle slot
        self.start_automation_signal.connect(self.automation_manager.start_automation)
        self.stop_automation_signal.connect(self.automation_manager.stop_automation)
        self.load_character_signal.connect(self.on_f3_pressed)
        self.automation_manager.status_changed.connect(self.status_overlay.show_status)

        # Set initial values from loaded settings
        self.lobbies_tab.lobby_placeholder_checkbox.setChecked(self.play_sound_on_found)
        self.lobbies_tab.volume_slider.setValue(self.volume)

        # Set initial selected ping sound
        self.update_ping_button_styles()

        # Apply loaded keybinds
        self.apply_keybind_settings()


        # Apply preset or custom theme depending on the flag
        self.custom_tab_bar._on_button_clicked(self.last_tab_index)
        self.refresh_lobbies()
        self.load_characters() # Load characters on startup
        self.refresh_timer = QTimer(self); self.refresh_timer.setInterval(15000); self.refresh_timer.timeout.connect(self.check_for_lobby_updates); self.refresh_timer.start()
        
        # Load saved recipes after the UI is fully initialized
        self.item_database.load_recipes()
        self.apply_saved_recipes() # This call is now safe

        # Register global hotkeys (F5 for automation, etc.)
        self.register_global_hotkeys()

        # Apply theme last to ensure all widgets are styled correctly on startup
        # A theme index of -1 indicates a custom theme was last used.
        if self.current_theme_index == -1:
            # Apply custom theme and update its preview
            self.apply_custom_theme()
            self.update_custom_theme_preview()
        else:
            self.apply_theme(self.current_theme_index)

    def update_automation_log(self, message: str):
        """Appends a message to the automation log text box."""
        self.automation_tab.automation_log_box.append(message)

    def set_volume(self, value: int):
        """Sets the media player volume from the slider (0-100)."""
        self.volume = value
        volume_float = value / 100.0
        self.audio_output.setVolume(volume_float)

    # Core helpers
    def create_theme_grid(self, layout: QGridLayout):
        row, col = 0, 0
        for i, theme in enumerate(self.themes):
            preview = ThemePreview(); preview.setFixedSize(150, 120)
            preview.setCursor(Qt.CursorShape.PointingHandCursor); preview.setObjectName("ThemePreview")
            preview.clicked.connect(lambda idx=i: self.apply_theme(idx))
            preview_layout = QVBoxLayout(preview)
            color_block = QLabel(); color_block.setFixedHeight(80)
            color_block.setStyleSheet(f"background-color: {theme['preview_color']}; border-radius: 5px;")
            name_label = QLabel(theme['name']); name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(color_block); preview_layout.addWidget(name_label)
            layout.addWidget(preview, row, col); self.theme_previews.append(preview)
            col += 1
            if col >= 4:
                col = 0
                row += 1
        layout.setRowStretch(row + 1, 1); layout.setColumnStretch(col + 1, 1)

    def select_ping_sound(self, sound_file: str):
        """Selects a sound, plays it, and updates button styles."""
        self.selected_sound = sound_file
        self.play_specific_sound(sound_file)
        self.update_ping_button_styles()

    def update_ping_button_styles(self):
        """Updates the visual state of the ping buttons."""
        theme = self.themes[self.current_theme_index] if self.current_theme_index != -1 else self.custom_theme
        accent_color = theme.get("accent", theme.get("preview_color", "#FF7F50"))
        is_dark = theme.get("is_dark", self.dark_mode)
        checked_fg = "#000000" if not is_dark else "#FFFFFF"
        if self.current_theme_index == -1: checked_fg = self.custom_theme.get("bg", "#121212")

        for sound, btn in self.lobbies_tab.ping_buttons.items():
            btn.setChecked(sound == self.selected_sound)
            if sound == self.selected_sound:
                btn.setStyleSheet(f"background-color: {accent_color}; color: {checked_fg}; border: 1px solid {accent_color};")
            else:
                btn.setStyleSheet("") # Revert to parent stylesheet

    # Title bar dragging
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.underMouse():
            self.old_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.old_pos is not None and event.buttons() == Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
    def mouseReleaseEvent(self, event: QMouseEvent):
        self.old_pos = None

    def eventFilter(self, obj, event):
        """Catch right-clicks on keybind buttons."""
        if event.type() == QMouseEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
            for name, button in self.quickcast_tab.key_buttons.items():
                if button is obj:
                    if name.startswith("spell_") or name.startswith("inv_"):
                        self.toggle_quickcast(name)
                        return True # Event handled
        return super().eventFilter(obj, event)




    # Preset themes
    def apply_theme(self, theme_index: int):
        self.current_theme_index = theme_index
        theme = self.themes[theme_index]

        self.dark_mode = theme["is_dark"]
        self.setStyleSheet(theme["style"])
        self.custom_tab_bar.apply_style(theme['name'], self.dark_mode)
        for i, preview in enumerate(self.theme_previews): # type: ignore
            border_style = "border: 2px solid #FF7F50;" if i == theme_index else "border: 2px solid transparent;" # type: ignore
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.dark_mode else '#D8DEE9'}; }}") # type: ignore
        self.update_ping_button_styles()

    # Custom theme builder
    def build_custom_stylesheet(self) -> str:
        bg = self.custom_theme["bg"]
        fg = self.custom_theme["fg"]
        accent = self.custom_theme["accent"]
        return f"""QWidget {{
    background-color: {bg};
    color: {fg};
    font-family: 'Segoe UI';
    font-size: 14px;
    outline: none;
}}

QMainWindow {{
    background-color: {bg};
}}
#CustomTitleBar {{
    background-color: {bg};
}}
#CustomTitleBar QLabel, #CustomTitleBar QPushButton {{
    background-color: transparent;
    border: none;
    color: {fg};
    font-size: 16px;
}}
#CustomTitleBar QPushButton:hover {{
    background-color: {accent};
}}
QPushButton {{
    background-color: {accent};
    color: {bg};
    border: 1px solid {accent};
    padding: 5px;
    border-radius: 6px;
}}
QPushButton:hover {{
    background-color: {bg};
    color: {accent};
}}
QLineEdit, QTextEdit, QListWidget, QTableWidget {{
    background-color: #2E2E2E;
    color: {fg};
    border: 1px solid {accent};
    border-radius: 6px;
    padding: 6px;
}}
QGroupBox {{
    border: 1px solid {accent};
    border-radius: 8px;
    margin-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 10px;
    font-weight: bold;
}}
QHeaderView::section {{
    background-color: #2E2E2E;
    color: {fg};
    border: 1px solid {accent};
    padding: 4px;
}}
QCheckBox::indicator {{
    border: 1px solid {accent};
}}
"""

    def apply_custom_theme(self):
        # Set current_theme_index to -1 to signify that a custom theme is active
        self.current_theme_index = -1
        
        # Determine if the custom theme is dark or light based on background color
        bg_color = QColor(self.custom_theme.get("bg", "#121212"))
        self.dark_mode = bg_color.lightness() < 128

        self.setStyleSheet(self.build_custom_stylesheet())
        self.custom_tab_bar.setStyleSheet(f"""            
            QPushButton {{
                background-color: {self.custom_theme['bg']};
                border: 1px solid {self.custom_theme['fg']};
                padding: 8px;
                border-radius: 6px;
                color: {self.custom_theme['fg']};
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {self.custom_theme['accent']};
            }}
            QPushButton:checked {{
                background-color: {self.custom_theme['accent']};
                color: {self.custom_theme['bg']};
                border-color: {self.custom_theme['accent']};
            }}
        """)
        # Re-apply theme to ensure all child widgets get the new style
        for i, preview in enumerate(self.theme_previews):
            border_style = "border: 2px solid transparent;"
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.dark_mode else '#D8DEE9'}; }}")
        
        # Update the live preview for the custom theme
        bg, fg, accent = self.custom_theme['bg'], self.custom_theme['fg'], self.custom_theme['accent']
        self.custom_theme_preview.setStyleSheet(f"#CustomThemePreview {{ background-color: {bg}; border: 1px solid {accent}; border-radius: 8px; }}")
        self.preview_label.setStyleSheet(f"color: {fg}; background-color: transparent; border: none;")
        self.preview_button.setStyleSheet(f"background-color: {accent}; color: {bg}; border: 1px solid {accent}; padding: 5px; border-radius: 6px;")

        self.update_ping_button_styles()

    def update_custom_theme_preview(self):
        """Updates only the live preview widget with the current custom theme colors."""
        bg = self.custom_theme.get('bg', '#121212')
        fg = self.custom_theme.get('fg', '#F0F0F0')
        accent = self.custom_theme.get('accent', '#FF7F50')
        
        self.custom_theme_preview.setStyleSheet(f"#CustomThemePreview {{ background-color: {bg}; border: 1px solid {accent}; border-radius: 8px; }}")
        self.preview_label.setStyleSheet(f"color: {fg}; background-color: transparent; border: none;")
        self.preview_button.setStyleSheet(f"background-color: {accent}; color: {bg}; border: 1px solid {accent}; padding: 5px; border-radius: 6px;")

    def pick_color(self, key: str):
        initial = QColor(self.custom_theme[key])
        color = QColorDialog.getColor(initial, self, f"Pick {key} color")
        if color.isValid():
            self.custom_theme[key] = color.name()
            self.update_custom_theme_preview()


    def reset_custom_theme_to_defaults(self):
        """Resets custom theme colors to their default values."""
        self.custom_theme = {
            "bg": "#121212",
            "fg": "#F0F0F0",
            "accent": "#FF7F50"
        }
        self.apply_custom_theme()

    def confirm_reset(self):
        confirm_box = QMessageBox(self); confirm_box.setWindowTitle("Confirm Reset")
        confirm_box.setText("Are you sure you want to reset the application?\nAll settings will be returned to their defaults.")
        confirm_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_box.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm_box.exec() == QMessageBox.StandardButton.Yes:
            self.reset_state()

    def reset_state(self):
        self.resize(700, 800)
        self.custom_theme = {"bg": "#121212", "fg": "#F0F0F0", "accent": "#FF7F50"}
        self.apply_theme(0)
        self.custom_tab_bar._on_button_clicked(0)
        self.watchlist = ["hellfire", "rpg"]
        self.lobbies_tab.watchlist_widget.clear(); self.lobbies_tab.watchlist_widget.addItems(self.watchlist) # type: ignore
        self.lobbies_tab.volume_slider.setValue(100)
        
        # Also reset recipes and automation settings
        self.in_progress_recipes.clear()
        self.items_tab.in_progress_recipes_list.clear() # type: ignore
        self._rebuild_materials_table() # type: ignore
        self._reset_automation_ui()

        # Reset message hotkeys
        self.message_hotkeys.clear()
        self.load_message_hotkeys() # This will clear the table
        self.register_global_hotkeys() # This will unhook old and register new (just F5)

    # Settings
    def capture_message_hotkey(self):
        """
        Starts a worker thread to capture a key combination, ensuring only one
        capture operation can run at a time.
        """
        # Prevent starting a new capture if one is already in progress.
        if self.is_capturing_hotkey:
            return
            
        # If a previous thread is still cleaning up, do not start a new one.
        if hasattr(self, 'capture_thread') and self.capture_thread and self.capture_thread.isRunning():
            print("[DEBUG] Hotkey capture aborted: previous capture thread still running.")
            return

        self.is_capturing_hotkey = True
        # Properly clean up any previous capture thread that might exist
        if hasattr(self, 'capture_thread') and self.capture_thread and self.capture_thread.isRunning():
            self.capture_thread.quit()
            self.capture_thread.wait()


        self.automation_tab.message_edit.setEnabled(False)
        self.automation_tab.hotkey_capture_btn.setText("[Press a key...]")
        self.automation_tab.hotkey_capture_btn.setEnabled(False)

        # Unhook all main hotkeys before starting the capture thread.
        keyboard.unhook_all()
        
        # Create and start a new thread and worker for this capture
        # These will be instance attributes to manage their lifecycle correctly
        self.capture_thread = QThread() 
        self.capture_worker = HotkeyCaptureWorker()
        self.capture_worker.moveToThread(self.capture_thread)

        # Connections
        self.capture_worker.hotkey_captured.connect(self.on_hotkey_captured)
        self.capture_thread.started.connect(self.capture_worker.run)
        
        # When the worker emits the hotkey, it's done. Quit the thread.
        self.capture_worker.hotkey_captured.connect(self.capture_thread.quit)

        # When the thread finishes, schedule both for deletion and clear references.
        self.capture_thread.finished.connect(self.on_capture_thread_finished)
        self.capture_thread.finished.connect(self.capture_worker.deleteLater)
        self.capture_thread.finished.connect(self.capture_thread.deleteLater)

        self.capture_thread.start()

    def on_hotkey_captured(self, hotkey: str):
        """Handles the captured hotkey string from the worker."""
        is_valid = hotkey != 'esc'
        
        # Update UI
        self.automation_tab.message_edit.setEnabled(True)
        self.automation_tab.hotkey_capture_btn.setEnabled(True)
        self.automation_tab.hotkey_capture_btn.setText(hotkey if is_valid and hotkey != 'esc' else "Click to set")

        # Re-register all application hotkeys now that capture is complete.
        # The keyboard library's internal state is now clean.
        keyboard.unhook_all()
        self.register_global_hotkeys()
        self.register_keybind_hotkeys() # Also re-register keybinds

        # If we were capturing for a keybind button, update it
        if self.capturing_for_control:
            button = self.quickcast_tab.key_buttons[self.capturing_for_control]
            button.setChecked(False) # Uncheck to remove capture highlight
            if is_valid:
                button.setText(hotkey.upper())
                if self.capturing_for_control not in self.keybinds:
                    self.keybinds[self.capturing_for_control] = {}
                self.keybinds[self.capturing_for_control]["hotkey"] = hotkey
            else: # Capture was cancelled
                button.setText(self.keybinds.get(self.capturing_for_control, {}).get("hotkey", "SET").upper())

        # Allow a new capture to be started. This is the crucial step.
        self.is_capturing_hotkey = False

    def on_capture_thread_finished(self):
        """Clears references to the hotkey capture thread and worker."""
        self.capture_thread = None
        self.capture_worker = None
        self.capturing_for_control = None # Clear the control reference

    def setup_chat_worker(self):
        """Creates and configures the persistent worker for sending chat messages."""
        print("[DEBUG] Setting up persistent chat worker...")
        self.chat_thread = QThread()
        self.chat_worker = ChatMessageWorker(self.game_title)
        self.chat_worker.moveToThread(self.chat_thread)

        # Connect signals
        self.send_message_signal.connect(self.chat_worker.sendMessage)
        self.chat_worker.finished.connect(self.on_chat_send_finished)
        self.chat_worker.error.connect(self.on_chat_send_error)

        # Clean up thread when application closes
        self.chat_thread.finished.connect(self.chat_worker.deleteLater)
        self.chat_thread.finished.connect(self.chat_thread.deleteLater)

        self.chat_thread.start()
        print(f"[DEBUG] Persistent Chat Thread (id: {id(self.chat_thread)}) started.")

    def load_message_hotkeys(self):
        """Populates the hotkey table from the loaded settings."""
        table = self.automation_tab.msg_hotkey_table
        table.setRowCount(0)
        if not isinstance(self.message_hotkeys, dict):
            self.message_hotkeys = {}
        for hotkey, message in self.message_hotkeys.items():
            row_position = table.rowCount()
            table.insertRow(row_position)
            table.setItem(row_position, 0, QTableWidgetItem(hotkey))
            table.setItem(row_position, 1, QTableWidgetItem(message))

    def add_message_hotkey(self):
        """Adds a new hotkey and message to the system."""
        hotkey = self.automation_tab.hotkey_capture_btn.text()
        message = self.automation_tab.message_edit.text()

        if hotkey == "Click to set" or not message or hotkey == 'esc':
            QMessageBox.warning(self, "Input Error", "Please set a hotkey and enter a message.")
            return
        
        if hotkey in self.message_hotkeys:
            QMessageBox.warning(self, "Duplicate Hotkey", "This hotkey is already in use. Delete the old one first.")
            return

        # Overwrite if exists, add if new.
        self.message_hotkeys[hotkey] = message

        # Reload the table and re-register all hotkeys
        self.load_message_hotkeys()
        self.register_global_hotkeys()

        # Reset UI for next entry
        self.automation_tab.hotkey_capture_btn.setText("Click to set")
        self.automation_tab.message_edit.clear()

    def delete_message_hotkey(self):
        """Deletes a selected hotkey."""
        table = self.automation_tab.msg_hotkey_table
        selected_items = table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Error", "Please select a hotkey from the list to delete.")
            return

        selected_row = selected_items[0].row()
        hotkey_to_delete = table.item(selected_row, 0).text()

        confirm = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete the hotkey '{hotkey_to_delete}'?")
        if confirm == QMessageBox.StandardButton.Yes:
            self.message_hotkeys.pop(hotkey_to_delete, None)
            table.removeRow(selected_row)
            self.register_global_hotkeys() # Re-register to remove the deleted one

            # Reset UI
            self.automation_tab.hotkey_capture_btn.setText("Click to set"); self.automation_tab.message_edit.clear()

    def send_chat_message(self, hotkey_pressed: str, message: str):
        """Sends a chat message if the game is active, otherwise passes the keypress through."""
        print(f"[DEBUG] send_chat_message triggered for hotkey: '{hotkey_pressed}'")
        if not win32gui:
            return
        try:
            game_hwnd = win32gui.FindWindow(None, self.game_title)
            is_game_active = (win32gui.GetForegroundWindow() == game_hwnd)
        except Exception:
            is_game_active = False

        if not is_game_active:
            print(f"[DEBUG] Game not active. Simulating original keypress for '{hotkey_pressed}'.")
            try: keyboard.send(hotkey_pressed)
            except Exception: pass # type: ignore
            return # type: ignore

        if self.is_sending_message:
            print("[DEBUG] Message sending is already in progress. Ignoring new request.")
            return
        self.is_sending_message = True
        print(f"[DEBUG] is_sending_message -> True. Emitting signal to worker with message: '{message}'")
        self.send_message_signal.emit(message)

    def on_chat_send_error(self, error_message: str):
        """Handles errors from the chat message worker."""
        print(f"[DEBUG] on_chat_send_error called. Error: {error_message}. Resetting flag.")
        QMessageBox.critical(self, "Chat Error", f"Failed to send message: {error_message}")
        self.is_sending_message = False
        print("[DEBUG] is_sending_message reset to False.")

    def on_chat_send_finished(self):
        """Handles successful completion from the chat message worker."""
        print("[DEBUG] on_chat_send_finished called. Resetting flag.")
        self.is_sending_message = False
        print("[DEBUG] is_sending_message reset to False.")

    def apply_loaded_settings(self):
        """Applies settings from the SettingsManager to the application state."""
        self.current_theme_index = self.settings_manager.get("theme_index")
        self.last_tab_index = self.settings_manager.get("last_tab_index")
        self.character_path = self.settings_manager.get("character_path")
        if not self.character_path:
             self.character_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
        self.message_hotkeys = self.settings_manager.get("message_hotkeys")
        self.automation_settings = self.settings_manager.get("automation")
        self.custom_theme = self.settings_manager.get("custom_theme")
        self.watchlist = self.settings_manager.get("watchlist")
        self.play_sound_on_found = self.settings_manager.get("play_sound_on_found")
        self.selected_sound = self.settings_manager.get("selected_sound")
        self.volume = self.settings_manager.get("volume", 100)
        self.keybinds = self.settings_manager.get("keybinds", {})

    def apply_automation_settings(self):
        """Applies loaded automation settings to the UI controls."""
        if not self.automation_settings:
            return

        key_settings = self.automation_settings.get("keys", {})
        for key, settings in key_settings.items():
            if key in self.automation_tab.automation_key_ctrls:
                self.automation_tab.automation_key_ctrls[key]["chk"].setChecked(settings.get("checked", False))
                self.automation_tab.automation_key_ctrls[key]["edit"].setText(settings.get("interval", "500"))

        custom_settings = self.automation_settings.get("custom", {})
        if custom_settings:
            self.automation_tab.custom_action_btn.setChecked(custom_settings.get("checked", False))
            self.automation_tab.custom_action_edit1.setText(custom_settings.get("interval", "30000"))
            self.automation_tab.custom_action_edit2.setText(custom_settings.get("message", "-save x"))

    def get_automation_settings_from_ui(self):
        """Gathers automation settings from the UI controls."""
        return {
            "keys": {
                key: {"checked": ctrls["chk"].isChecked(), "interval": ctrls["edit"].text()}
                for key, ctrls in self.automation_tab.automation_key_ctrls.items()
            },
            "custom": {
                "checked": self.automation_tab.custom_action_btn.isChecked(),
                "interval": self.automation_tab.custom_action_edit1.text(),
                "message": self.automation_tab.custom_action_edit2.text()
            }
        }

    # Keybinds / Quickcast
    def apply_keybind_settings(self):
        """Applies loaded keybind settings to the UI and registers hotkeys."""
        # Set checkbox states
        for name, checkbox in self.quickcast_tab.setting_checkboxes.items():
            is_enabled = self.keybinds.get("settings", {}).get(name, True)
            checkbox.setChecked(is_enabled)

        # Set button text and styles
        for name, button in self.quickcast_tab.key_buttons.items():
            key_info = self.keybinds.get(name, {})
            hotkey = key_info.get("hotkey", button.text())
            quickcast = key_info.get("quickcast", False)

            button.setText(hotkey.upper())
            self.update_keybind_style(button, quickcast)

        self.register_keybind_hotkeys()

    def on_keybind_button_clicked(self, button: QPushButton, name: str):
        """Handles left-click on a keybind button to start capture."""
        if self.is_capturing_hotkey:
            return

        self.capturing_for_control = name
        button.setText("...")
        button.setChecked(True) # Use checked state to indicate capture
        self.capture_message_hotkey() # Reuse the hotkey capture logic

    def on_keybind_setting_changed(self, setting_name: str):
        """Handles when a keybind setting checkbox is changed."""
        if "settings" not in self.keybinds:
            self.keybinds["settings"] = {}
        
        is_enabled = self.quickcast_tab.setting_checkboxes[setting_name].isChecked()
        self.keybinds["settings"][setting_name] = is_enabled
        self.register_keybind_hotkeys()

    def toggle_quickcast(self, name: str):
        """Toggles quickcast for a given keybind."""
        if name not in self.keybinds:
            self.keybinds[name] = {}

        current_qc = self.keybinds[name].get("quickcast", False)
        self.keybinds[name]["quickcast"] = not current_qc

        button = self.quickcast_tab.key_buttons[name]
        self.update_keybind_style(button, not current_qc)
        self.register_keybind_hotkeys()

    def update_keybind_style(self, button: QPushButton, quickcast: bool):
        """Updates the font color of a button based on quickcast state."""
        if quickcast:
            button.setStyleSheet("color: green;")
        else:
            button.setStyleSheet("") # Revert to default stylesheet color

    def execute_keybind(self, name: str):
        """Executes the action for a triggered keybind hotkey."""
        key_info = self.keybinds.get(name, {})
        if not key_info: return

        # Check if the corresponding setting is enabled
        category = name.split("_")[0] # "spell", "inv", "mouse"
        if category == "inv": category = "inventory"
        
        is_enabled = self.keybinds.get("settings", {}).get(category, True)
        if not is_enabled:
            return

        # Find game window
        hwnd = win32gui.FindWindow(None, self.game_title) if win32gui else 0
        if hwnd == 0 or win32gui.GetForegroundWindow() != hwnd:
            return # Only run if game is active

        quickcast = key_info.get("quickcast", False)
        
        # Determine original key
        original_key = ""
        if name.startswith("spell_"):
            original_key = name.split("_")[1].lower()
        elif name.startswith("inv_"):
            # Map 1-6 to Numpad 7,8,4,5,1,2
            inv_map = ["numpad7", "numpad8", "numpad4", "numpad5", "numpad1", "numpad2"]
            inv_index = int(name.split("_")[1]) - 1
            original_key = inv_map[inv_index]
        elif name.startswith("mouse_"):
            original_key = name.split("_")[1].lower()

        if not original_key: return

        if name.startswith("mouse_"):
            pyautogui.click(button=original_key)
        elif quickcast:
            # The quickcast macro from the AHK script
            pyautogui.keyDown('ctrl'); pyautogui.press('9'); pyautogui.press('0'); pyautogui.keyUp('ctrl')
            pyautogui.press(original_key)
            pyautogui.click()
            pyautogui.press('9'); pyautogui.press('0')
        else:
            # Normal remap
            pyautogui.press(original_key)

    def get_keybind_settings_from_ui(self):
        """Gathers keybind settings from the UI controls for saving."""
        # This is now handled by directly modifying self.keybinds,
        # so this function just returns the current state.
        # We ensure the hotkey text is up-to-date.
        for name, button in self.quickcast_tab.key_buttons.items():
            if name not in self.keybinds:
                self.keybinds[name] = {}
            self.keybinds[name]["hotkey"] = button.text().lower()

        return self.keybinds


    def apply_saved_recipes(self):
        """Loads and populates the in-progress recipes from settings."""
        saved_recipes = self.settings_manager.get("in_progress_recipes", [])
        for recipe_name in saved_recipes:
            self._add_recipe_by_name(recipe_name)

    # Watchlist
    def load_watchlist(self):
        """Loads the watchlist from settings. This is now handled by apply_loaded_settings().""" # type: ignore
        # This method is kept for compatibility but logic is in load_settings()
        # The watchlist is loaded with other settings at startup.
        self.lobbies_tab.watchlist_widget.clear() # type: ignore
        self.lobbies_tab.watchlist_widget.addItems(self.watchlist) # type: ignore
    def add_to_watchlist(self):
        keyword = self.lobbies_tab.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.lobbies_tab.watchlist_widget.addItem(keyword)
            self.lobbies_tab.watchlist_input.clear()
            self.filter_lobbies(self.lobbies_tab.lobby_search_bar.text())
    def remove_from_watchlist(self):
        selected_items = self.lobbies_tab.watchlist_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.lobbies_tab.watchlist_widget.takeItem(self.lobbies_tab.watchlist_widget.row(item))
        self.filter_lobbies(self.lobbies_tab.lobby_search_bar.text())

    # Items
    def on_item_search_changed(self):
        """Decides which view to filter based on the active sub-tab."""
        # If the recipe tracker is visible (index 1), filter recipes.
        if self.items_tab.main_stack.currentIndex() == 1:
            self.filter_recipes_list()
        else: # Otherwise, filter the currently visible item table.
            self.filter_current_item_view()

    def filter_current_item_view(self):
        query = self.items_tab.search_box.text().lower() # type: ignore
        current_index = self.items_tab.item_tables_stack.currentIndex() # type: ignore
        data_source, table_widget = [], None # type: ignore
        if current_index == 0: data_source, table_widget = self.item_database.all_items_data, self.items_tab.all_items_table # type: ignore
        elif current_index == 1: data_source, table_widget = self.item_database.drops_data, self.items_tab.drops_table # type: ignore
        elif current_index == 2: data_source, table_widget = self.item_database.raid_data, self.items_tab.raid_items_table # type: ignore
        elif current_index == 3: data_source, table_widget = self.item_database.vendor_data, self.items_tab.vendor_table # type: ignore
        if not table_widget: return # type: ignore
        table_widget.setSortingEnabled(False); table_widget.setRowCount(0) # type: ignore
        filtered_data = [item for item in data_source if query in item.get("Item", "").lower() or # type: ignore
                         query in item.get("Unit", "").lower() or query in item.get("Location", "").lower()] # type: ignore
        headers = [table_widget.horizontalHeaderItem(i).text() for i in range(table_widget.columnCount())] # type: ignore
        for row, item_data in enumerate(filtered_data): # type: ignore
            table_widget.insertRow(row) # type: ignore
            for col, header in enumerate(headers): # type: ignore
                table_widget.setItem(row, col, QTableWidgetItem(item_data.get(header, ""))) # type: ignore
        table_widget.setSortingEnabled(True) # type: ignore

    def switch_items_sub_tab(self, index: int):
        for i, btn in self.items_tab.item_tab_buttons.items(): # type: ignore
            btn.setChecked(i == index)

        is_recipe_tab = (index == len(self.items_tab.item_tab_buttons) - 1) # type: ignore

        if is_recipe_tab:
            self.items_tab.main_stack.setCurrentIndex(1) # type: ignore
            self.items_tab.search_box.setPlaceholderText("Search...") # type: ignore
            if not self.item_database.recipes_data:
                self.item_database.load_recipes()
            self.filter_recipes_list()
            self._rebuild_materials_table()
        else:
            self.items_tab.main_stack.setCurrentIndex(0) # type: ignore
            self.items_tab.item_tables_stack.setCurrentIndex(index) # type: ignore
            self.items_tab.search_box.show() # type: ignore

            if index == 0 and not self.item_database.all_items_data:
                self.item_database.all_items_data = self.item_database._load_item_data_from_folder("All Items")
            elif index == 1 and not self.item_database.drops_data:
                self.item_database.drops_data = self.item_database._load_item_data_from_folder("Drops")
            elif index == 2 and not self.item_database.raid_data:
                self.item_database.raid_data = self.item_database._load_item_data_from_folder("Raid Items")
            elif index == 3 and not self.item_database.vendor_data:
                self.item_database.vendor_data = self.item_database._load_item_data_from_folder("Vendor Items")
            self.filter_current_item_view()

    # Recipes
    def filter_recipes_list(self):
        query = self.items_tab.search_box.text().lower() # type: ignore
        self.items_tab.available_recipes_list.clear() # type: ignore
        for recipe in self.item_database.recipes_data:
            if query in recipe["name"].lower():
                item = QListWidgetItem(recipe["name"])
                item.setData(Qt.ItemDataRole.UserRole, recipe) # type: ignore
                self.items_tab.available_recipes_list.addItem(item) # type: ignore

    def add_recipe_to_progress(self):
        """Adds a recipe to the 'in-progress' list from the UI selection."""
        selected_item = self.items_tab.available_recipes_list.currentItem() # type: ignore
        if not selected_item:
            return False
        if self._add_recipe_by_name(selected_item.text()):
            self._rebuild_materials_table()
            return True
        return False

    def _add_recipe_by_name(self, recipe_name: str):
        """Helper to add a recipe to the in-progress list by its name."""
        if recipe_name in self.in_progress_recipes:
            # Don't show a message box when loading from settings, just skip.
            # QMessageBox.information(self, "Duplicate", "This recipe is already in the 'In Progress' list.")
            return False

        # Find the full recipe object from the database
        recipe = next((r for r in self.item_database.recipes_data if r["name"] == recipe_name), None)
        if not recipe:
            return False # Recipe not found in database

        recipe_name = recipe["name"]
        self.in_progress_recipes[recipe_name] = recipe
        item = QListWidgetItem(recipe_name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable) # type: ignore
        item.setCheckState(Qt.CheckState.Unchecked)
        self.items_tab.in_progress_recipes_list.addItem(item) # type: ignore
        return True

    def remove_recipe_from_progress(self):
        selected_item = self.items_tab.in_progress_recipes_list.currentItem() # type: ignore
        if not selected_item:
            return
        recipe_name = selected_item.text()
        recipe = self.in_progress_recipes.pop(recipe_name, None)
        if recipe:
            list_widget = self.items_tab.in_progress_recipes_list # type: ignore
            list_widget.takeItem(list_widget.row(selected_item))
            self._rebuild_materials_table()

    def reset_recipes(self):
        """Clears all in-progress recipes and the materials list."""
        confirm = QMessageBox.question(self, "Confirm Reset", "Are you sure you want to clear all in-progress recipes?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.in_progress_recipes.clear()
            self.items_tab.in_progress_recipes_list.clear() # type: ignore
            self._rebuild_materials_table()

    def _reset_automation_ui(self):
        """Resets the automation UI controls to their default values without confirmation."""
        self.automation_manager.reset_settings(confirm=False)

    def _rebuild_materials_table(self):
        """Clears and repopulates the materials table based on the internal data dictionary and checked recipes."""
        # Disconnect signals to prevent loops during update
        materials_table = self.items_tab.materials_table # type: ignore
        materials_table.setSortingEnabled(False)
        try:
            materials_table.itemChanged.disconnect(self.on_material_checked)

            # Store the names of currently checked materials
            checked_materials = set()
            for row in range(materials_table.rowCount()):
                item = materials_table.item(row, 0)
                if item and item.checkState() == Qt.CheckState.Checked:
                    checked_materials.add(item.text())

        except RuntimeError: # Already disconnected
            pass
        materials_table.setRowCount(0)
        
        checked_recipe_names = []
        in_progress_list = self.items_tab.in_progress_recipes_list # type: ignore
        for i in range(in_progress_list.count()):
            item = in_progress_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_recipe_names.append(item.text())
        
        # If no recipes are checked, use all recipes in the "In Progress" list
        in_progress_list = self.items_tab.in_progress_recipes_list # type: ignore
        target_recipe_names = checked_recipe_names if checked_recipe_names else [in_progress_list.item(i).text() for i in range(in_progress_list.count())]
        
        # Calculate materials needed for the target recipes
        materials_to_display = {}
        for recipe_name in target_recipe_names:
            recipe = self.in_progress_recipes.get(recipe_name)
            if not recipe: continue
            
            for component_str in recipe["components"]:
                match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
                name, quantity = (match.group(1).strip(), int(match.group(2))) if match else (component_str.strip(), 1)
                
                if name in materials_to_display:
                    materials_to_display[name]["#"] += quantity
                else:
                    drop_info = next((item for item in self.item_database.all_items_data if item["Item"].lower() == name.lower()), None)
                    materials_to_display[name] = {"Material": name, "#": quantity, "Unit": drop_info["Unit"] if drop_info else "?", "Location": drop_info["Location"] if drop_info else "?"}
        
        # Populate the table
        for row, item_data in enumerate(materials_to_display.values()):
            materials_table.insertRow(row)
            material_item = QTableWidgetItem(item_data["Material"])
            material_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            material_item.setCheckState(Qt.CheckState.Unchecked)
            materials_table.setItem(row, 0, material_item)

            # Create non-editable items for other columns
            for col, key in enumerate(["#", "Unit", "Location"], 1):
                text = str(item_data.get(key, ""))
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                materials_table.setItem(row, col, item)

            # Hidden sort column
            sort_item = QTableWidgetItem("0")
            sort_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            materials_table.setItem(row, 4, sort_item)
        
        # Reconnect signals and enable sorting
        materials_table.itemChanged.connect(self.on_material_checked)
        materials_table.setSortingEnabled(True)

    def on_recipe_check_changed(self, item: QListWidgetItem):
        """Called when any recipe's check state changes to rebuild the material list."""
        # This handler is now connected to QListWidget.itemChanged
        self._rebuild_materials_table()

    # Character loading
    def on_path_changed(self, new_path: str):
        self.character_path = new_path # Still need to update the main window's state

    def on_material_checked(self, item: QTableWidgetItem):
        if item.column() != 0: return
        materials_table = self.items_tab.materials_table # type: ignore
        is_checked = item.checkState() == Qt.CheckState.Checked
        color = QColor("gray") if is_checked else self.palette().color(self.foregroundRole())
        materials_table.itemChanged.disconnect(self.on_material_checked)
        for col in range(materials_table.columnCount()):
            table_item = materials_table.item(item.row(), col)
            if table_item: table_item.setForeground(color)
        sort_item = materials_table.item(item.row(), 4)
        if sort_item: sort_item.setText("1" if is_checked else "0")
        materials_table.setSortingEnabled(True)
        materials_table.sortItems(4, Qt.SortOrder.AscendingOrder)
        materials_table.itemChanged.connect(self.on_material_checked)

    def select_character_path(self):
        default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData")
        new_path = QFileDialog.getExistingDirectory(self, "Select the character data folder", dir=default_path)
        if new_path:
            self.load_tab.load_path_edit.setText(new_path); self.load_characters()
    def reset_character_path(self):
        confirm_box = QMessageBox.question(self, "Confirm Reset", "Reset character path to default?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                           QMessageBox.StandardButton.No)
        if confirm_box == QMessageBox.StandardButton.Yes:
            default_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
            self.load_tab.load_path_edit.setText(default_path); self.load_characters()
    def load_characters(self):
        self.load_tab.char_list_box.clear(); self.load_tab.char_content_box.clear()
        if not self.character_path or not os.path.isdir(self.character_path):
            if self.character_path:
                QMessageBox.warning(self, "Error", f"Character save directory not found:\n{self.character_path}")
            return
        char_files = []
        for filename in os.listdir(self.character_path):
            if filename.endswith(".txt"):
                full_path = os.path.join(self.character_path, filename)
                try:
                    mod_time = os.path.getmtime(full_path)
                    char_name = os.path.splitext(filename)[0]
                    char_files.append({"name": char_name, "path": full_path, "mod_time": mod_time})
                except OSError:
                    continue
        sorted_chars = sorted(char_files, key=lambda x: x["mod_time"], reverse=True)
        for char in sorted_chars:
            item = QListWidgetItem(char["name"])
            item.setData(Qt.ItemDataRole.UserRole, char["path"])
            self.load_tab.char_list_box.addItem(item)
        if self.load_tab.char_list_box.count() > 0:
            self.load_tab.char_list_box.setCurrentRow(0)
    def show_character_file_contents(self, current_item: QListWidgetItem, previous_item: QListWidgetItem):
        if not current_item:
            self.load_tab.char_content_box.clear(); return
        file_path = current_item.data(Qt.ItemDataRole.UserRole)
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                self.load_tab.char_content_box.setText(f.read())
        except (IOError, OSError) as e:
            self.load_tab.char_content_box.setText(f"Error reading file: {e}")
    def load_selected_character(self):
        # This is now the core logic, can be called by button or hotkey handler
        if not self.load_tab.char_list_box.currentItem():
            # If nothing is selected, try to select the first item
            if self.load_tab.char_list_box.count() > 0:
                self.load_tab.char_list_box.setCurrentRow(0)
        current_item = self.load_tab.char_list_box.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Character Selected", "Please select a character from the list."); return
        char_name = current_item.text()
        try:
            hwnd = win32gui.FindWindow(None, self.game_title)
            if hwnd == 0:
                QMessageBox.critical(self, "Error", f"'{self.game_title}' window not found."); return
            win32gui.SetForegroundWindow(hwnd)
            pyautogui.press('enter'); pyautogui.write(f"-load {char_name}", interval=0.05); pyautogui.press('enter')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to send command to game: {e}")

    def on_f3_pressed(self):
        """Handler for the F3 hotkey press."""
        self.load_selected_character()
        self.showMinimized()

    def check_for_lobby_updates(self):
        """Performs a lightweight check to see if a full refresh is needed."""
        if self.is_fetching_lobbies:
            return

        self.thread = QThread()
        self.worker = LobbyHeartbeatChecker(self.last_lobby_id)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.update_required.connect(self.refresh_lobbies)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    # Lobbies
    def refresh_lobbies(self):
        if self.is_fetching_lobbies:
            return # Don't start a new refresh if one is already running
        self.is_fetching_lobbies = True
        lobbies_table = self.lobbies_tab.lobbies_table

        lobbies_table.setRowCount(0); lobbies_table.setRowCount(1)
        loading_item = QTableWidgetItem("Fetching lobby data..."); loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        lobbies_table.setItem(0, 0, loading_item); lobbies_table.setSpan(0, 0, 1, 3)
        self.thread = QThread(); self.worker = LobbyFetcher(); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_lobbies_fetched)
        self.worker.error.connect(self.on_lobbies_fetch_error)
        self.worker.finished.connect(self.thread.quit); self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater); self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
    def on_lobbies_fetched(self, lobbies: list):
        current_watched_lobbies = set()
        if lobbies: self.last_lobby_id = lobbies[0].get("id", self.last_lobby_id)
        self.is_fetching_lobbies = False # Reset the flag
        for lobby in lobbies:
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    current_watched_lobbies.add(lobby.get('name')); break
        newly_found = current_watched_lobbies - self.previous_watched_lobbies # type: ignore
        if newly_found and self.lobbies_tab.lobby_placeholder_checkbox.isChecked():
            self.play_notification_sound()
        self.previous_watched_lobbies = current_watched_lobbies
        self.all_lobbies = lobbies
        self.filter_lobbies(self.lobbies_tab.lobby_search_bar.text())
    def on_lobbies_fetch_error(self, error_message: str):
        self.is_fetching_lobbies = False # Reset the flag
        lobbies_table = self.lobbies_tab.lobbies_table
        lobbies_table.setRowCount(1)
        lobbies_table.setSpan(0, 0, 1, lobbies_table.columnCount())
        error_item = QTableWidgetItem(f"Error: {error_message}")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        lobbies_table.setItem(0, 0, error_item)
    def filter_lobbies(self, query: str):
        lobbies_table = self.lobbies_tab.lobbies_table
        lobbies_table.setRowCount(0); lobbies_table.setSortingEnabled(False)
        query = query.lower()
        filtered_lobbies = [l for l in self.all_lobbies if query in l.get('name', '').lower() or query in l.get('map', '').lower()]
        def is_watched(lobby):
            name = lobby.get('name', '').lower(); map_name = lobby.get('map', '').lower()
            return any(k in name or k in map_name for k in self.watchlist)
        sorted_lobbies = sorted(filtered_lobbies, key=is_watched, reverse=True)
        lobbies_table.setRowCount(len(sorted_lobbies))
        for row, lobby in enumerate(sorted_lobbies):
            lobby_name = lobby.get('name', '').lower(); lobby_map = lobby.get('map', '').lower()
            watched = any(k in lobby_name or k in lobby_map for k in self.watchlist)
            lobbies_table.setItem(row, 0, QTableWidgetItem(lobby.get('name', 'N/A')))
            lobbies_table.setItem(row, 1, QTableWidgetItem(lobby.get('map', 'N/A')))
            players = f"{lobby.get('slotsTaken', '?')}/{lobby.get('slotsTotal', '?')}"
            lobbies_table.setItem(row, 2, AlignedTableWidgetItem(players))
            host = lobby.get('host', lobby.get('server', 'N/A')) # Fallback to 'server' if 'host' is not present
            lobbies_table.setItem(row, 3, AlignedTableWidgetItem(host))
            if watched:
                for col in range(lobbies_table.columnCount()):
                    lobbies_table.item(row, col).setBackground(QColor("#3A5F0B"))
        lobbies_table.setSortingEnabled(True)

    def toggle_watchlist_visibility(self):
        """Shows or hides the watchlist group box."""
        is_visible = self.lobbies_tab.watchlist_group.isVisible()
        self.lobbies_tab.watchlist_group.setVisible(not is_visible)

    # Tab select logic
    def on_main_tab_selected(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        tab_name = self.tab_names[index]
        if tab_name == "Items" and not self.item_database.all_items_data:
            self.switch_items_sub_tab(0) # Lazy load
        elif tab_name == "Placeholder":
            pass # Nothing to do for the placeholder tab
        elif tab_name == "Lobbies" and not self.lobbies_tab.lobbies_table.rowCount():
            self.refresh_lobbies() # Refresh when tab is first viewed
        elif tab_name == "Automation":
            self.load_message_hotkeys()

    def _reset_automation_button_style(self):
        """Resets the automation button to its default theme color."""
        accent_color = self.custom_theme.get("accent", "#FF7F50")
        text_color = self.custom_theme.get("bg", "#121212")
        self.automation_tab.start_automation_btn.setStyleSheet(f"background-color: {accent_color}; color: {text_color};")

    def reset_automation_settings(self, confirm=True):
        """Resets all automation settings in the UI to their defaults."""
        self.automation_manager.reset_settings(confirm)

    def register_global_hotkeys(self):
        # This function will now only handle app-level hotkeys (F3, F5, F6) and message hotkeys.
        """Registers all hotkeys, including global controls and custom messages."""
        keyboard.unhook_all()
        self.hotkey_ids.clear()

        # Register global F5 for starting automation
        try:
            f5_id = keyboard.add_hotkey('f5', lambda: self.start_automation_signal.emit(), suppress=True)
            self.hotkey_ids['f5'] = f5_id
        except Exception as e:
            print(f"Failed to register F5 hotkey: {e}")

        # Register global F6 for stopping automation
        try:
            f6_id = keyboard.add_hotkey('f6', lambda: self.stop_automation_signal.emit(), suppress=True)
            self.hotkey_ids['f6'] = f6_id
        except Exception as e:
            print(f"Failed to register F6 hotkey: {e}")

        # Register global F3 for loading character
        try:
            f3_id = keyboard.add_hotkey('f3', lambda: self.load_character_signal.emit(), suppress=True)
            self.hotkey_ids['f3'] = f3_id
        except Exception as e:
            print(f"Failed to register F3 hotkey: {e}")

        # Register all custom message hotkeys
        for hotkey, message in self.message_hotkeys.items():
            self.register_single_hotkey(hotkey, message)

    def register_keybind_hotkeys(self):
        """Registers all hotkeys defined in the Quickcast tab."""
        # Unhook only the keybind hotkeys, leaving global ones intact
        for name in self.keybinds:
            if name in self.hotkey_ids:
                keyboard.remove_hotkey(self.hotkey_ids.pop(name))

        for name, key_info in self.keybinds.items():
            if "hotkey" in key_info and key_info["hotkey"]:
                self.register_single_keybind(name, key_info["hotkey"])

    def register_single_hotkey(self, hotkey: str, message: str):
        """Helper to register a single message hotkey."""
        try:
            hk_id = keyboard.add_hotkey(hotkey, lambda h=hotkey, msg=message: self.send_chat_message(h, msg), suppress=True)
            self.hotkey_ids[hotkey] = hk_id
        except (ValueError, ImportError) as e:
            print(f"Failed to register hotkey '{hotkey}': {e}")

    def register_single_keybind(self, name: str, hotkey: str):
        """Helper to register a single keybind hotkey."""
        try:
            # The 'when' lambda function ensures the hotkey only triggers when WC3 is the active window.
            is_wc3_active = lambda: win32gui.GetForegroundWindow() == win32gui.FindWindow(None, self.game_title) if win32gui else False
            
            hk_id = keyboard.add_hotkey(hotkey, lambda n=name: self.execute_keybind(n), suppress=True, when=is_wc3_active)
            self.hotkey_ids[name] = hk_id
        except (ValueError, ImportError, KeyError) as e:
            print(f"Failed to register keybind '{hotkey}' for '{name}': {e}")

    def play_specific_sound(self, sound_file: str):
        """Plays a specific sound file from the contents/sounds directory."""
        try:
            sound_file_path = os.path.join(get_base_path(), "contents", "sounds", sound_file)
            if os.path.exists(sound_file_path):
                self.player.setSource(QUrl.fromLocalFile(sound_file_path))
                self.player.play()
            else:
                print(f"Sound file not found: {sound_file_path}")
                QApplication.beep()
        except Exception as e:
            print(f"Error playing sound: {e}")
            QApplication.beep()
    
    def play_notification_sound(self):
        """Plays a custom sound file (ping.mp3), with fallback to a system beep."""
        self.play_specific_sound(self.selected_sound)

    # Ensure timers are cleaned up on exit
    def closeEvent(self, event):
        self.settings_manager.save(self) # Save all settings on exit
        self.automation_manager.stop_automation() # This was already here
        self.chat_thread.quit() # Tell the persistent chat thread to stop
        keyboard.unhook_all() # Clean up all global listeners
        event.accept()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())