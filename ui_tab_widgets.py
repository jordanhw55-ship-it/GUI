from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTextEdit, QTableWidget, QHeaderView, QGroupBox, QFrame,
    QGridLayout, QCheckBox, QLabel, QStackedWidget, QSlider
)
from PySide6.QtCore import Qt


class CharacterLoadTab(QWidget):
    """A widget for the 'Load' tab, handling character loading UI."""
    def __init__(self, parent_window):
        super().__init__()
        # self.parent_window = parent_window # Not strictly needed if we connect signals in the main window
        self._create_widgets()
        self._create_layouts()

    def _create_widgets(self):
        """Creates all the widgets for the tab."""
        self.load_path_edit = QLineEdit()
        self.load_path_edit.setPlaceholderText("Character save path...")
        self.browse_btn = QPushButton("Browse...")
        self.reset_path_btn = QPushButton("Reset Path")

        self.load_char_btn = QPushButton("Load Character (F3)")
        self.refresh_chars_btn = QPushButton("Refresh")

        self.char_list_box = QListWidget()
        self.char_list_box.setFixedWidth(200)
        self.char_content_box = QTextEdit()
        self.char_content_box.setReadOnly(True)
        self.char_content_box.setFontFamily("Consolas")
        self.char_content_box.setFontPointSize(10)

    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QVBoxLayout(self)
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.load_path_edit)
        path_layout.addWidget(self.browse_btn)
        path_layout.addWidget(self.reset_path_btn)
        action_layout = QHBoxLayout()
        action_layout.addWidget(self.load_char_btn); action_layout.addWidget(self.refresh_chars_btn); action_layout.addStretch()
        content_layout = QHBoxLayout()
        content_layout.addWidget(self.char_list_box); content_layout.addWidget(self.char_content_box)
        main_layout.addLayout(path_layout); main_layout.addLayout(action_layout); main_layout.addLayout(content_layout)

class AutomationTab(QWidget):
    """A widget for the 'Automation' tab, handling key automation and message hotkeys."""
    def __init__(self, parent_window):
        super().__init__()
        self._create_widgets()
        self._create_layouts()

    def _create_widgets(self):
        """Creates all the widgets for the tab."""
        # --- Left Panel: Key Automation ---
        self.automation_keys_group = QGroupBox("Key Automation")
        self.automation_key_ctrls = {}
        # All keys that can be in the automation grid
        self.automationKeys = [ 
            "y", "s", "h", "a", "p", "d", "f", "t", "q", "w", "e", "r", "Complete Quest",
            "Num7", "Num8", "Num4", "Num5", "Num1", "Num2"
        ]
        for key in self.automationKeys:
            chk = QCheckBox(key.upper() if key != "Complete Quest" else "Complete Quest")
            edit = QLineEdit("15000" if key == "Complete Quest" else "500")
            edit.setFixedWidth(35)
            self.automation_key_ctrls[key] = {"chk": chk, "edit": edit}

        self.custom_action_btn = QCheckBox("Custom")
        self.custom_action_edit1 = QLineEdit("30000"); self.custom_action_edit1.setFixedWidth(35)
        self.custom_action_edit2 = QLineEdit("-save x"); self.custom_action_edit2.setFixedWidth(120)

        # Automation log box
        self.automation_log_group = QGroupBox("Automation Log")
        self.automation_log_box = QTextEdit()
        self.automation_log_box.setReadOnly(True)

        self.start_automation_btn = QPushButton("Start/F5")
        self.stop_automation_btn = QPushButton("Stop/F6")
        self.reset_automation_btn = QPushButton("Reset Automation")

        # --- Right Panel: Message Hotkeys ---
        self.msg_hotkey_group = QGroupBox("Custom Message Hotkeys")
        self.msg_hotkey_table = QTableWidget()
        self.msg_hotkey_table.setColumnCount(2)
        self.msg_hotkey_table.setHorizontalHeaderLabels(["Hotkey", "Message"])
        self.msg_hotkey_table.verticalHeader().setVisible(False)
        self.msg_hotkey_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.msg_hotkey_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.msg_hotkey_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.hotkey_capture_btn = QPushButton("Click to set")
        self.message_edit = QLineEdit()
        self.add_msg_btn = QPushButton("Add")
        self.delete_msg_btn = QPushButton("Delete")

    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QVBoxLayout(self)

        # --- Top Section (Key Automation) ---
        key_automation_layout = QVBoxLayout()

        # Main grid to hold the three new boxes
        top_level_grid = QGridLayout()
        self.automation_keys_group.setLayout(top_level_grid)
        top_level_grid.setColumnStretch(0, 2) # Main keys column takes more space
        top_level_grid.setColumnStretch(1, 1) # Numpad keys column takes less space

        # --- Box 1: Top-Left (Main Keys) ---
        main_keys_group = QGroupBox("Main Keys")
        main_keys_grid = QGridLayout(main_keys_group)
        main_keys_grid.setHorizontalSpacing(10); main_keys_grid.setVerticalSpacing(2)
        main_keys_layout_def = [
            ["y", "s", "h", "a"],
            ["p", "d", "f", "t"],
            ["q", "w", "e", "r"]
        ]
        for r, row_keys in enumerate(main_keys_layout_def):
            for c, key in enumerate(row_keys):
                if key in self.automation_key_ctrls:
                    ctrls = self.automation_key_ctrls[key]
                    pair = QHBoxLayout(); pair.setSpacing(5); pair.addWidget(ctrls["chk"]); pair.addWidget(ctrls["edit"])
                    main_keys_grid.addLayout(pair, r, c)
        top_level_grid.addWidget(main_keys_group, 0, 0)

        # --- Box 2: Top-Right (Numpad Keys) ---
        numpad_group = QGroupBox("Numpad Keys")
        numpad_grid = QGridLayout(numpad_group)
        numpad_grid.setHorizontalSpacing(10); numpad_grid.setVerticalSpacing(2)
        numpad_layout_def = [["Num7", "Num8"], ["Num4", "Num5"], ["Num1", "Num2"]]
        for r, row_keys in enumerate(numpad_layout_def):
            for c, key in enumerate(row_keys):
                if key in self.automation_key_ctrls:
                    ctrls = self.automation_key_ctrls[key]
                    pair = QHBoxLayout(); pair.setSpacing(5); pair.addWidget(ctrls["chk"]); pair.addWidget(ctrls["edit"])
                    numpad_grid.addLayout(pair, r, c)
        top_level_grid.addWidget(numpad_group, 0, 1)

        # --- Box 3: Bottom-Left (Other Actions) ---
        other_actions_group = QGroupBox("Other Actions")
        other_actions_layout = QVBoxLayout(other_actions_group)
        other_actions_layout.addLayout(self._create_control_pair(self.automation_key_ctrls["Complete Quest"]))
        other_actions_layout.addLayout(self._create_custom_action_layout())
        top_level_grid.addWidget(other_actions_group, 1, 0)

        automation_actions_layout = QHBoxLayout()
        automation_actions_layout.addWidget(self.start_automation_btn); automation_actions_layout.addWidget(self.stop_automation_btn); automation_actions_layout.addWidget(self.reset_automation_btn)

        key_automation_layout.addWidget(self.automation_keys_group)
        key_automation_layout.addLayout(automation_actions_layout)
        key_automation_layout.addWidget(QLabel("Intervals are in ms. Example: 500 = 0.5s"))

        # --- Bottom Section (Hotkeys and Log) ---
        bottom_section_layout = QHBoxLayout()

        # Custom Message Hotkeys (left part of bottom section)
        log_layout = QVBoxLayout(self.automation_log_group)
        log_layout.addWidget(self.automation_log_box)
        right_layout = QVBoxLayout(self.msg_hotkey_group)
        right_layout.addWidget(self.msg_hotkey_table)
        msg_form_layout = QGridLayout(); msg_form_layout.addWidget(QLabel("Hotkey:"), 0, 0); msg_form_layout.addWidget(self.hotkey_capture_btn, 0, 1); msg_form_layout.addWidget(QLabel("Message:"), 1, 0); msg_form_layout.addWidget(self.message_edit, 1, 1); right_layout.addLayout(msg_form_layout)
        msg_btn_layout = QHBoxLayout(); msg_btn_layout.addWidget(self.add_msg_btn); msg_btn_layout.addWidget(self.delete_msg_btn); right_layout.addLayout(msg_btn_layout)

        # Add top and bottom sections to the main vertical layout
        main_layout.addLayout(key_automation_layout)
        bottom_section_layout.addWidget(self.msg_hotkey_group, 1)
        bottom_section_layout.addWidget(self.automation_log_group, 1)
        main_layout.addLayout(bottom_section_layout, 1)

    def _create_control_pair(self, ctrls):
        """Helper to create a CheckBox + LineEdit pair layout."""
        pair_layout = QHBoxLayout(); pair_layout.setSpacing(5)
        pair_layout.addWidget(ctrls["chk"]); pair_layout.addWidget(ctrls["edit"]); pair_layout.addStretch()
        return pair_layout

    def _create_custom_action_layout(self):
        """Helper to create the custom action layout."""
        custom_layout = QHBoxLayout(); custom_layout.setSpacing(5)
        custom_layout.addWidget(self.custom_action_btn); custom_layout.addWidget(self.custom_action_edit1); custom_layout.addWidget(self.custom_action_edit2); custom_layout.addStretch()
        return custom_layout

class QuickcastTab(QWidget):
    """A widget for the 'Quickcast' tab, for setting up key quickcasts."""
    def __init__(self, parent):
        super().__init__(parent)
        self.key_buttons = {}
        self.setting_checkboxes = {}

        self._create_widgets()
        self._create_layouts()

    def _create_widgets(self):
        """Creates all the widgets for the tab."""
        self.remap_spells_group = QGroupBox("Remap Spells")

        # --- Settings ---
        self.settings_group = QGroupBox("Settings")
        self.reset_keybinds_btn = QPushButton("Reset Keybinds") 
        self.reset_keybinds_btn.setObjectName("ResetKeybindsButton") # For styling
        
        self.activate_quickcast_btn = QPushButton("Activate Quickcast")

        # --- AHK Installation ---
        self.install_ahk_group = QGroupBox("Install AutoHotkey v2")
        self.install_ahk_cmd_btn = QPushButton("Install via CMD")
        self.install_ahk_web_btn = QPushButton("Install from Website")

    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QHBoxLayout(self)
        
        # --- Main Remapping Panel (Left) ---
        remap_panel = QWidget()
        remap_layout = QVBoxLayout(remap_panel)
        remap_layout.addWidget(self.remap_spells_group)
        main_layout.addWidget(remap_panel, 2) # Give it more space

        spells_grid = QGridLayout(self.remap_spells_group)

        # Define the layout row by row
        layout_definition = [
            ["Y", "S", "H", "A", "Numpad 7", "Numpad 8"],
            ["P", "D", "F", "T", "Numpad 4", "Numpad 5"],
            ["Q", "W", "E", "R", "Numpad 1", "Numpad 2"]
        ]

        for row_idx, row_keys in enumerate(layout_definition):
            for col_idx, key in enumerate(row_keys):
                # Use a consistent naming scheme for the keybind dictionary
                key_id = f"spell_{key}"
                # Create the button
                self.key_buttons[key_id] = self._create_key_button(key)
                # Add it to the grid
                spells_grid.addWidget(self.key_buttons[key_id], row_idx, col_idx)
        # --- Settings Panel (Right) ---
        settings_panel = QWidget()
        settings_panel_layout = QVBoxLayout(settings_panel)
        settings_panel_layout.addWidget(self.settings_group)
        settings_panel_layout.addStretch()
        settings_panel_layout.addWidget(self.install_ahk_group)
        main_layout.addWidget(settings_panel, 1)

        settings_v_layout = QVBoxLayout(self.settings_group)
        settings_v_layout.addWidget(self.activate_quickcast_btn)
        settings_v_layout.addWidget(self.reset_keybinds_btn)

        install_ahk_layout = QVBoxLayout(self.install_ahk_group)
        install_ahk_layout.addWidget(self.install_ahk_cmd_btn)
        install_ahk_layout.addWidget(self.install_ahk_web_btn)


    def _create_key_button(self, default_text: str) -> QPushButton:
        """Helper to create a standard key button."""
        button = QPushButton(default_text)
        button.setFixedSize(60, 60)
        button.setCheckable(True) # To show "capture" state
        return button

    def reset_ui_to_defaults(self):
        """Resets all buttons and checkboxes in this tab to their default visual state."""
        # This method is now empty as there are no UI elements to reset to a default state
        # beyond what is handled by apply_keybind_settings in the main window.
        pass

class ItemsTab(QWidget):
    """A widget for the 'Items' tab, including sub-tabs for different item categories."""
    def __init__(self, parent_window):
        super().__init__()
        self._create_widgets()
        self._create_layouts()

    def _create_widgets(self):
        """Creates all the widgets for the tab."""
        self.sub_tabs_widget = QWidget()
        self.sub_tabs_layout = QHBoxLayout(self.sub_tabs_widget)
        self.sub_tabs_layout.setContentsMargins(0,0,0,0)
        self.sub_tabs_layout.setSpacing(5)
        self.item_tab_buttons = {}
        # Separate "Recipes" from the main item tabs
        item_tab_names = ["All Items", "Drops", "Raid Items", "Vendor Items"]
        for i, name in enumerate(item_tab_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            self.item_tab_buttons[i] = btn
            self.sub_tabs_layout.addWidget(btn)
        self.recipes_btn = QPushButton("Recipes"); self.recipes_btn.setCheckable(True)
        self.item_tab_buttons[len(item_tab_names)] = self.recipes_btn # Add it as the last button logically

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")

        # Main stack for switching between item tables and recipe tracker
        self.main_stack = QStackedWidget()

        # --- Widget for the item tables ---
        self.item_tables_widget = QWidget()
        item_tables_layout = QVBoxLayout(self.item_tables_widget)
        item_tables_layout.setContentsMargins(0,0,0,0)
        self.item_tables_stack = QStackedWidget()
        self.all_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.drops_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.raid_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.vendor_table = self._create_item_table(["Item", "Unit", "Location"])
        self.item_tables_stack.addWidget(self.all_items_table)
        self.item_tables_stack.addWidget(self.drops_table)
        self.item_tables_stack.addWidget(self.raid_items_table)
        self.item_tables_stack.addWidget(self.vendor_table)
        item_tables_layout.addWidget(self.item_tables_stack)

        # --- Widget for the recipe tracker ---
        self.recipe_tracker_widget = QWidget()
        recipe_tracker_layout = QVBoxLayout(self.recipe_tracker_widget)
        recipe_tracker_layout.setContentsMargins(0,0,0,0)
        
        self.available_recipes_list = QListWidget()
        self.add_recipe_btn = QPushButton("Add ->")
        self.remove_recipe_btn = QPushButton("<- Remove")
        self.reset_recipes_btn = QPushButton("Reset")
        self.in_progress_recipes_list = QListWidget()
        self.materials_table = QTableWidget()
        self.materials_table.setColumnCount(5)
        self.materials_table.setHorizontalHeaderLabels(["Material", "#", "Unit", "Location", "Checked"])
        self.materials_table.setColumnHidden(4, True)
        self.materials_table.verticalHeader().setVisible(False)
        self.materials_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.materials_table.setSortingEnabled(True)

        recipe_top_layout = QHBoxLayout()
        recipes_list_layout = QVBoxLayout(); recipes_list_layout.addWidget(self.available_recipes_list)
        add_remove_layout = QVBoxLayout(); add_remove_layout.addStretch(); add_remove_layout.addWidget(self.add_recipe_btn); add_remove_layout.addWidget(self.remove_recipe_btn); add_remove_layout.addWidget(self.reset_recipes_btn); add_remove_layout.addStretch()
        recipe_top_layout.addLayout(recipes_list_layout); recipe_top_layout.addLayout(add_remove_layout); recipe_top_layout.addWidget(self.in_progress_recipes_list)
        recipe_tracker_layout.addLayout(recipe_top_layout); recipe_tracker_layout.addWidget(self.materials_table)
        recipe_tracker_layout.setStretchFactor(recipe_top_layout, 1); recipe_tracker_layout.setStretchFactor(self.materials_table, 3)

        # Add both main widgets to the main stack
        self.main_stack.addWidget(self.item_tables_widget)
        self.main_stack.addWidget(self.recipe_tracker_widget)

    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QVBoxLayout(self)
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.sub_tabs_widget)
        controls_layout.addStretch()
        controls_layout.addWidget(self.recipes_btn) # Add recipes button before search
        controls_layout.addWidget(self.search_box)
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.main_stack)

    def _create_item_table(self, headers: list) -> QTableWidget:
        """Helper to create a standard QTableWidget for items."""
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, len(headers)):
            table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        table.setSortingEnabled(True)
        return table

class LobbiesTab(QWidget):
    """A widget for the 'Lobbies' tab, for browsing game lobbies."""
    def __init__(self, parent_window):
        super().__init__()
        self._create_widgets()
        self._create_layouts()

    def _create_widgets(self):
        """Creates all the widgets for the tab."""
        self.lobby_search_bar = QLineEdit()
        self.lobby_search_bar.setPlaceholderText("Search by name or map…")
        self.refresh_button = QPushButton("Refresh")
        self.toggle_watchlist_btn = QPushButton("Show/Hide Watchlist")

        self.lobbies_table = QTableWidget()
        self.lobbies_table.setColumnCount(4)
        self.lobbies_table.setHorizontalHeaderLabels(["Name", "Map", "Players", "Host"])
        self.lobbies_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.lobbies_table.verticalHeader().setVisible(False)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lobbies_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.lobbies_table.setSortingEnabled(True)

        self.watchlist_group = QGroupBox("Watchlist")
        self.watchlist_widget = QListWidget()
        self.watchlist_input = QLineEdit()
        self.watchlist_input.setPlaceholderText("Add keyword...")
        self.add_watchlist_button = QPushButton("Add")
        self.remove_watchlist_button = QPushButton("Remove")

        # Sound controls
        self.ping_buttons = {
            "ping1.mp3": QPushButton("Ping 1"),
            "ping2.mp3": QPushButton("Ping 2"),
            "ping3.mp3": QPushButton("Ping 3"),
        }
        for btn in self.ping_buttons.values():
            btn.setCheckable(True)

        self.lobby_placeholder_checkbox = QCheckBox("Play Sound When Game Found")
        self.test_sound_button = QPushButton("Test Sound")

        # Volume slider
        self.volume_label = QLabel("Volume:")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)



    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QVBoxLayout(self)
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.lobby_search_bar, 1)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addWidget(self.toggle_watchlist_btn)
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.lobbies_table)
        main_layout.addWidget(self.watchlist_group) # Initially visible, can be hidden

        watchlist_layout = QVBoxLayout(self.watchlist_group)
        watchlist_layout.addWidget(self.watchlist_widget)
        watchlist_controls_layout = QHBoxLayout()
        watchlist_controls_layout.addWidget(self.watchlist_input)
        watchlist_controls_layout.addWidget(self.add_watchlist_button)
        watchlist_controls_layout.addWidget(self.remove_watchlist_button)
        watchlist_layout.addLayout(watchlist_controls_layout)

        # Sound controls layout
        ping_buttons_layout = QHBoxLayout()
        for btn in self.ping_buttons.values():
            ping_buttons_layout.addWidget(btn)
        watchlist_layout.addLayout(ping_buttons_layout)

        sound_options_layout = QHBoxLayout()
        sound_options_layout.addWidget(self.lobby_placeholder_checkbox)
        sound_options_layout.addWidget(self.test_sound_button)
        watchlist_layout.addLayout(sound_options_layout)

        volume_layout = QHBoxLayout()
        volume_layout.addWidget(self.volume_label)
        volume_layout.addWidget(self.volume_slider)
        watchlist_layout.addLayout(volume_layout)