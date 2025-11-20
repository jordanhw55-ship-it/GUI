from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTextEdit, QTableWidget, QHeaderView, QGroupBox,
    QGridLayout, QCheckBox, QLabel, QStackedWidget
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


class RecipeTrackerTab(QWidget):
    """A widget for the 'Recipes' tab, for tracking crafting materials."""
    def __init__(self, parent_window):
        super().__init__()
        # self.parent_window = parent_window
        self._create_widgets()
        self._create_layouts()

    def _create_widgets(self):
        """Creates all the widgets for the tab."""
        self.recipe_search_box = QLineEdit()
        self.recipe_search_box.setPlaceholderText("Search Recipes...")
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

    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        recipes_list_layout = QVBoxLayout(); recipes_list_layout.addWidget(self.recipe_search_box); recipes_list_layout.addWidget(self.available_recipes_list)
        add_remove_layout = QVBoxLayout(); add_remove_layout.addStretch(); add_remove_layout.addWidget(self.add_recipe_btn); add_remove_layout.addWidget(self.remove_recipe_btn); add_remove_layout.addWidget(self.reset_recipes_btn); add_remove_layout.addStretch()
        top_layout.addLayout(recipes_list_layout); top_layout.addLayout(add_remove_layout); top_layout.addWidget(self.in_progress_recipes_list)
        main_layout.addLayout(top_layout); main_layout.addWidget(self.materials_table)
        main_layout.setStretchFactor(top_layout, 1); main_layout.setStretchFactor(self.materials_table, 3)


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

        self.start_automation_btn = QPushButton("Start (F5)")
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
        left_layout.addWidget(self.automation_keys_group); left_layout.addWidget(self.start_automation_btn); left_layout.addWidget(self.reset_automation_btn)
        left_layout.addWidget(QLabel("Intervals are in ms. Example: 500 = 0.5s")); left_layout.addStretch()
        right_layout = QVBoxLayout(self.msg_hotkey_group)
        right_layout.addWidget(self.msg_hotkey_table)
        msg_form_layout = QGridLayout(); msg_form_layout.addWidget(QLabel("Hotkey:"), 0, 0); msg_form_layout.addWidget(self.hotkey_capture_btn, 0, 1); msg_form_layout.addWidget(QLabel("Message:"), 1, 0); msg_form_layout.addWidget(self.message_edit, 1, 1); right_layout.addLayout(msg_form_layout)
        msg_btn_layout = QHBoxLayout(); msg_btn_layout.addWidget(self.add_msg_btn); msg_btn_layout.addWidget(self.delete_msg_btn); right_layout.addLayout(msg_btn_layout)
        left_panel = QWidget(); left_panel.setLayout(left_layout)
        main_layout.addWidget(left_panel, 1); main_layout.addWidget(self.msg_hotkey_group, 1)


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
        item_tab_names = ["All Items", "Drops", "Raid Items", "Vendor Items"]
        for i, name in enumerate(item_tab_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            self.item_tab_buttons[i] = btn
            self.sub_tabs_layout.addWidget(btn)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search...")
        self.search_box.setObjectName("ItemSearchBox")

        self.stacked_widget = QStackedWidget()
        self.all_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.drops_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.raid_items_table = self._create_item_table(["Item", "Drop%", "Unit", "Location"])
        self.vendor_table = self._create_item_table(["Item", "Unit", "Location"])
        self.stacked_widget.addWidget(self.all_items_table)
        self.stacked_widget.addWidget(self.drops_table)
        self.stacked_widget.addWidget(self.raid_items_table)
        self.stacked_widget.addWidget(self.vendor_table)

    def _create_layouts(self):
        """Creates and arranges the layouts for the tab."""
        main_layout = QVBoxLayout(self)
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.sub_tabs_widget)
        controls_layout.addStretch()
        controls_layout.addWidget(self.search_box)
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.stacked_widget)

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