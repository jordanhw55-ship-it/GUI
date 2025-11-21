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
        self.automationKeys = ["q", "w", "e", "r", "d", "f", "t", "z", "x", "Complete Quest"]
        for key in self.automationKeys:
            chk = QCheckBox(key.upper() if key != "Complete Quest" else "Complete Quest")
            edit = QLineEdit("15000" if key == "Complete Quest" else "500")
            edit.setFixedWidth(70)
            self.automation_key_ctrls[key] = {"chk": chk, "edit": edit}

        self.custom_action_btn = QCheckBox("Custom Action")
        self.custom_action_edit1 = QLineEdit("30000"); self.custom_action_edit1.setFixedWidth(70)
        self.custom_action_edit2 = QLineEdit("-save x")

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
        main_layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        automation_grid = QGridLayout()
        row, col = 0, 0
        for key in self.automationKeys:
            ctrls = self.automation_key_ctrls[key]
            automation_grid.addWidget(ctrls["chk"], row, col * 2); automation_grid.addWidget(ctrls["edit"], row, col * 2 + 1)
            col += 1;
            if col > 1: col, row = 0, row + 1
        custom_action_layout = QHBoxLayout(); custom_action_layout.addWidget(self.custom_action_btn); custom_action_layout.addWidget(self.custom_action_edit1); custom_action_layout.addWidget(self.custom_action_edit2)
        automation_grid.addLayout(custom_action_layout, row, 0, 1, 4); self.automation_keys_group.setLayout(automation_grid)
        automation_actions_layout = QHBoxLayout()
        automation_actions_layout.addWidget(self.start_automation_btn); automation_actions_layout.addWidget(self.stop_automation_btn); automation_actions_layout.addWidget(self.reset_automation_btn)
        log_layout = QVBoxLayout(self.automation_log_group)
        log_layout.addWidget(self.automation_log_box)
        left_layout.addWidget(self.automation_keys_group);
        left_layout.addLayout(automation_actions_layout)
        left_layout.addWidget(QLabel("Intervals are in ms. Example: 500 = 0.5s"))
        left_layout.addWidget(self.automation_log_group)
        left_layout.setStretchFactor(self.automation_log_group, 1) # Make the log group expand
        right_layout = QVBoxLayout(self.msg_hotkey_group)
        right_layout.addWidget(self.msg_hotkey_table)
        msg_form_layout = QGridLayout(); msg_form_layout.addWidget(QLabel("Hotkey:"), 0, 0); msg_form_layout.addWidget(self.hotkey_capture_btn, 0, 1); msg_form_layout.addWidget(QLabel("Message:"), 1, 0); msg_form_layout.addWidget(self.message_edit, 1, 1); right_layout.addLayout(msg_form_layout)
        msg_btn_layout = QHBoxLayout(); msg_btn_layout.addWidget(self.add_msg_btn); msg_btn_layout.addWidget(self.delete_msg_btn); right_layout.addLayout(msg_btn_layout)
        left_panel = QWidget(); left_panel.setLayout(left_layout)
        main_layout.addWidget(left_panel, 1); main_layout.addWidget(self.msg_hotkey_group, 1)


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
        # --- Spell Remapping ---
        self.remap_spells_group = QGroupBox("Remap Spells")
        self.original_spells_group = QGroupBox("Original")
        self.new_spells_group = QGroupBox("New")

        # --- Inventory Remapping ---
        self.remap_inventory_group = QGroupBox("Remap Inventory")

        # --- Mouse Remapping ---
        self.remap_mouse_group = QGroupBox("Remap Mouse")

        # --- Settings ---
        self.settings_group = QGroupBox("Settings")
        self.setting_checkboxes['spells'] = QCheckBox("Remap Spells")
        self.setting_checkboxes['inventory'] = QCheckBox("Remap Inventory")
        self.setting_checkboxes['mouse'] = QCheckBox("Remap Mouse")
        self.reset_keybinds_btn = QPushButton("Reset Keybinds")

    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QHBoxLayout(self)
        left_panel = QWidget()
        right_panel = QWidget()
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(right_panel, 1)

        # --- Left Panel ---
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(self.remap_spells_group)

        spells_layout = QHBoxLayout(self.remap_spells_group)
        spells_layout.addWidget(self.original_spells_group)
        spells_layout.addWidget(self.new_spells_group)

        original_grid = QGridLayout(self.original_spells_group)
        new_grid = QGridLayout(self.new_spells_group)

        spell_keys = ["M", "S", "H", "A", "P", "D", "T", "F", "Q", "W", "E", "R"]
        for i, key in enumerate(spell_keys):
            row, col = i // 4, i % 4
            # Original key (just a label)
            original_label = QLabel(key)
            original_label.setFixedSize(60, 60)
            original_label.setAlignment(Qt.AlignCenter)
            original_label.setFrameShape(QFrame.Shape.Box)
            original_grid.addWidget(original_label, row, col)
            # New key (button)
            self.key_buttons[f"spell_{key}"] = self._create_key_button(key)
            new_grid.addWidget(self.key_buttons[f"spell_{key}"], row, col)

        # --- Right Panel ---
        right_layout = QVBoxLayout(right_panel)
        right_layout.addWidget(self.remap_inventory_group)
        right_layout.addWidget(self.remap_mouse_group)
        right_layout.addWidget(self.settings_group)
        right_layout.addStretch()

        inventory_grid = QGridLayout(self.remap_inventory_group)
        for i in range(6):
            row, col = i // 2, i % 2
            self.key_buttons[f"inv_{i+1}"] = self._create_key_button(str(i + 1))
            inventory_grid.addWidget(self.key_buttons[f"inv_{i+1}"], row, col)

        mouse_grid = QGridLayout(self.remap_mouse_group)
        mouse_grid.addWidget(QLabel("Left Click"), 0, 0)
        mouse_grid.addWidget(QLabel("Right Click"), 0, 1)
        self.key_buttons["mouse_Left"] = self._create_key_button("LButton")
        self.key_buttons["mouse_Right"] = self._create_key_button("RButton")
        mouse_grid.addWidget(self.key_buttons["mouse_Left"], 1, 0)
        mouse_grid.addWidget(self.key_buttons["mouse_Right"], 1, 1)

        settings_v_layout = QVBoxLayout(self.settings_group)
        for checkbox in self.setting_checkboxes.values():
            settings_v_layout.addWidget(checkbox)

    def _create_key_button(self, default_text: str) -> QPushButton:
        """Helper to create a standard key button."""
        button = QPushButton(default_text)
        button.setFixedSize(60, 60)
        button.setCheckable(True) # To show "capture" state
        return button

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