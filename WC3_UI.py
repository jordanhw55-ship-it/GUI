import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton, QGridLayout
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from utils import get_base_path
class WC3UITab(QWidget):
    """A widget for the 'WC3 UI' tab, containing various UI customization options."""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        main_layout = QVBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create the sub-tabs
        self.ui_tab = QWidget()
        self.font_tab = QWidget()
        self.background_tab = QWidget()
        self.hp_bar_tab = QWidget()
        self.reticle_tab = QWidget()
        self.apply_tab = QWidget()

        # Add sub-tabs to the tab widget
        self.tab_widget.addTab(self.ui_tab, "UI")
        self.tab_widget.addTab(self.font_tab, "Font")
        self.tab_widget.addTab(self.background_tab, "Background")
        self.tab_widget.addTab(self.hp_bar_tab, "HP Bar")
        self.tab_widget.addTab(self.reticle_tab, "Reticle")
        self.tab_widget.addTab(self.apply_tab, "Apply")

        self._populate_tabs()

    def _populate_tabs(self):
        """Adds content to the sub-tabs."""
        # UI Tab
        ui_layout = QGridLayout(self.ui_tab)
        ui_layout.setVerticalSpacing(10)  # Add vertical space between rows
        self.theme_buttons = []

        for i in range(1, 7):
            button = QPushButton(f"Theme {i}")
            self.theme_buttons.append(button)
            ui_layout.addWidget(button, i - 1, 0)  # Add button to column 0

            # Create a label for the image in column 1
            image_label = QLabel()
            theme_folder = f"theme{i}"
            image_name = f"theme{i}.png"
            image_path = os.path.join(get_base_path(), "contents", "WC3UI", theme_folder, image_name)
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                image_label.setPixmap(pixmap.scaledToHeight(80, Qt.TransformationMode.SmoothTransformation))

            ui_layout.addWidget(image_label, i - 1, 1) # Add image label to column 1

        # Set column stretches to define the layout proportions
        ui_layout.setColumnStretch(0, 1)  # Button column
        ui_layout.setColumnStretch(1, 5)  # Image column (5 times wider)
        ui_layout.setRowStretch(6, 1)     # Add stretch below the last row

        # Populate other tabs with placeholders
        other_tabs = [self.font_tab, self.background_tab, self.hp_bar_tab, self.reticle_tab, self.apply_tab]
        for tab in other_tabs:
            tab_name = self.tab_widget.tabText(self.tab_widget.indexOf(tab))
            layout = QVBoxLayout(tab)
            layout.addWidget(QLabel(f"Content for {tab_name} tab."))
            layout.addStretch()