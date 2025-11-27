import sys
import json
import os
import re
import subprocess
from typing import List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QGroupBox, QFileDialog, QTextEdit,
    QListWidgetItem, QColorDialog, QCheckBox, QSlider, QFontComboBox, QSpinBox
)
from PySide6.QtCore import Signal, Qt, QThread, QTimer, QUrl, QPoint
from PySide6.QtGui import QMouseEvent, QColor, QIntValidator, QFont, QPalette, QAction, QDesktopServices, QShortcut, QKeySequence, QIcon, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

import keyboard   # type: ignore
import pyautogui  # type: ignore

from utils import get_base_path, DARK_STYLE, LIGHT_STYLE, FOREST_STYLE, OCEAN_STYLE
from data import ItemDatabase
from theme_manager import ThemeManager
from items_manager import ItemsManager
from lobby_manager import LobbyManager
from character_load_manager import CharacterLoadManager
from workers import LobbyFetcher, HotkeyCaptureWorker, LobbyHeartbeatChecker
from settings import SettingsManager
from automation_manager import AutomationManager
from quickcast_manager import QuickcastManager
from ui_tab_widgets import CharacterLoadTab, AutomationTab, ItemsTab, QuickcastTab, LobbiesTab
from ui_overlay import OverlayStatus
import time
import ctypes

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
    quickcast_toggle_signal = Signal()

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
        self.font_family = self.settings_manager.get("font_family", "Segoe UI")
        self.font_size = self.settings_manager.get("font_size", 11)

        self.old_pos = None
        self.hotkey_ids = {}            # {hotkey_str: id from keyboard.add_hotkey}
        self.is_sending_message = False
        self.game_title = "Warcraft III"

        # Automation state flags
        self.automation_settings = {} # To hold loaded settings
        self.is_capturing_hotkey = False
        self.ahk_process = None
        self.dark_mode = True # Initialize with a default to prevent startup errors
        self.message_hotkeys = {}       # {hotkey_str: message_str}
        self.custom_theme_enabled = self.settings_manager.get("custom_theme_enabled", False)
        self.keybinds = self.settings_manager.get("keybinds", {})

        # Keybind state
        self.capturing_for_control = None
        self.is_executing_keybind = False # Flag to prevent hotkey recursion
        self.vk_map = {
            'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45, 'f': 0x46, 'g': 0x47, 'h': 0x48,
            'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50,
            'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54, 'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
            'y': 0x59, 'z': 0x5A,
            '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, '5': 0x35, '6': 0x36, '7': 0x37,
            '8': 0x38, '9': 0x39,
            'numpad0': 0x60, 'numpad1': 0x61, 'numpad2': 0x62, 'numpad3': 0x63, 'numpad4': 0x64,
            'numpad5': 0x65, 'numpad6': 0x66, 'numpad7': 0x67, 'numpad8': 0x68, 'numpad9': 0x69,
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74, 'f6': 0x75, 'f7': 0x76,
            'f8': 0x77, 'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
            'enter': 0x0D, 'esc': 0x1B, 'space': 0x20, 'tab': 0x09, 'backspace': 0x08,
            'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
            'ctrl': win32con.VK_CONTROL, 'alt': 0x12, 'shift': 0x10,
            'lbutton': 0x01, 'rbutton': 0x02,
            # Add other keys as needed
        } if win32con else {}
        self.f2_key_down = False # Debounce flag for F2 spam

        # --- Ctypes definitions for SendInput ---
        # Define these once at startup to avoid redefining them on every keypress,
        # which is a minor performance optimization for the quickcast macro.
        if win32con:
            PUL = ctypes.POINTER(ctypes.c_ulong)
            class KeyBdInput(ctypes.Structure):
                _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                            ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                            ("dwExtraInfo", PUL)]

            class MouseInput(ctypes.Structure):
                _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                            ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                            ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]

            class Input_I(ctypes.Union):
                _fields_ = [("ki", KeyBdInput), ("mi", MouseInput)]

            class Input(ctypes.Structure):
                _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

            self.Input = Input
            self.KeyBdInput = KeyBdInput
            self.MouseInput = MouseInput
            self.Input_I = Input_I
        # This new implementation is a much more faithful recreation of AHK's SendInput.
        
        # Define structures for inputs

        # Initialize the floating status overlay
        self.status_overlay = OverlayStatus()

        # Initialize media player for custom sounds
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(700, 800)

        self.setWindowTitle("Hellfire Helper")
        self.setWindowIcon(QIcon(os.path.join(get_base_path(), "contents", "icon.ico"))) # Set the application icon
        self.apply_loaded_settings() # Load settings before creating UI elements that depend on them

        # Apply font settings at startup
        initial_font = QFont(self.font_family, self.font_size)
        QApplication.instance().setFont(initial_font)


        # Center the window on the primary screen
        screen = QApplication.primaryScreen()
        if screen:
            center_point = screen.geometry().center()
            frame_geometry = self.frameGeometry()
            frame_geometry.moveCenter(center_point)
            self.move(frame_geometry.topLeft())

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

        # Create a placeholder for the title widget, which will be populated by set_title_image
        self.title_widget_container = QWidget()
        self.title_widget_container.setLayout(QHBoxLayout())
        self.title_widget_container.setStyleSheet("background-color: transparent;")
        self.title_widget_container.layout().setContentsMargins(0,0,0,0)

        min_button = QPushButton("_"); min_button.setFixedSize(30, 30); min_button.clicked.connect(self.showMinimized)
        close_button = QPushButton("X"); close_button.setFixedSize(30, 30); close_button.clicked.connect(self.close)

        # Create a separate layout for the buttons (only minimize and close)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(0)
        button_layout.addWidget(min_button)
        button_layout.addWidget(close_button)

        title_bar_layout.addWidget(self.title_widget_container, 0, 0, 1, 1, Qt.AlignmentFlag.AlignCenter) # Title centered
        title_bar_layout.addLayout(button_layout, 0, 0, 1, 1, Qt.AlignmentFlag.AlignRight) # Buttons right-aligned
        main_layout.addWidget(self.title_bar)

        # Tabs
        self.tab_names = ["Load", "Items", "Placeholder", "Automation", "Quickcast", "Lobbies", "Settings", "Reset"]
        self.custom_tab_bar = CustomTabBar(self.tab_names, tabs_per_row=4)
        main_layout.addWidget(self.custom_tab_bar)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        self.custom_tab_bar.tab_selected.connect(self.stacked_widget.setCurrentIndex)

        # Load tab
        self.load_tab = CharacterLoadTab(self); self.stacked_widget.addWidget(self.load_tab)
        self.character_load_manager = CharacterLoadManager(self)
        # Items tab
        self.item_database = ItemDatabase()
        self.items_tab = ItemsTab(self)
        self.stacked_widget.addWidget(self.items_tab)

        # Initialize the ItemsManager to handle all logic for the Items tab
        self.items_manager = ItemsManager(self)
        self.items_manager.switch_items_sub_tab(0)

        # Placeholder Tab
        placeholder_tab = QWidget()
        placeholder_layout = QVBoxLayout(placeholder_tab)
        placeholder_label = QLabel("This is a placeholder tab.")
        placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder_layout.addWidget(placeholder_label)
        self.stacked_widget.addWidget(placeholder_tab)

        # Recipes tab
        self.in_progress_recipes = {}

        # Automation tab
        self.automation_tab = AutomationTab(self)
        self.stacked_widget.addWidget(self.automation_tab)

        # Initialize managers after all tabs are created
        self.automation_manager = AutomationManager(self)
        self.quickcast_manager = QuickcastManager(self)


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
        self.quickcast_tab.reset_keybinds_btn.clicked.connect(self.reset_keybinds)
        # New connection for the Activate Quickcast button
        self.quickcast_tab.activate_quickcast_btn.clicked.connect(self.quickcast_manager.toggle_ahk_quickcast)
                # Connections for AHK installation buttons
        self.quickcast_tab.install_ahk_cmd_btn.clicked.connect(self.quickcast_manager.show_ahk_install_cmd)
        self.quickcast_tab.install_ahk_web_btn.clicked.connect(self.quickcast_manager.open_ahk_website)
        self.quickcast_tab.activate_quickcast_btn.setText("Activate Quickcast (F2)")
        
        # Lobbies tab
        self.lobbies_tab = LobbiesTab(self)
        self.stacked_widget.addWidget(self.lobbies_tab)

        # Initialize the LobbyManager to handle all logic for the Lobbies tab
        self.lobby_manager = LobbyManager(self)

        # Settings tab (themes + custom theme picker)
        settings_tab_content = QWidget()
        settings_layout = QGridLayout(settings_tab_content)

        self.theme_manager = ThemeManager(self)
        # Preset themes grid
        self.theme_manager.create_theme_grid(settings_layout)

        # Custom theme controls below presets
        row_below = (len(self.theme_manager.themes) - 1) // 4 + 1
        custom_box = QGroupBox("Custom theme")
        custom_v_layout = QVBoxLayout(custom_box)

        self.bg_color_btn = QPushButton("Background")
        self.bg_color_btn.clicked.connect(lambda: self.pick_color('bg'))
        self.fg_color_btn = QPushButton("Text")
        self.fg_color_btn.clicked.connect(lambda: self.pick_color('fg'))
        self.accent_color_btn = QPushButton("Accent")
        self.accent_color_btn.clicked.connect(lambda: self.theme_manager.pick_color('accent'))

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
        self.apply_custom_btn.clicked.connect(self.theme_manager.apply_custom_theme)
        self.reset_custom_btn = QPushButton("Reset custom")
        self.reset_custom_btn.clicked.connect(self.reset_custom_theme_and_title)

        self.select_custom_title_btn = QPushButton("Select Custom Title Image")
        self.select_custom_title_btn.clicked.connect(self.select_custom_title_image)

        action_buttons_h_layout = QHBoxLayout()
        action_buttons_h_layout.addWidget(self.apply_custom_btn)
        action_buttons_h_layout.addWidget(self.reset_custom_btn)

        custom_v_layout.addWidget(self.select_custom_title_btn)
        custom_v_layout.addLayout(pick_buttons_h_layout)
        custom_v_layout.addWidget(self.custom_theme_preview)        
        custom_v_layout.addLayout(action_buttons_h_layout)

        settings_layout.setRowStretch(row_below + 2, 1) # Add stretch to the main grid layout
        settings_layout.addWidget(custom_box, row_below, 0, 1, 4)

        # Fonts box
        fonts_box = QGroupBox("Fonts")
        fonts_layout = QVBoxLayout(fonts_box)
        
        font_controls_layout = QHBoxLayout()
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(self.font_family))
        
        self.font_size_spinbox = QSpinBox()
        self.font_size_spinbox.setRange(8, 24)
        self.font_size_spinbox.setValue(self.font_size)
        self.font_size_spinbox.setSuffix(" pt")

        font_controls_layout.addWidget(QLabel("Font:"))
        font_controls_layout.addWidget(self.font_combo, 1)
        font_controls_layout.addWidget(self.font_size_spinbox)
        
        font_buttons_layout = QHBoxLayout()
        font_buttons_layout.addStretch()
        self.reset_font_btn = QPushButton("Reset Font")
        self.apply_font_btn = QPushButton("Apply Font")
        font_buttons_layout.addWidget(self.reset_font_btn)
        font_buttons_layout.addWidget(self.apply_font_btn)

        fonts_layout.addLayout(font_controls_layout)
        fonts_layout.addLayout(font_buttons_layout)
        fonts_box.setLayout(fonts_layout)
        settings_layout.addWidget(fonts_box, row_below + 1, 0, 1, 4)

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
        self.quickcast_toggle_signal.connect(self.quickcast_manager.toggle_ahk_quickcast)
        self.send_message_signal.connect(self._main_thread_send_chat_message)

        self.reset_font_btn.clicked.connect(self.reset_font_settings)
        self.apply_font_btn.clicked.connect(self.apply_font_settings)
        self.automation_manager.status_changed.connect(self.status_overlay.show_status)
        self.automation_manager.automation_state_changed.connect(self.update_automation_button_style)

        # Set initial selected ping sound
        self.update_ping_button_styles()

        # Apply loaded keybinds
        self.quickcast_manager.apply_keybind_settings()


        # Finalize UI state
        self.custom_tab_bar._on_button_clicked(self.last_tab_index)
        
        # Load saved recipes after the UI is fully initialized
        self.item_database.load_recipes()
        self.apply_saved_recipes() # This call is now safe

        # Register global hotkeys (F5 for automation, etc.)
        self.register_global_hotkeys()

        # Apply theme last to ensure all widgets are styled correctly on startup
        # A theme index of -1 indicates a custom theme was last used.
        if self.current_theme_index == -1:
            # Apply custom theme and update its preview
            self.theme_manager.apply_custom_theme()
            self.theme_manager.update_custom_theme_preview()
        else:
            self.theme_manager.apply_theme(self.current_theme_index)

        # Initial data load for lobbies
        self.lobby_manager.refresh_lobbies()

    def update_automation_button_style(self, is_running: bool):
        """Updates the 'Start/F5' button color based on automation state."""
        button = self.automation_tab.start_automation_btn
        # Revert to the default stylesheet to ensure we have a clean base
        button.setStyleSheet("")
        if is_running:
            button.setStyleSheet("background-color: #228B22; color: white;") # ForestGreen
        else:
            # Force a style refresh by unpolishing and repolishing the widget.
            # This makes it re-read the global stylesheet.
            button.style().unpolish(button)
            button.style().polish(button)

    def update_automation_log(self, message: str):
        """Appends a message to the automation log text box."""
        self.automation_tab.automation_log_box.append(message)

    def set_volume(self, value: int):
        """Sets the media player volume. The manager keeps track of the value."""
        volume_float = value / 100.0
        self.audio_output.setVolume(volume_float)

    # Core helpers
    def select_ping_sound(self, sound_file: str):
        """Delegates sound selection to the LobbyManager."""
        self.lobby_manager.select_ping_sound(sound_file)

    def update_ping_button_styles(self):
        """Updates the visual state of the ping buttons."""
        theme = self.theme_manager.themes[self.current_theme_index] if self.current_theme_index != -1 else self.custom_theme
        accent_color = theme.get("accent", theme.get("preview_color", "#FF7F50"))
        is_dark = theme.get("is_dark", self.dark_mode)
        checked_fg = "#000000" if not is_dark else "#FFFFFF"
        if self.current_theme_index == -1: checked_fg = self.custom_theme.get("bg", "#121212")
        
        selected_sound = self.lobby_manager.selected_sound
        for sound, btn in self.lobby_manager.lobbies_tab.ping_buttons.items():
            btn.setChecked(sound == selected_sound)
            if sound == selected_sound:
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



    def pick_color(self, key: str):
        """Delegates color picking to the ThemeManager."""
        self.theme_manager.pick_color(key)

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
        self.theme_manager.apply_theme(0)
        self.custom_tab_bar._on_button_clicked(0)
        self.lobby_manager.watchlist = ["hellfire", "rpg"]
        self.custom_title_image_path = "" # Reset custom title image path
        self.lobby_manager.lobbies_tab.watchlist_widget.clear(); self.lobby_manager.lobbies_tab.watchlist_widget.addItems(self.lobby_manager.watchlist)
        self.lobby_manager.lobbies_tab.volume_slider.setValue(100)
        
        # Also reset recipes and automation settings (delegating recipe reset)
        self.in_progress_recipes.clear()
        self.items_tab.in_progress_recipes_list.clear() # type: ignore
        self.items_manager.rebuild_materials_table()
        self.reset_automation_settings(confirm=False)

        # Reset font settings
        self.reset_font_settings()

        # Reset message hotkeys
        self.message_hotkeys.clear()
        self.load_message_hotkeys() # This will clear the table
        self.register_global_hotkeys() # This will unhook old and register new (just F5)

    def set_title_image(self, image_name: str | None):
        """Sets the title bar image, or falls back to text if not found."""
        # Clear the existing title widget
        while self.title_widget_container.layout().count():
            child = self.title_widget_container.layout().takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        title_widget = None
        if image_name:
            image_path = image_name if os.path.isabs(image_name) else os.path.join(get_base_path(), "contents", image_name)
            if os.path.exists(image_path):
                title_widget = QLabel()
                pixmap = QPixmap(image_path)
                title_widget.setPixmap(pixmap.scaled(pixmap.width(), 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                title_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                title_widget.setStyleSheet("background-color: transparent;")

        if not title_widget:
            # Fallback to icon and text if no image or image not found
            title_widget = QWidget()
            title_widget.setStyleSheet("background-color: transparent;")
            title_layout = QHBoxLayout(title_widget)
            title_layout.setContentsMargins(0,0,0,0)
            title_layout.setSpacing(5)
            icon_label = QLabel()
            icon_pixmap = QPixmap(os.path.join(get_base_path(), "contents", "icon.ico"))
            icon_label.setPixmap(icon_pixmap.scaled(19, 19, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            title_layout.addWidget(icon_label); title_layout.addWidget(QLabel("Hellfire Helper"))

        self.title_widget_container.layout().addWidget(title_widget, 0, Qt.AlignmentFlag.AlignVCenter)

    def select_custom_title_image(self):
        """Opens a file dialog to select an image for the custom theme title."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Custom Title Image", get_base_path(), "Images (*.png *.jpg *.bmp)")
        if file_path:
            self.custom_title_image_path = file_path
            self.theme_manager.apply_custom_theme() # Re-apply to show the new title

    def reset_custom_theme_and_title(self):
        self.custom_title_image_path = ""
        self.theme_manager.reset_custom_theme_to_defaults()

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

    def _get_default_key_for_control(self, control_name: str) -> str:
        """Gets the default key for a given keybind control name."""
        parts = control_name.split('_')
        if parts[0] == "mouse":
            return "LButton" if parts[1] == "Left" else "RButton"
        else: # spell or inv
            return parts[1]

    def on_hotkey_captured(self, hotkey: str):
        """Handles the captured hotkey string from the worker."""
        self.automation_tab.message_edit.setEnabled(True)
        self.automation_tab.hotkey_capture_btn.setEnabled(True)
        is_valid = hotkey.lower() != 'esc'

        # If we were capturing for a keybind button, update it
        if self.capturing_for_control:
            button = self.quickcast_tab.key_buttons[self.capturing_for_control]
            button.setChecked(False) # Uncheck to remove capture highlight
            if is_valid:
                button.setText(hotkey.upper())
                key_name = self.capturing_for_control
                if key_name not in self.keybinds:
                    self.keybinds[key_name] = {}
                self.keybinds[key_name]["hotkey"] = hotkey
            else: # Capture was cancelled
                # Revert to the default key for this control
                key_name = self.capturing_for_control
                default_key = self._get_default_key_for_control(key_name)
                button.setText(default_key.upper())
                if key_name in self.keybinds:
                    # Set the hotkey back to the default in the data model
                    self.keybinds[key_name]["hotkey"] = default_key
        else: # We were capturing for a message hotkey
            self.automation_tab.hotkey_capture_btn.setText(hotkey if is_valid else "Click to set")

        # Re-register all application hotkeys now that capture is complete.
        self.register_global_hotkeys()
        self.register_keybind_hotkeys()
        # Allow a new capture to be started. This is the crucial step.
        self.is_capturing_hotkey = False

    def on_capture_thread_finished(self):
        """Clears references to the hotkey capture thread and worker."""
        self.capture_thread = None
        self.capture_worker = None
        self.capturing_for_control = None # Clear the control reference

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
        """Sends a chat message if the game is active. This is called from a background thread."""
        if self.is_sending_message: return
        try:
            if win32gui.GetForegroundWindow() != win32gui.FindWindow(None, self.game_title): return
        except Exception: return

        self.is_sending_message = True
        self.send_message_signal.emit(message)

    def _main_thread_send_chat_message(self, message: str):
        """This slot runs on the main GUI thread to safely interact with the clipboard and pyautogui."""
        if not pyautogui: return

        try:
            clipboard = QApplication.clipboard()
            original_clipboard = clipboard.text()
            clipboard.setText(message)

            pyautogui.press('enter')
            QTimer.singleShot(50, lambda: pyautogui.hotkey('ctrl', 'v'))
            QTimer.singleShot(100, lambda: pyautogui.press('enter'))

            def cleanup():
                clipboard.setText(original_clipboard)
                self.is_sending_message = False
            QTimer.singleShot(200, cleanup)

        except Exception as e:
            QMessageBox.critical(self, "Chat Error", f"An error occurred while sending the message: {e}")
            self.is_sending_message = False

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
        self.keybinds = self.settings_manager.get("keybinds", {})
        self.custom_title_image_path = self.settings_manager.get("custom_title_image_path", "")
        self.font_family = self.settings_manager.get("font_family", "Segoe UI")
        self.font_size = self.settings_manager.get("font_size", 11)

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

    def apply_font_settings(self):
        """Applies the selected font and size to the entire application."""
        self.font_family = self.font_combo.currentFont().family()
        self.font_size = self.font_size_spinbox.value()
        
        new_font = QFont(self.font_family, self.font_size)
        QApplication.instance().setFont(new_font)
        
        # Re-applying the theme will now correctly pick up the new application font
        self.theme_manager.reapply_current_theme()

    def reset_font_settings(self):
        """Resets the font to the application default and applies it."""
        # These are the default values from the SettingsManager
        self.font_combo.setCurrentFont(QFont(self.settings_manager.defaults["font_family"]))
        self.font_size_spinbox.setValue(self.settings_manager.defaults["font_size"])
        # Apply the reset
        self.apply_font_settings()

    def reset_keybinds(self):
        self.quickcast_manager.reset_keybinds()

    # Keybinds / Quickcast
    def apply_keybind_settings(self):
        self.quickcast_manager.apply_keybind_settings()

    def on_keybind_button_clicked(self, button: QPushButton, name: str):
        self.quickcast_manager.on_keybind_button_clicked(button, name)

    def on_keybind_setting_changed(self, setting_name: str):
        self.quickcast_manager.on_keybind_setting_changed(setting_name)

    def toggle_quickcast(self, name: str):
        self.quickcast_manager.toggle_quickcast(name)

    def execute_keybind(self, name: str, hotkey: str):
        """Executes the action for a triggered keybind hotkey."""
        # If this function is already running, exit to prevent recursion from SendInput.
        if self.is_executing_keybind:
            return

        
        try:
            self.is_executing_keybind = True
            print(f"\n[DEBUG] execute_keybind triggered: name='{name}', hotkey='{hotkey}'")

            key_info = self.keybinds.get(name, {})
            print(f"[DEBUG] Found key_info: {key_info}")
            if not key_info: return
            

            # Check if the corresponding setting is enabled
            category = name.split("_")[0] # "spell", "inv", "mouse"
            if category == "inv": category = "inventory"
            is_enabled = self.keybinds.get("settings", {}).get(category, True)
            print(f"[DEBUG] Is category '{category}' enabled? {is_enabled}")
            if not is_enabled:
                return # Setting is disabled, let the keypress go through
        finally:
            # Always reset the flag, even if an error occurs.
            self.is_executing_keybind = False

    def get_keybind_settings_from_ui(self):
        """Gathers keybind settings from the UI controls for saving."""
        return self.quickcast_manager.get_keybind_settings_from_ui()


    def apply_saved_recipes(self):
        """Loads and populates the in-progress recipes from settings."""
        saved_recipes = self.settings_manager.get("in_progress_recipes", [])
        for recipe_name in saved_recipes:
            self.items_manager._add_recipe_by_name(recipe_name)

    # Character loading
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

    def on_f3_pressed(self):
        """Handler for the F3 hotkey press."""
        self.character_load_manager.load_selected_character()
        self.showMinimized()

    # Tab select logic
    def on_main_tab_selected(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        tab_name = self.tab_names[index]
        if tab_name == "Items" and not self.items_manager.item_database.all_items_data:
            self.items_manager.switch_items_sub_tab(0) # Lazy load
        elif tab_name == "Placeholder":
            pass # Nothing to do for the placeholder tab
        elif tab_name == "Lobbies" and not self.lobby_manager.lobbies_tab.lobbies_table.rowCount():
            self.lobby_manager.refresh_lobbies() # Refresh when tab is first viewed
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

        # Register global F2 for toggling Quickcast (emit Qt signal to keep UI thread-safe)
        # We handle this one manually to implement a debounce for key-holding.
        def on_f2_press(e):
            if e.event_type == keyboard.KEY_DOWN and not self.f2_key_down:
                self.f2_key_down = True
                self.quickcast_toggle_signal.emit()
            elif e.event_type == keyboard.KEY_UP:
                self.f2_key_down = False

        # Unhook any previous F2 handler to be safe
        if 'f2' in self.hotkey_ids:
            try: keyboard.remove_hotkey(self.hotkey_ids['f2']) 
            except (KeyError, ValueError): pass
        
        try:
            self.hotkey_ids['f2'] = keyboard.hook_key('f2', on_f2_press, suppress=True)
        except Exception as e:
            print(f"Failed to hook F2 key: {e}")
        # Register all custom message hotkeys
        for hotkey, message in self.message_hotkeys.items():
            self.register_single_hotkey(hotkey, message) # type: ignore

    def register_keybind_hotkeys(self):
        """
        Safely unregisters and re-registers all keybind-specific hotkeys.

        This method iterates through a copy of the tracked hotkey IDs and
        selectively removes only those that are not global or message hotkeys.
        It uses a try-except block to prevent crashes if a hotkey is already
        unregistered, ensuring the application remains stable.
        """
        self.quickcast_manager.register_keybind_hotkeys()

    def register_single_hotkey(self, hotkey: str, message: str):
        """Helper to register a single message hotkey."""
        try:
            hk_id = keyboard.add_hotkey(hotkey, lambda h=hotkey, msg=message: self.send_chat_message(h, msg), suppress=False) # type: ignore
            self.hotkey_ids[hotkey] = hk_id
        except (ValueError, ImportError) as e:
            print(f"Failed to register hotkey '{hotkey}': {e}")

    def register_single_keybind(self, name: str, hotkey: str):
        """Helper to register a single keybind hotkey."""
        try:
            # The keyboard library does not support mouse buttons as hotkeys.
            # We prevent trying to register them.
            if "button" in hotkey.lower():
                return

            # The check for the active window is now handled inside execute_keybind.
            hk_id = keyboard.add_hotkey(hotkey, lambda n=name, h=hotkey: self.execute_keybind(n, h), suppress=False)
            self.hotkey_ids[name] = hk_id
        except (ValueError, ImportError, KeyError) as e:
            print(f"Failed to register keybind '{hotkey}' for '{name}': {e}")

    def deactivate_ahk_script_if_running(self, inform_user=True):
        """Delegates AHK deactivation to the QuickcastManager."""
        return self.quickcast_manager.deactivate_ahk_script_if_running(inform_user)

    def toggle_ahk_quickcast(self):
        """Delegates AHK toggling to the QuickcastManager."""
        self.quickcast_manager.toggle_ahk_quickcast()
                
    def _find_ahk_path(self) -> str | None:
        """Finds the path to the AutoHotkey executable."""
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        possible_paths = [
            os.path.join(program_files, "AutoHotkey", "AutoHotkey.exe"),
            os.path.join(program_files, "AutoHotkey", "v2", "AutoHotkey.exe"),
            os.path.join(program_files, "AutoHotkey", "UX", "AutoHotkey.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        try:
            result = subprocess.run(['where', 'AutoHotkey.exe'], capture_output=True, text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
            return result.stdout.strip().split('\n')[0]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def generate_and_run_ahk_script(self):
        """Delegates AHK script generation to the QuickcastManager."""
        return self.quickcast_manager.generate_and_run_ahk_script()

    def unregister_python_hotkeys(self):
        """Delegates Python hotkey unregistration to the QuickcastManager."""
        self.quickcast_manager.unregister_python_hotkeys()

    def register_keybind_hotkeys(self):
        """
        Safely unregisters and re-registers all keybind-specific hotkeys.
        This method iterates through a copy of the tracked hotkey IDs...
        """
        self.quickcast_manager.register_keybind_hotkeys()

    def _send_vk_key(self, vk_code):
        """Sends a key press and release using a virtual-key code."""
        if not win32api or not win32con:
            return
        win32api.keybd_event(vk_code, 0, 0, 0)
        time.sleep(0)
        win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)

    def _send_vk_char(self, char: str):
        """Sends a character key press and release."""
        if not win32api or not win32con:
            return
        self._send_vk_key(ord(char.upper()))

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
        """Plays the currently selected notification sound."""
        self.play_specific_sound(self.lobby_manager.selected_sound)

    # Ensure timers are cleaned up on exit
    def closeEvent(self, event):
        """Ensures all background processes and threads are cleaned up before closing."""
        self.settings_manager.save(self) # Save all settings on exit
        self.automation_manager.stop_automation()
        keyboard.unhook_all() # Clean up all global listeners

        # Ensure the AHK process is terminated on exit
        self.quickcast_manager.deactivate_ahk_script_if_running(inform_user=False)

        event.accept()
 


if __name__ == "__main__":

    # For Windows, set an explicit AppUserModelID to ensure the taskbar icon is correct.
    if os.name == 'nt':
        myappid = 'cherrybandit.hellfirehelper.1.0' # arbitrary string
        shell32 = ctypes.windll.shell32
        shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        # Notify the shell that the file association for our icon may have changed.
        # This can help refresh the icon cache if the .exe is moved.
        SHCNE_ASSOCCHANGED = 0x08000000
        shell32.SHChangeNotify(SHCNE_ASSOCCHANGED, 0, None, None)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())