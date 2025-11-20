from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QListWidget, QTextEdit, QTableWidget, QHeaderView
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