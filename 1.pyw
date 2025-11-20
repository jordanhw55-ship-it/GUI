import sys
import json
import os
import re
from typing import List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QGroupBox, QFileDialog, QTextEdit,
    QListWidgetItem, QColorDialog, QCheckBox
)
from PySide6.QtCore import Signal, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QMouseEvent, QColor, QIntValidator
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import keyboard   # type: ignore
import pyautogui  # type: ignore

from utils import get_base_path, DARK_STYLE, LIGHT_STYLE, FOREST_STYLE, OCEAN_STYLE
from data import ItemDatabase
from workers import LobbyFetcher, HotkeyCaptureWorker, ChatMessageWorker
from settings import SettingsManager
from ui_tab_widgets import CharacterLoadTab, RecipeTrackerTab, AutomationTab, ItemsTab

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
    automation_toggled_signal = Signal()
    load_character_signal = Signal()

    def __init__(self):
        super().__init__()

        self.settings_manager = SettingsManager()

        # Theme state
        self.current_theme_index = self.settings_manager.get("theme_index")
        self.last_tab_index = self.settings_manager.get("last_tab_index")
        self.custom_theme_enabled = self.settings_manager.get("custom_theme_enabled")
        self.custom_theme = self.settings_manager.get("custom_theme", {
            "bg": "#121212",
            "fg": "#F0F0F0",
            "accent": "#FF7F50"
        })

        self.old_pos = None
        self.all_lobbies = []
        self.thread = None # type: ignore
        self.hotkey_ids = {}            # {hotkey_str: id from keyboard.add_hotkey}
        self.is_sending_message = False
        self.game_title = "Warcraft III"

        # Automation state flags
        self.automation_timers = {}
        self.is_automation_running = False
        self.automation_settings = {} # To hold loaded settings
        self.custom_action_running = False
        self.theme_previews = []
        self.previous_watched_lobbies = set()
        self.message_hotkeys = {}       # {hotkey_str: message_str}
        self.watchlist = ["hellfire", "rpg"] # Default, will be overwritten by load_settings
        self.play_sound_on_found = False # Default, will be overwritten by load_settings
        self.selected_sound = self.settings_manager.get("selected_sound", "ping1.mp3")

        self.setWindowTitle("Hellfire Helper")
        self.apply_loaded_settings()

        # Initialize media player for custom sounds
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(700, 800)

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
        title_bar_layout = QHBoxLayout(self.title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        left_spacer = QWidget(); left_spacer.setFixedSize(60, 30); left_spacer.setStyleSheet("background-color: transparent;")
        title_label = QLabel("<span style='color: #FF7F50;'>🔥</span> Hellfire Helper")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_button = QPushButton("_"); min_button.setFixedSize(30, 30); min_button.clicked.connect(self.showMinimized)
        close_button = QPushButton("X"); close_button.setFixedSize(30, 30); close_button.clicked.connect(self.close)
        title_bar_layout.addWidget(left_spacer); title_bar_layout.addStretch(); title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch(); title_bar_layout.addWidget(min_button); title_bar_layout.addWidget(close_button)
        main_layout.addWidget(self.title_bar)

        # Tabs
        self.tab_names = ["Load", "Items", "Recipes", "Automation", "Hotkey", "Lobbies", "Settings", "Reset"]
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
        self.items_tab.search_box.textChanged.connect(self.filter_current_item_view)
        for i, btn in self.items_tab.item_tab_buttons.items():
            btn.clicked.connect(lambda checked, idx=i: self.switch_items_sub_tab(idx))

        # Set initial state for the items tab
        self.switch_items_sub_tab(0)

        # Recipes tab
        self.in_progress_recipes = {}
        self.recipes_tab = RecipeTrackerTab(self)
        self.stacked_widget.addWidget(self.recipes_tab)

        # Connect signals from the new RecipeTrackerTab
        self.recipes_tab.recipe_search_box.textChanged.connect(self.filter_recipes_list)
        self.recipes_tab.add_recipe_btn.clicked.connect(self.add_recipe_to_progress)
        self.recipes_tab.remove_recipe_btn.clicked.connect(self.remove_recipe_from_progress)
        self.recipes_tab.reset_recipes_btn.clicked.connect(self.reset_recipes)
        self.recipes_tab.in_progress_recipes_list.itemChanged.connect(self.on_recipe_check_changed)
        self.recipes_tab.materials_table.itemChanged.connect(self.on_material_checked)

        # Automation tab
        self.automation_tab = AutomationTab(self)
        self.stacked_widget.addWidget(self.automation_tab)

        # Connect signals from the new AutomationTab
        self.automation_tab.start_automation_btn.clicked.connect(self.toggle_automation)
        self.automation_tab.reset_automation_btn.clicked.connect(self.reset_automation_settings)
        self.automation_tab.hotkey_capture_btn.clicked.connect(self.capture_message_hotkey)
        self.automation_tab.add_msg_btn.clicked.connect(self.add_message_hotkey)
        self.automation_tab.delete_msg_btn.clicked.connect(self.delete_message_hotkey)

        # Add validators to the line edits in the new tab
        int_validator = QIntValidator(50, 600000, self)
        for ctrls in self.automation_tab.automation_key_ctrls.values():
            ctrls["edit"].setValidator(int_validator)
        self.automation_tab.custom_action_edit1.setValidator(int_validator)

        # Apply loaded automation settings after UI is created
        self.apply_automation_settings()

        # Hotkey tab placeholder
        hotkey_tab_content = QWidget()
        hotkey_layout = QVBoxLayout(hotkey_tab_content)
        hotkey_layout.addWidget(QLabel("This is the 'Hotkey' tab."))
        hotkey_layout.addStretch()
        self.stacked_widget.addWidget(hotkey_tab_content)

        # Lobbies tab
        lobbies_tab_content = QWidget()
        lobbies_layout = QVBoxLayout(lobbies_tab_content)
        controls_layout = QHBoxLayout()
        self.lobby_search_bar = QLineEdit(); self.lobby_search_bar.setPlaceholderText("Search by name or map…")
        self.lobby_search_bar.textChanged.connect(self.filter_lobbies); controls_layout.addWidget(self.lobby_search_bar)
        refresh_button = QPushButton("Refresh"); refresh_button.clicked.connect(self.refresh_lobbies); controls_layout.addWidget(refresh_button)
        lobbies_layout.addLayout(controls_layout)
        watchlist_group = QGroupBox("Watchlist"); watchlist_layout = QHBoxLayout()
        self.watchlist_widget = QListWidget(); self.watchlist_widget.addItems(self.watchlist)
        watchlist_layout.addWidget(self.watchlist_widget)
        watchlist_controls_layout = QVBoxLayout()
        self.watchlist_input = QLineEdit(); self.watchlist_input.setPlaceholderText("Add keyword...")
        watchlist_controls_layout.addWidget(self.watchlist_input)
        add_watchlist_button = QPushButton("Add"); add_watchlist_button.clicked.connect(self.add_to_watchlist)
        watchlist_controls_layout.addWidget(add_watchlist_button)
        remove_watchlist_button = QPushButton("Remove"); remove_watchlist_button.clicked.connect(self.remove_from_watchlist)
        watchlist_controls_layout.addWidget(remove_watchlist_button)
        
        # Sound selection buttons
        ping_buttons_layout = QHBoxLayout()
        self.ping_buttons = {
            "ping1.mp3": QPushButton("Ping 1"),
            "ping2.mp3": QPushButton("Ping 2"),
            "ping3.mp3": QPushButton("Ping 3"),
        }
        for sound, btn in self.ping_buttons.items():
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked=False, s=sound: self.select_ping_sound(s)) # type: ignore
            ping_buttons_layout.addWidget(btn)

        watchlist_controls_layout.addLayout(ping_buttons_layout)

        # Add the sound controls
        self.lobby_placeholder_checkbox = QCheckBox("Play Sound When Game Found")
        test_sound_button = QPushButton("Test Sound")
        test_sound_button.clicked.connect(self.play_notification_sound)
        sound_layout = QHBoxLayout(); sound_layout.addWidget(self.lobby_placeholder_checkbox); sound_layout.addWidget(test_sound_button)
        watchlist_controls_layout.addLayout(sound_layout)
        self.lobby_placeholder_checkbox.setChecked(self.play_sound_on_found)
        watchlist_controls_layout.addStretch()

        watchlist_layout.addLayout(watchlist_controls_layout); watchlist_group.setLayout(watchlist_layout)
        lobbies_layout.addWidget(watchlist_group)
        self.lobbies_table = QTableWidget(); self.lobbies_table.setColumnCount(4)
        self.lobbies_table.setHorizontalHeaderLabels(["Name", "Map", "Players", "Host"]) # Added "Host"
        self.lobbies_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lobbies_table.verticalHeader().setVisible(False)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        lobbies_layout.addWidget(self.lobbies_table)
        self.stacked_widget.addWidget(lobbies_tab_content)

        # Settings tab (themes + custom theme picker)
        settings_tab_content = QWidget()
        settings_layout = QGridLayout(settings_tab_content)

        # Preset themes grid
        self.create_theme_grid(settings_layout)

        # Custom theme controls below presets
        row_below = (len(self.themes) - 1) // 4 + 1
        custom_box = QGroupBox("Custom theme")
        custom_layout = QGridLayout(custom_box)

        self.custom_enable_checkbox = QCheckBox("Enable custom theme (overrides preset)")
        self.custom_enable_checkbox.setChecked(self.custom_theme_enabled)
        self.custom_enable_checkbox.stateChanged.connect(self.on_custom_theme_toggled)
        custom_layout.addWidget(self.custom_enable_checkbox, 0, 0, 1, 3)

        self.bg_color_btn = QPushButton("Pick background")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color('bg'))
        self.fg_color_btn = QPushButton("Pick text")
        self.fg_color_btn.clicked.connect(lambda: self.pick_color('fg'))
        self.accent_color_btn = QPushButton("Pick accent")
        self.accent_color_btn.clicked.connect(lambda: self.pick_color('accent'))

        self.apply_custom_btn = QPushButton("Apply custom")
        self.apply_custom_btn.clicked.connect(self.apply_custom_theme)
        self.reset_custom_btn = QPushButton("Reset custom")
        self.reset_custom_btn.clicked.connect(self.reset_custom_theme_to_defaults)

        custom_layout.addWidget(self.bg_color_btn, 1, 0)
        custom_layout.addWidget(self.fg_color_btn, 1, 1)
        custom_layout.addWidget(self.accent_color_btn, 1, 2)
        custom_layout.addWidget(self.apply_custom_btn, 2, 0, 1, 2)
        custom_layout.addWidget(self.reset_custom_btn, 2, 2)

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
        self.automation_toggled_signal.connect(self.toggle_automation)
        self.load_character_signal.connect(self.on_f3_pressed)

        # Set initial selected ping sound
        self.update_ping_button_styles()

        # Apply preset or custom theme depending on the flag
        self.custom_tab_bar._on_button_clicked(self.last_tab_index)
        self.refresh_lobbies()
        self.load_characters() # Load characters on startup
        self.refresh_timer = QTimer(self); self.refresh_timer.setInterval(30000); self.refresh_timer.timeout.connect(self.refresh_lobbies); self.refresh_timer.start()
        
        # Load saved recipes after the UI is fully initialized
        self.item_database.load_recipes()
        self.apply_saved_recipes() # This call is now safe

        # Register global hotkeys (F5 for automation, etc.)
        self.register_global_hotkeys()

        # Apply theme last to ensure all widgets are styled correctly on startup
        if self.custom_theme_enabled:
            self.apply_custom_theme()
        else:
            self.apply_theme(self.current_theme_index)

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
        # Determine the correct accent color from the current theme (logic simplified)
        if self.custom_theme_enabled:
            accent_color = self.custom_theme.get("accent", "#FF7F50")
            checked_fg = self.custom_theme.get("bg", "#121212")
        else:
            theme = self.themes[self.current_theme_index]
            accent_color = theme.get("preview_color", "#FF7F50")
            # Simplified logic for text color on checked button
            checked_fg = "#000000" if not theme.get('is_dark') else self.custom_theme.get('bg', '#121212')
            if theme['name'] == 'Black/Orange':
                checked_fg = '#000000'
            elif theme['name'] == 'Black/Blue':
                checked_fg = '#EAEAEA'
            elif theme['name'] == 'White/Blue':
                checked_fg = '#F0F8FF'

        for sound, btn in self.ping_buttons.items():
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

    # Preset themes
    def apply_theme(self, theme_index: int):
        self.custom_theme_enabled = False  # disable custom when preset applied
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
        return f"""
        QWidget {{
            background-color: {bg};
            color: {fg};
            font-family: 'Segoe UI';
            font-size: 14px;
            outline: none;
        }}
        QMainWindow {{ background-color: {bg}; }}
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
            border: 1px solid {fg};
            padding: 5px;
            border-radius: 6px;
            color: {bg};
        }}
        QHeaderView::section {{
            background-color: {bg};
            border: 1px solid {fg};
            color: {fg};
        }}
        QLineEdit, QTextEdit, QListWidget, QTableWidget {{
            background-color: {bg};
            color: {fg};
            border: 1px solid {fg};
        }}
        QGroupBox {{
            border: 1px solid {fg};
            margin-top: 6px;
        }}
        QGroupBox:title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
        }}
        QCheckBox::indicator {{
            border: 1px solid {fg};
            background-color: {bg};
        }}
        """

    def apply_custom_theme(self):
        self.custom_theme_enabled = True
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
        self.update_ping_button_styles()

    def on_custom_theme_toggled(self, state: int):
        self.custom_theme_enabled = state == Qt.CheckState.Checked
        
        if self.custom_theme_enabled:
            self.apply_custom_theme()
        else:
            self.apply_theme(self.current_theme_index)

    def pick_color(self, key: str):
        initial = QColor(self.custom_theme[key])
        color = QColorDialog.getColor(initial, self, f"Pick {key} color")
        if color.isValid():
            self.custom_theme[key] = color.name()
            if self.custom_theme_enabled:
                self.apply_custom_theme()


    def reset_custom_theme_to_defaults(self):
        """Resets custom theme colors to their default values."""
        self.custom_theme = {
            "bg": "#121212",
            "fg": "#F0F0F0",
            "accent": "#FF7F50"
        }
        if self.custom_theme_enabled:
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
        self.custom_theme_enabled = False
        self.custom_theme = {"bg": "#121212", "fg": "#F0F0F0", "accent": "#FF7F50"}
        self.apply_theme(0)
        self.custom_tab_bar._on_button_clicked(0)
        self.watchlist = ["hellfire", "rpg"]
        self.watchlist_widget.clear(); self.watchlist_widget.addItems(self.watchlist)
        
        # Also reset recipes and automation settings
        self.in_progress_recipes.clear()
        self.in_progress_recipes_list.clear()
        self._rebuild_materials_table()
        self._reset_automation_ui()

        # Reset message hotkeys
        self.message_hotkeys.clear()
        self.load_message_hotkeys() # This will clear the table
        self.register_global_hotkeys() # This will unhook old and register new (just F5)

    # Settings
    def capture_message_hotkey(self):
        """Starts a worker thread to capture a key combination."""

        # Ensure any previous capture thread is stopped before starting a new one.
        if hasattr(self, 'capture_thread') and self.capture_thread.isRunning():
            self.capture_thread.quit()
            self.capture_thread.wait()


        self.automation_tab.message_edit.setEnabled(False)
        self.automation_tab.hotkey_capture_btn.setText("[Press a key...]")
        self.automation_tab.hotkey_capture_btn.setEnabled(False)

        # Unhook all global hotkeys to ensure the capture worker gets the keypress
        keyboard.unhook_all()

        self.capture_thread = QThread()
        self.capture_worker = HotkeyCaptureWorker()
        self.capture_worker.moveToThread(self.capture_thread) # type: ignore
        self.capture_thread.started.connect(self.capture_worker.run)
        self.capture_worker.hotkey_captured.connect(self.on_hotkey_captured)
        self.capture_thread.start()

    def on_hotkey_captured(self, hotkey: str):
        """Handles the captured hotkey string from the worker."""
        is_valid = True
        if '+' in hotkey:
            parts = hotkey.split('+')
            # Ensure modifiers are valid and not something like "2+3"
            for part in parts[:-1]:
                if part.strip().lower() not in keyboard.all_modifiers:
                    is_valid = False
                    break
        
        self.automation_tab.message_edit.setEnabled(True)

        if not is_valid or hotkey == 'esc':
            self.automation_tab.hotkey_capture_btn.setText("Click to set")
        else:
            self.automation_tab.hotkey_capture_btn.setText(hotkey)
        
        self.automation_tab.hotkey_capture_btn.setEnabled(True)

        # Clean up the thread and re-register global hotkeys
        if hasattr(self, 'capture_thread') and self.capture_thread.isRunning():
            self.capture_thread.quit()
            self.capture_thread.wait()
            self.capture_thread.deleteLater()
            del self.capture_thread
        # Re-registering ensures that F3, F5, etc. are always active after a capture attempt.
        self.register_global_hotkeys()

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

        if hotkey == "Click to set" or not message:
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
            self.automation_tab.hotkey_capture_btn.setText("Click to set")
            self.automation_tab.message_edit.clear()

    def send_chat_message(self, hotkey_pressed: str, message: str):
        """Sends a chat message if the game is active, otherwise passes the keypress through."""
        if not win32gui:
            return
        try:
            game_hwnd = win32gui.FindWindow(None, self.game_title)
            is_game_active = (win32gui.GetForegroundWindow() == game_hwnd)
        except Exception:
            is_game_active = False

        if not is_game_active:
            try: keyboard.send(hotkey_pressed)
            except Exception: pass
            return # type: ignore

        if self.is_sending_message: return
        self.is_sending_message = True

        worker = ChatMessageWorker(self.game_title, hotkey_pressed, message)
        thread = QThread()
        worker.moveToThread(thread)

        # Ensure both worker and thread are cleaned up
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)

        thread.started.connect(worker.run)
        worker.finished.connect(self.on_chat_send_finished)
        worker.error.connect(self.on_chat_send_error)
        thread.start()

    def on_chat_send_error(self, error_message: str): # type: ignore
        QMessageBox.critical(self, "Chat Error", f"Failed to send message: {error_message}") # type: ignore
        self.is_sending_message = False

    def on_chat_send_finished(self):
        self.is_sending_message = False

    def apply_loaded_settings(self):
        """Applies settings from the SettingsManager to the application state."""
        self.current_theme_index = self.settings_manager.get("theme_index")
        self.last_tab_index = self.settings_manager.get("last_tab_index")
        self.character_path = self.settings_manager.get("character_path")
        if not self.character_path:
             self.character_path = os.path.join(os.path.expanduser("~"), "Documents", "Warcraft III", "CustomMapData", "Hellfire RPG")
        self.message_hotkeys = self.settings_manager.get("message_hotkeys")
        self.custom_theme_enabled = self.settings_manager.get("custom_theme_enabled")
        self.automation_settings = self.settings_manager.get("automation")
        self.custom_theme = self.settings_manager.get("custom_theme")
        self.watchlist = self.settings_manager.get("watchlist")
        self.play_sound_on_found = self.settings_manager.get("play_sound_on_found")
        self.selected_sound = self.settings_manager.get("selected_sound")

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

    def apply_saved_recipes(self):
        """Loads and populates the in-progress recipes from settings."""
        saved_recipes = self.settings_manager.get("in_progress_recipes", [])
        for recipe_name in saved_recipes:
            self._add_recipe_by_name(recipe_name)

    # Watchlist
    def load_watchlist(self):
        """Loads the watchlist from settings. This is now handled by load_settings()."""
        # This method is kept for compatibility but logic is in load_settings()
        # The watchlist is loaded with other settings at startup.
        self.watchlist_widget.clear()
        self.watchlist_widget.addItems(self.watchlist)
    def add_to_watchlist(self):
        keyword = self.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.watchlist_widget.addItem(keyword)
            self.watchlist_input.clear()
            self.filter_lobbies(self.lobby_search_bar.text())
    def remove_from_watchlist(self):
        selected_items = self.watchlist_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.watchlist_widget.takeItem(self.watchlist_widget.row(item))
        self.filter_lobbies(self.lobby_search_bar.text())

    # Items
    def filter_current_item_view(self):
        query = self.items_tab.search_box.text().lower()
        current_index = self.items_tab.stacked_widget.currentIndex()
        data_source, table_widget = [], None
        if current_index == 0: data_source, table_widget = self.item_database.all_items_data, self.items_tab.all_items_table
        elif current_index == 1: data_source, table_widget = self.item_database.drops_data, self.items_tab.drops_table
        elif current_index == 2: data_source, table_widget = self.item_database.raid_data, self.items_tab.raid_items_table
        elif current_index == 3: data_source, table_widget = self.item_database.vendor_data, self.items_tab.vendor_table
        if not table_widget: return
        table_widget.setSortingEnabled(False); table_widget.setRowCount(0)
        filtered_data = [item for item in data_source if query in item.get("Item", "").lower() or
                         query in item.get("Unit", "").lower() or query in item.get("Location", "").lower()]
        headers = [table_widget.horizontalHeaderItem(i).text() for i in range(table_widget.columnCount())]
        for row, item_data in enumerate(filtered_data):
            table_widget.insertRow(row)
            for col, header in enumerate(headers):
                table_widget.setItem(row, col, QTableWidgetItem(item_data.get(header, "")))
        table_widget.setSortingEnabled(True)

    def switch_items_sub_tab(self, index: int):
        for i, btn in self.items_tab.item_tab_buttons.items():
            btn.setChecked(i == index)
        self.items_tab.stacked_widget.setCurrentIndex(index)
        self.items_tab.search_box.setVisible(True)
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
        if not self.item_database.recipes_data:
            self.item_database.load_recipes()
        query = self.recipes_tab.recipe_search_box.text().lower()
        self.recipes_tab.available_recipes_list.clear()
        for recipe in self.item_database.recipes_data:
            if query in recipe["name"].lower():
                item = QListWidgetItem(recipe["name"])
                item.setData(Qt.ItemDataRole.UserRole, recipe)
                self.recipes_tab.available_recipes_list.addItem(item)

    def add_recipe_to_progress(self):
        """Adds a recipe to the 'in-progress' list from the UI selection."""
        selected_item = self.recipes_tab.available_recipes_list.currentItem()
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
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.recipes_tab.in_progress_recipes_list.addItem(item)
        return True

    def remove_recipe_from_progress(self):
        selected_item = self.recipes_tab.in_progress_recipes_list.currentItem()
        if not selected_item:
            return
        recipe_name = selected_item.text()
        recipe = self.in_progress_recipes.pop(recipe_name, None)
        if recipe:
            list_widget = self.recipes_tab.in_progress_recipes_list
            list_widget.takeItem(list_widget.row(selected_item))
            self._rebuild_materials_table()

    def reset_recipes(self):
        """Clears all in-progress recipes and the materials list."""
        confirm = QMessageBox.question(self, "Confirm Reset", "Are you sure you want to clear all in-progress recipes?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.in_progress_recipes.clear()
            self.recipes_tab.in_progress_recipes_list.clear()
            self._rebuild_materials_table()

    def _reset_automation_ui(self):
        """Resets the automation UI controls to their default values without confirmation."""
        self.reset_automation_settings(confirm=False)

    def _rebuild_materials_table(self):
        """Clears and repopulates the materials table based on the internal data dictionary and checked recipes."""
        # Disconnect signals to prevent loops during update
        materials_table = self.recipes_tab.materials_table
        materials_table.setSortingEnabled(False)
        try:
            materials_table.itemChanged.disconnect(self.on_material_checked)
        except RuntimeError: # Already disconnected
            pass
        materials_table.setRowCount(0)
        
        # Determine which recipes to calculate materials for
        checked_recipe_names = []
        in_progress_list = self.recipes_tab.in_progress_recipes_list
        for i in range(in_progress_list.count()):
            item = in_progress_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_recipe_names.append(item.text())
        
        # If no recipes are checked, use all recipes in the "In Progress" list
        in_progress_list = self.recipes_tab.in_progress_recipes_list
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
            materials_table.setItem(row, 0, material_item)
            materials_table.setItem(row, 1, QTableWidgetItem(str(item_data["#"])))
            materials_table.setItem(row, 2, QTableWidgetItem(item_data["Unit"]))
            materials_table.setItem(row, 3, QTableWidgetItem(item_data["Location"]))
            materials_table.setItem(row, 4, QTableWidgetItem("0"))
        
        # Reconnect signals and enable sorting
        materials_table.itemChanged.connect(self.on_material_checked)
        materials_table.setSortingEnabled(True)

    def on_material_checked(self, item: QTableWidgetItem):
        if item.column() != 0: return
        materials_table = self.recipes_tab.materials_table
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

    def on_recipe_check_changed(self, item: QListWidgetItem):
        """Called when any recipe's check state changes to rebuild the material list."""
        # This handler is now connected to QListWidget.itemChanged
        self._rebuild_materials_table()

    # Character loading
    def on_path_changed(self, new_path: str):
        self.character_path = new_path # Still need to update the main window's state
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

    # Lobbies
    def refresh_lobbies(self):
        if self.is_fetching_lobbies:
            return # Don't start a new refresh if one is already running
        self.is_fetching_lobbies = True

        self.lobbies_table.setRowCount(0); self.lobbies_table.setRowCount(1)
        loading_item = QTableWidgetItem("Fetching lobby data..."); loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, loading_item); self.lobbies_table.setSpan(0, 0, 1, 3)
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
        self.is_fetching_lobbies = False # Reset the flag
        for lobby in lobbies:
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    current_watched_lobbies.add(lobby.get('name')); break
        newly_found = current_watched_lobbies - self.previous_watched_lobbies
        if newly_found and self.lobby_placeholder_checkbox.isChecked():
            self.play_notification_sound()
        self.previous_watched_lobbies = current_watched_lobbies
        self.all_lobbies = lobbies # type: ignore
        self.filter_lobbies(self.lobby_search_bar.text())
    def on_lobbies_fetch_error(self, error_message: str):
        self.is_fetching_lobbies = False # Reset the flag
        self.lobbies_table.setRowCount(1)
        self.lobbies_table.setSpan(0, 0, 1, self.lobbies_table.columnCount())
        error_item = QTableWidgetItem(f"Error: {error_message}")
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobbies_table.setItem(0, 0, error_item)
    def filter_lobbies(self, query: str):
        self.lobbies_table.setRowCount(0); self.lobbies_table.setSortingEnabled(False)
        query = query.lower()
        filtered_lobbies = [l for l in self.all_lobbies if query in l.get('name', '').lower() or query in l.get('map', '').lower()]
        def is_watched(lobby):
            name = lobby.get('name', '').lower(); map_name = lobby.get('map', '').lower()
            return any(k in name or k in map_name for k in self.watchlist)
        sorted_lobbies = sorted(filtered_lobbies, key=is_watched, reverse=True)
        self.lobbies_table.setRowCount(len(sorted_lobbies))
        for row, lobby in enumerate(sorted_lobbies):
            lobby_name = lobby.get('name', '').lower(); lobby_map = lobby.get('map', '').lower()
            watched = any(k in lobby_name or k in lobby_map for k in self.watchlist)
            self.lobbies_table.setItem(row, 0, QTableWidgetItem(lobby.get('name', 'N/A')))
            self.lobbies_table.setItem(row, 1, QTableWidgetItem(lobby.get('map', 'N/A')))
            players = f"{lobby.get('slotsTaken', '?')}/{lobby.get('slotsTotal', '?')}"
            self.lobbies_table.setItem(row, 2, AlignedTableWidgetItem(players))
            host = lobby.get('host', lobby.get('server', 'N/A')) # Fallback to 'server' if 'host' is not present
            self.lobbies_table.setItem(row, 3, AlignedTableWidgetItem(host))
            if watched:
                for col in range(self.lobbies_table.columnCount()): # type: ignore
                    self.lobbies_table.item(row, col).setBackground(QColor("#3A5F0B"))
        self.lobbies_table.setSortingEnabled(True)

    # Tab select logic
    def on_main_tab_selected(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        tab_name = self.tab_names[index]
        if tab_name == "Items" and not self.item_database.all_items_data:
            self.switch_items_sub_tab(0) # Lazy load
        elif tab_name == "Lobbies":
            self.refresh_lobbies() # Refresh when tab is viewed
        elif tab_name == "Recipes":
            if not self.item_database.recipes_data: self.item_database.load_recipes()
            self.filter_recipes_list()
            self._rebuild_materials_table() # Rebuild materials when tab is viewed
        elif tab_name == "Automation":
            self.load_message_hotkeys()

    def control_send_key(self, key: str):
        """Sends a key press to the game window without activating it."""
        if not win32gui or not win32api or not win32con:
            print("ControlSend functionality is only available on Windows.")
            return

        hwnd = win32gui.FindWindow(None, self.game_title)
        if hwnd == 0:
            # Silently fail if the window is not found, to avoid spamming messages.
            # The user will see that the automation isn't working.
            return

        # Virtual-Key Codes mapping
        vk_code = {
            'q': 0x51, 'w': 0x57, 'e': 0x45, 'r': 0x52, 'd': 0x44, 'f': 0x46,
            't': 0x54, 'z': 0x5A, 'x': 0x58, 'y': 0x59, 'esc': win32con.VK_ESCAPE
        }.get(key.lower())

        if vk_code is None:
            print(f"No virtual key code found for key: {key}")
            return

        # PostMessage is asynchronous and non-blocking
        win32api.PostMessage(hwnd, win32con.WM_KEYDOWN, vk_code, 0)
        # Add a small delay before sending the key up message
        QTimer.singleShot(50, lambda: self._control_send_key_up(hwnd, vk_code))

    def _control_send_key_up(self, hwnd, vk_code):
        """Helper to send the WM_KEYUP message."""
        if not win32api or not win32con:
            return
        # The lparam for key up includes flags indicating the key is being released.
        lparam = (1 << 31) | (1 << 30)
        win32api.PostMessage(hwnd, win32con.WM_KEYUP, vk_code, lparam)

    def pause_all_automation(self):
        # Unhook message hotkeys temporarily to prevent them from firing
        for hk, hk_id in list(self.hotkey_ids.items()):
            if hk not in ['f5']: # Keep global toggle active
                try: keyboard.remove_hotkey(hk_id)
                except Exception: pass

        for timer in self.automation_timers.values():
            timer.stop()

    def resume_all_automation(self):
        # Re-register message hotkeys
        for hotkey, message in self.message_hotkeys.items():
            if hotkey not in self.hotkey_ids:
                self.register_single_hotkey(hotkey, message)

        for timer in self.automation_timers.values():
            timer.start()

    def run_complete_quest(self):
        # If custom action is running, wait then retry
        if self.custom_action_running:
            QTimer.singleShot(2500, self.run_complete_quest)
            return
        # Pause QWERDFZX timers
        self.pause_all_automation()
        # Sequence: y -> 100ms -> e -> 100ms -> esc
        self.control_send_key('y')
        QTimer.singleShot(100, lambda: self.control_send_key('e'))
        QTimer.singleShot(200, lambda: self.control_send_key('esc'))
        # Resume after ~2.1s to allow keys to be processed
        QTimer.singleShot(2100, self.resume_all_automation)

    def run_custom_action(self, message: str):
        # Highest priority, pauses everything including complete quest
        self.custom_action_running = True
        self.pause_all_automation()
        def type_message():
            pyautogui.press('enter')
            pyautogui.write(message, interval=0.03)
            pyautogui.press('enter')
        # Wait 2s, type, then wait 2s more and resume
        QTimer.singleShot(2000, type_message)
        QTimer.singleShot(4000, self._end_custom_action)

    def _end_custom_action(self):
        self.custom_action_running = False
        self.resume_all_automation()

    def _reset_automation_button_style(self):
        """Resets the automation button to its default theme color."""
        if self.custom_theme_enabled:
            accent_color = self.custom_theme.get("accent", "#FF7F50")
            text_color = self.custom_theme.get("bg", "#121212")
            self.automation_tab.start_automation_btn.setStyleSheet(f"background-color: {accent_color}; color: {text_color};")
        else:
            # For preset themes, setting an empty stylesheet is enough to revert.
            # However, to be explicit and robust:
            self.automation_tab.start_automation_btn.setStyleSheet("")

    def toggle_automation(self):
        self.is_automation_running = not self.is_automation_running
        if self.is_automation_running:
            self.automation_tab.start_automation_btn.setText("Stop (F5)")
            self.automation_tab.start_automation_btn.setStyleSheet("background-color: #B00000;")
            # Start timers
            for key, ctrls in self.automation_tab.automation_key_ctrls.items():
                if ctrls["chk"].isChecked():
                    interval_text = ctrls["edit"].text().strip()
                    if not interval_text:
                        continue
                    try:
                        interval = int(interval_text)
                        timer = QTimer(self)
                        if key == "Complete Quest":
                            timer.timeout.connect(self.run_complete_quest)
                        else:
                            # Raw key presses (no typing into chat)
                            timer.timeout.connect(lambda k=key: self.control_send_key(k))
                        timer.start(interval)
                        self.automation_timers[key] = timer
                    except ValueError:
                        QMessageBox.warning(self, "Invalid interval", f"Interval for '{key}' must be a number in ms.")
            # Custom Action timer
            if self.automation_tab.custom_action_btn.isChecked():
                interval_text = self.automation_tab.custom_action_edit1.text().strip()
                if interval_text:
                    try:
                        interval = int(interval_text)
                        message = self.automation_tab.custom_action_edit2.text()
                        timer = QTimer(self)
                        timer.timeout.connect(lambda msg=message: self.run_custom_action(msg))
                        timer.start(interval)
                        self.automation_timers["custom"] = timer
                    except ValueError:
                        QMessageBox.warning(self, "Invalid interval", "Interval for 'Custom Action' must be a number in ms.")
        else:
            self.automation_tab.start_automation_btn.setText("Start (F5)")
            self._reset_automation_button_style()
            for timer in self.automation_timers.values():
                timer.stop(); timer.deleteLater()
            self.automation_timers.clear()

    def reset_automation_settings(self, confirm=True):
        """Resets all automation settings in the UI to their defaults."""
        do_reset = False
        if not confirm:
            do_reset = True
        elif QMessageBox.question(self, "Confirm Reset", "Are you sure you want to reset all automation settings to their defaults?") == QMessageBox.StandardButton.Yes:
            do_reset = True
        if do_reset:
            # Reset key automation
            for key, ctrls in self.automation_tab.automation_key_ctrls.items():
                ctrls["chk"].setChecked(False)
                default_interval = "15000" if key == "Complete Quest" else "500"
                ctrls["edit"].setText(default_interval)
            # Reset custom action
            self.automation_tab.custom_action_btn.setChecked(False)
            self.automation_tab.custom_action_edit1.setText("30000")
            self.automation_tab.custom_action_edit2.setText("-save x")

    def register_global_hotkeys(self):
        """Registers all hotkeys, including global controls and custom messages."""
        keyboard.unhook_all()
        self.hotkey_ids.clear()

        # Register global F5 for automation toggle
        try:
            f5_id = keyboard.add_hotkey('f5', lambda: self.automation_toggled_signal.emit(), suppress=True)
            self.hotkey_ids['f5'] = f5_id
        except Exception as e:
            print(f"Failed to register F5 hotkey: {e}")

        # Register global F3 for loading character
        try:
            f3_id = keyboard.add_hotkey('f3', lambda: self.load_character_signal.emit(), suppress=True)
            self.hotkey_ids['f3'] = f3_id
        except Exception as e:
            print(f"Failed to register F3 hotkey: {e}")

        # Register all custom message hotkeys
        for hotkey, message in self.message_hotkeys.items():
            self.register_single_hotkey(hotkey, message)

    def register_single_hotkey(self, hotkey: str, message: str):
        """Helper to register a single message hotkey."""
        try:
            hk_id = keyboard.add_hotkey(hotkey, lambda h=hotkey, msg=message: self.send_chat_message(h, msg), suppress=True)
            self.hotkey_ids[hotkey] = hk_id
        except (ValueError, ImportError) as e:
            print(f"Failed to register hotkey '{hotkey}': {e}")

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
        try:
            for timer in self.automation_timers.values():
                timer.stop(); timer.deleteLater()
            self.automation_timers.clear()
        except Exception:
            pass
        keyboard.unhook_all() # Clean up all global listeners
        event.accept()


if __name__ == "__main__":

    app = QApplication(sys.argv)
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())