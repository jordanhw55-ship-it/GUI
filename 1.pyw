import sys
import json
import os
import re
import subprocess
from typing import List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QStackedWidget, QGridLayout, QMessageBox, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QListWidget, QGroupBox, QFileDialog, QTextEdit, QFrame,
    QListWidgetItem, QColorDialog, QCheckBox, QSlider, QFontComboBox, QSpinBox
)
from PySide6.QtCore import Signal, Qt, QThread, QTimer, QUrl, QPoint
from PySide6.QtGui import QMouseEvent, QColor, QIntValidator, QFont, QPalette, QAction, QDesktopServices, QShortcut, QKeySequence, QIcon, QPixmap, QPainter
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
from WC3_UI import WC3UITab
from key_translator import normalize_to_canonical, to_keyboard_lib, to_pyautogui
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

class FlatStackedWidget(QStackedWidget):
    """
    A QStackedWidget subclass that overrides the paint event to ensure no borders
    or frames are ever drawn by the style engine. This is a definitive fix for
    phantom border/seam rendering artifacts.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFrameShape(QFrame.NoFrame)
        self.setFrameShadow(QFrame.Plain)
        self.setLineWidth(0)
        self.setMidLineWidth(0)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #252526; border: none;")

    def paintEvent(self, event):
        # Explicitly fill the background to prevent any theme bleed-through.
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(self.backgroundRole()))
        # The original paintEvent is not called to prevent it from drawing a frame.

class AlignedTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, alignment=Qt.AlignmentFlag.AlignCenter):
        super().__init__(text)
        self.setTextAlignment(alignment)

class NavButton(QPushButton):
    """A custom button with a separate icon and text label for precise alignment."""
    def __init__(self, icon: str, text: str):
        super().__init__()
        # Store colors to manage hover state manually
        self.default_bg = "transparent"
        self.hover_bg = "#00A8E8" # Teal accent
        self.checked_bg = "#007AAB" # Darker teal for checked
        self.setCheckable(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(25, 0, 15, 0) # Increased left padding for more space
        layout.setSpacing(10) # Space between icon and text

        self.icon_label = QLabel(icon)
        self.icon_label.setFixedWidth(20) # Fixed width for icon alignment
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Allow parent to handle hover
        # self.icon_label.setStyleSheet("background-color: transparent; border: none;") # Removed to allow global stylesheet to work

        self.text_label = QLabel(text)
        # self.text_label.setStyleSheet("background-color: transparent; border: none;") # Removed to allow global stylesheet to work
        self.text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) # Allow parent to handle hover

        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        layout.addStretch()
        
    def setChecked(self, checked: bool):
        """Override setChecked to style the internal labels."""
        super().setChecked(checked)
        # The styling is now handled entirely by the main stylesheet for consistency,
        # so this method only needs to call the parent implementation.

class NavigationSidebar(QWidget):
    """A vertical navigation bar with buttons."""
    tab_selected = Signal(int)

    def __init__(self, tab_names: list[str]):
        super().__init__()
        self.setObjectName("NavigationSidebar")
        self.setFixedWidth(180) # Increased width for more space
        
        self.buttons: List[QPushButton] = []
        self.current_index = -1

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 19, 5, 10) # Increased left margin by 3px
        main_layout.setSpacing(5) # Increased spacing between buttons

        # Add a label at the top for the title image
        self.title_label = QLabel()
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setContentsMargins(2, 0, 0, 15) # 2px left margin to push right, 15px bottom for spacing
        main_layout.addWidget(self.title_label)
        
        # Icons using unicode characters
        # Refined, more modern-looking unicode characters
        icons = ["\U0001F4C2", "\U0001F4E6", "\u2699", "\u26A1", "\u2328", "\U0001F4E1", # Load, Items, WC3UI, Automation, Quickcast, Lobbies
                 "\u2699", "\u2753"] # Settings, Help (kept the same)
        
        # Main navigation buttons
        for i, name in enumerate(tab_names):
            if name in ["Settings", "Help"]: continue # Handle these separately
            button = NavButton(icons[i], name)
            button.clicked.connect(lambda checked, idx=i: self.set_current_index(idx))
            self.buttons.append(button)
            main_layout.addWidget(button)

        main_layout.addStretch()

        # Bottom-grouped buttons (Settings, Help)
        for i, name in enumerate(tab_names):
            if name in ["Settings", "Help"]:
                button = NavButton(icons[i], name)
                button.clicked.connect(lambda checked, idx=i: self.set_current_index(idx))
                self.buttons.append(button)
                main_layout.addWidget(button)

        # Add the "Upgrade now" button at the bottom
        self.upgrade_button = QPushButton("Upgrade now")
        self.upgrade_button.setObjectName("UpgradeButton")
        # self.upgrade_button.clicked.connect(self.on_upgrade_clicked) # Add a function if needed
        main_layout.addWidget(self.upgrade_button)

    def set_current_index(self, index: int):
        if self.current_index != -1:
            self.buttons[self.current_index].setChecked(False)
        self.buttons[index].setChecked(True)
        self.current_index = index
        self.tab_selected.emit(index)

    def setTitleImage(self, image_path: str | None):
        """Sets the pixmap for the title label."""
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # Scale pixmap to fit the sidebar width minus some padding
            self.title_label.setPixmap(pixmap.scaledToWidth(self.width() - 20, Qt.TransformationMode.SmoothTransformation))
        else:
            self.title_label.clear() # Clear the image if path is invalid

class SimpleWindow(QMainWindow):
    start_automation_signal = Signal()
    stop_automation_signal = Signal()
    send_message_signal = Signal(str)
    load_character_signal = Signal()
    quickcast_toggle_signal = Signal()

    def __init__(self):
        super().__init__()
        self.navigation_sidebar = None

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
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74, 'f6': 0x75, 'f7': 0x76,
            'f8': 0x77, 'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
            'num 0': 0x60,
            'num 1': 0x61,
            'num 2': 0x62,
            'num 3': 0x63,
            'num 4': 0x64,
            'num 5': 0x65,
            'num 6': 0x66,
            'num 7': 0x67,
            'num 8': 0x68,
            'num 9': 0x69,
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

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.resize(950, 700)

        self.setWindowTitle("Hellfire Helper")
        self.setWindowIcon(QIcon(os.path.join(get_base_path(), "contents", "icon.ico"))) # Set the application icon
        self.apply_loaded_settings() # Load settings before creating UI elements that depend on them
        self.setStyleSheet(self.get_new_dark_style())
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

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_widget = QWidget()
        main_widget.setObjectName("MainWidget") # Give the central widget a name for styling
        # Ensure the central widget paints its background fully to prevent seams.
        main_widget.setAttribute(Qt.WA_StyledBackground, True)
        main_widget.setAutoFillBackground(True)
        main_widget.setLayout(main_layout) # This will be the central widget's layout
        self.setCentralWidget(main_widget)

        # --- New Main Layout Structure ---
        content_widget = QWidget()
        # Force styled background to prevent theme bleed-through
        content_widget.setAttribute(Qt.WA_StyledBackground, True)
        content_widget.setAutoFillBackground(True)        
        content_widget.setAttribute(Qt.WA_OpaquePaintEvent, True)
        content_widget.setObjectName("ContentWidget") # For specific styling
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0) # Zero out margins to prevent seams
        content_layout.setSpacing(0)

        # --- New Integrated Window Controls ---
        window_controls_layout = QHBoxLayout()
        window_controls_layout.addStretch() # Push buttons to the right
        min_button = QPushButton("–"); min_button.setFixedSize(30, 25); min_button.clicked.connect(self.showMinimized)
        close_button = QPushButton("X"); close_button.setFixedSize(30, 25); close_button.clicked.connect(self.close)
        min_button.setObjectName("WindowControlButton")
        close_button.setObjectName("WindowControlButton")
        window_controls_layout.addWidget(min_button)
        window_controls_layout.addWidget(close_button)
        content_layout.addLayout(window_controls_layout)
        
        # Use the custom FlatStackedWidget to guarantee no borders are drawn.
        self.stacked_widget = FlatStackedWidget()
        content_layout.addWidget(self.stacked_widget)

        # Sidebar Navigation
        self.tab_names = ["Load", "Items", "WC3 UI", "Automation", "Quickcast", "Lobbies", "Settings", "Help"]
        self.navigation_sidebar = NavigationSidebar(self.tab_names)
        # Force styled background to prevent theme bleed-through
        self.navigation_sidebar.setAttribute(Qt.WA_StyledBackground, True)
        self.navigation_sidebar.setAutoFillBackground(True)
        
        # Add a dedicated separator widget instead of using a CSS border to avoid rendering artifacts.
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setObjectName("SidebarSeparator")

        main_layout.addWidget(self.navigation_sidebar)
        main_layout.addWidget(separator)
        main_layout.addWidget(content_widget, 1) # Add content widget with stretch factor        
        self.navigation_sidebar.tab_selected.connect(self.stacked_widget.setCurrentIndex)

        # Load tab
        self.load_tab = CharacterLoadTab(self); self.stacked_widget.addWidget(self.load_tab)
        self.character_load_manager = CharacterLoadManager(self)
        self.load_tab.browse_btn.setObjectName("SecondaryButton")
        # Items tab
        self.item_database = ItemDatabase()
        self.items_tab = ItemsTab(self)
        self.stacked_widget.addWidget(self.items_tab)

        # Force all pages in the stacked widget to have a styled, opaque background
        # to prevent any transparency or theme bleed-through at the edges.
        for i in range(self.stacked_widget.count()):
            page = self.stacked_widget.widget(i)
            page.setAttribute(Qt.WA_StyledBackground, True)
            page.setAutoFillBackground(True)

        # Initialize the ItemsManager to handle all logic for the Items tab
        self.items_manager = ItemsManager(self)
        self.items_manager.switch_items_sub_tab(0)

        # WC3 UI Tab
        self.wc3_ui_tab = WC3UITab(self)
        self.stacked_widget.addWidget(self.wc3_ui_tab)

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
        self.lobbies_tab.refresh_button.setObjectName("SecondaryButton")

        # Settings tab (themes + custom theme picker)
        settings_tab_content = QWidget() # This will be the "Settings" tab
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

        # Add a reset button to the settings tab
        reset_group = QGroupBox("Application Reset")
        reset_layout = QVBoxLayout(reset_group)
        reset_warning = QLabel("This will reset all application settings to their defaults.")
        self.reset_gui_button = QPushButton("Reset Application")
        self.reset_gui_button.setObjectName("DangerButton") # For specific styling
        reset_layout.addWidget(reset_warning)
        reset_layout.addWidget(self.reset_gui_button)
        settings_layout.addWidget(reset_group, row_below + 2, 0, 1, 4)
        self.reset_gui_button.clicked.connect(self.confirm_reset)

        # New Help Tab
        help_tab = self.create_help_tab()
        self.stacked_widget.addWidget(help_tab)

        # Finalize

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
        self.navigation_sidebar.set_current_index(self.last_tab_index)
        
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

    def get_new_dark_style(self):
        """Returns the CCleaner-inspired dark theme stylesheet."""
        return """
            QWidget {
                background-color: #1e1e1e; /* Deep charcoal */
                color: #E6E6E6; /* Brighter Off-white for better readability */
                font-family: "Segoe UI", Arial, sans-serif;
            }
            QMainWindow {
                background-color: #252526; /* Set the main window background color */
            }
            QWidget#MainWidget {
                background-color: #252526;
            }
            QWidget#MainWidget {
                background-color: transparent; /* Allow QMainWindow's background to show through */
            }
            QPushButton#WindowControlButton {
                background-color: transparent;
                border: none;
                color: #d4d4d4;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton#WindowControlButton:hover {
                background-color: #E81123; /* Brighter Red for close hover */
            }
            /* The main content area to the right of the sidebar */
            QWidget#ContentWidget {
                background-color: #252526; /* Slightly lighter charcoal for the content panel */
                background-color: #252526;
                border: none;
            }
            #NavigationSidebar {
                background-color: #2C3033; /* CCleaner sidebar color */
                border-right: none; /* Replaced with a dedicated separator widget */
            }
            /* Style for the new separator widget */
            QFrame#SidebarSeparator {
                background-color: #43474A;
            }
            #NavigationSidebar QPushButton {
                background-color: transparent;
                border: none;
                outline: none; /* Explicitly remove outline */
                color: #D1D3D4;
                padding: 12px 15px; /* Increased left padding to move text right */
                text-align: left;
                font-size: 15px;
                border-left: 3px solid transparent;
            }
            /* Default state for labels inside the nav buttons */
            #NavigationSidebar QPushButton QLabel {
                background-color: transparent;
                border: none;
                outline: none; /* Explicitly remove outline */
                color: #D1D3D4;
            }
            #NavigationSidebar QPushButton:checked {
                color: #FFFFFF; /* White text for active item */
                font-weight: bold;
                background-color: #007AAB; /* Use a slightly darker accent for checked */
                border-left: 3px solid #00A8E8; /* Keep the bright accent border */
            }
            /* Style the text and icon inside the checked button */
            #NavigationSidebar QPushButton:checked QLabel {
                color: #FFFFFF;
                font-weight: bold;
                background-color: transparent;
            }
            #UpgradeButton {
                background-color: #F05E16; /* Orange CTA */
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 4px;
                margin: 10px 5px;
            }
            #UpgradeButton:hover {
                background-color: #FF7833;
            }
            QPushButton {
                background-color: transparent; /* Fade into background */
                color: #f0f0f0;
                border: 1px solid transparent; /* Hidden by default */
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3c3c3c; /* Reveal on hover */
                border-color: #555555; /* Show border on hover */
            }
            /* Secondary buttons have a visible border but no fill */
            QPushButton#SecondaryButton {
                background-color: transparent;
                border: 1px solid #555555;
            }
            QPushButton#SecondaryButton:hover {
                background-color: #3c3c3c;
                border-color: #666666;
            }
            QPushButton#PrimaryButton {
                background-color: #007AAB; /* CCleaner's blue */
            }
            QPushButton#PrimaryButton:hover {
                background-color: #0095CC;
            }
            QPushButton#DangerButton {
                background-color: #B22222; /* FireBrick */
            }
            QPushButton#DangerButton:hover {
                background-color: #c83e3e;
            }
            QGroupBox {
                border: none;
                border-radius: 4px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left; /* Position at the top-left */
                padding: 0 3px;
                color: #9D9D9D; /* Muted title color */
                margin-left: 5px;
            }
            /* Target widgets that inherit QFrame and remove their default border */
            QLineEdit, QTextEdit, QTableWidget, QListWidget, QSpinBox, QFontComboBox, QScrollArea {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                padding: 5px;
                color: #d4d4d4;
            }
            QHeaderView::section {
                background-color: #3B3F42;
                border: 1px solid #3c3c3c;
                padding: 4px;
            }
            /* This combination should finally remove any borders from the
               stacked widget container and its direct pages. */
            QStackedWidget {
                border: 0px;
            }
            QStackedWidget > QWidget {
                border: none;
            }
        """

    def get_new_dark_style_legacy(self):
        """Returns the CCleaner-inspired dark theme stylesheet."""
        return """
            QWidget {
                background-color: #1e1e1e; /* Deep charcoal */
                color: #E6E6E6; /* Brighter Off-white for better readability */
                outline: none; /* FINAL FIX: Remove the focus outline from all widgets */
                font-family: "Segoe UI", Arial, sans-serif;
            }
            QMainWindow {
                background-color: #252526; /* Set the main window background color */
            }
            QWidget#MainWidget {
                background-color: transparent; /* Allow QMainWindow's background to show through */
            }
            QPushButton#WindowControlButton {
                background-color: transparent;
                border: none;
                color: #d4d4d4;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton#WindowControlButton:hover {
                background-color: #E81123; /* Brighter Red for close hover */
            }
            /* The main content area to the right of the sidebar */
            QWidget#ContentWidget {
                background-color: #252526; /* Slightly lighter charcoal for the content panel */
                border: none;
            }
            #NavigationSidebar {
                background-color: #2C3033; /* CCleaner sidebar color */
                border-right: 1px solid #43474A;
            }
            #NavigationSidebar QPushButton {
                background-color: transparent;
                border: none;
                color: #D1D3D4;
                padding: 12px 10px;
                text-align: left;
                font-size: 15px;
                border-left: 3px solid transparent;
            }
            #NavigationSidebar QPushButton:hover {
                background-color: #333333;
            }
            #NavigationSidebar QPushButton:checked {
                color: #FFFFFF; /* White text for active item */
                font-weight: bold;
                background-color: #3B3F42;
                border-left: 3px solid #00A8E8; /* Teal accent */
            }
            #UpgradeButton {
                background-color: #F05E16; /* Orange CTA */
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 4px;
                margin: 10px 5px;
            }
            #UpgradeButton:hover {
                background-color: #FF7833;
            }
            QPushButton {
                background-color: transparent; /* Fade into background */
                color: #f0f0f0;
                border: 1px solid transparent; /* Hidden by default */
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3c3c3c; /* Reveal on hover */
                border-color: #555555; /* Show border on hover */
            }
            /* Secondary buttons have a visible border but no fill */
            QPushButton#SecondaryButton {
                background-color: transparent;
                border: 1px solid #555555;
            }
            QPushButton#SecondaryButton:hover {
                background-color: #3c3c3c;
                border-color: #666666;
            }
            QPushButton#PrimaryButton {
                background-color: #007AAB; /* CCleaner's blue */
            }
            QPushButton#PrimaryButton:hover {
                background-color: #0095CC;
            }
            QPushButton#DangerButton {
                background-color: #B22222; /* FireBrick */
            }
            QPushButton#DangerButton:hover {
                background-color: #c83e3e;
            }
            QGroupBox {
                border: none; /* No border for group boxes */
                border-radius: 4px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left; /* Position at the top-left */
                padding: 0 3px;
                color: #9D9D9D; /* Muted title color */
                margin-left: 5px;
            }
            /* Target widgets that inherit QFrame and remove their default border */
            QLineEdit, QTextEdit, QTableWidget, QListWidget, QSpinBox, QFontComboBox, QScrollArea {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 5px;
                color: #d4d4d4;
            }
            QHeaderView::section {
                background-color: #3B3F42;
                border: 1px solid #3c3c3c;
                padding: 4px;
            }
            QTableWidget::item {
                padding: 3px;
            }
        """

    def create_help_tab(self):
        """Creates the content for the new Help tab."""
        help_widget = QWidget()
        layout = QVBoxLayout(help_widget)
        
        title = QLabel("Help & Information")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
            <h3>Welcome to Hellfire Helper!</h3>
            <p>This utility is designed to assist with various tasks related to Warcraft III.</p>
            
            <h4><b>Global Hotkeys:</b></h4>
            <ul>
                <li><b>F2:</b> Activate/Deactivate Quickcast (requires AutoHotkey).</li>
                <li><b>F3:</b> Load selected character in the 'Load' tab.</li>
                <li><b>F5:</b> Start Automation.</li>
                <li><b>F6:</b> Stop Automation.</li>
            </ul>

            <h4><b>General Usage:</b></h4>
            <p>Use the navigation sidebar on the left to switch between different modules. Most settings are saved automatically when you close the application.</p>
            
            <h4><b>Quickcast (AHK):</b></h4>
            <p>The Quickcast feature requires <b>AutoHotkey v2</b> to be installed. You can find installation links in the 'Quickcast' tab. Once activated, you can remap keys and enable quickcasting, which simulates a mouse click after a key press.</p>

            <h4><b>Troubleshooting:</b></h4>
            <p>If you encounter issues, a good first step is to reset the application via the 'Settings' tab. This will restore all settings to their default values.</p>
        """)
        
        layout.addWidget(title)
        layout.addWidget(help_text)
        
        return help_widget

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
        # Allow dragging from the top 30px of the window, as long as it's not over the sidebar
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 30:
            if self.navigation_sidebar and self.navigation_sidebar.geometry().contains(event.position().toPoint()):
                return # Don't drag if clicking on the sidebar
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
        self.apply_new_style()
        self.navigation_sidebar.set_current_index(0)
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

    def apply_new_style(self):
        self.setStyleSheet(self.get_new_dark_style())
        self.theme_manager.reapply_current_theme()

    def set_title_image(self, image_name: str | None):
        """Finds the title image and tells the sidebar to display it."""
        image_path = None
        if image_name:
            # Check if it's an absolute path (from custom theme) or a relative name
            if os.path.isabs(image_name):
                if os.path.exists(image_name):
                    image_path = image_name
            else:
                # It's a relative name, look in the contents folder
                path = os.path.join(get_base_path(), "contents", image_name)
                if os.path.exists(path):
                    image_path = path

        if self.navigation_sidebar:
            self.navigation_sidebar.setTitleImage(image_path)

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
        
        print(f"[DEBUG] on_hotkey_captured - Raw: '{hotkey}'")
        is_capturing_numpad = self.capturing_for_control and "numpad" in self.capturing_for_control.lower()
        # Normalize the captured key to the canonical internal format (e.g., "numpad 7")
        canonical_hotkey = normalize_to_canonical(hotkey, is_capturing_numpad)
        print(f"[DEBUG] on_hotkey_captured - Normalized to canonical: '{canonical_hotkey}'")

        # If we were capturing for a keybind button, update it
        if self.capturing_for_control:
            button = self.quickcast_tab.key_buttons[self.capturing_for_control]
            button.setChecked(False) # Uncheck to remove capture highlight
            if is_valid:
                button.setText(canonical_hotkey.upper())
                key_name = self.capturing_for_control
                if key_name not in self.keybinds:
                    self.keybinds[key_name] = {}
                self.keybinds[key_name]["hotkey"] = canonical_hotkey
            else: # Capture was cancelled
                # Revert to the default key for this control
                key_name = self.capturing_for_control
                default_key = self._get_default_key_for_control(key_name)
                button.setText(default_key.upper())
                if key_name in self.keybinds:
                    # Set the hotkey back to the default in the data model
                    self.keybinds[key_name]["hotkey"] = default_key
        else: # We were capturing for a message hotkey
            self.automation_tab.hotkey_capture_btn.setText(canonical_hotkey if is_valid else "Click to set")

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

        # --- CRITICAL FIX: Normalize all loaded keybinds on startup ---
        # This ensures that any invalid formats (e.g., "numpad7") saved in settings.json
        # are corrected to the canonical format ("numpad 7") before they are used.
        if self.keybinds:
            print("[INFO] Normalizing loaded keybinds...")
            for name, key_info in self.keybinds.items():
                if "hotkey" in key_info:
                    is_numpad_control = "numpad" in name.lower()
                    key_info["hotkey"] = normalize_to_canonical(key_info["hotkey"], is_numpad_control)

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

            # Translate from canonical to the format the 'keyboard' library expects
            lib_hotkey = to_keyboard_lib(hotkey)

            # The check for the active window is now handled inside execute_keybind.
            hk_id = keyboard.add_hotkey(lib_hotkey, lambda n=name, h=hotkey: self.execute_keybind(n, h), suppress=False)
            self.hotkey_ids[name] = hk_id
        except (ValueError, ImportError, KeyError) as e:
            print(f"Failed to register keybind '{lib_hotkey}' for '{name}': ({e.__class__.__name__}, {e})")

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

    # Enable High DPI scaling for better rendering on scaled displays.
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    # Set the style to Fusion for more predictable cross-platform rendering.
    app.setStyle("Fusion") 
    window = SimpleWindow()
    window.show()
    sys.exit(app.exec())