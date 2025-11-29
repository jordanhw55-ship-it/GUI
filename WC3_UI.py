import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton, QHBoxLayout
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
        ui_layout = QVBoxLayout(self.ui_tab)
        self.theme_buttons = []
        for i in range(1, 7):
            theme_layout = QHBoxLayout()
            button = QPushButton(f"Theme {i}")
            self.theme_buttons.append(button)
            theme_layout.addWidget(button, 1)  # Button takes some space

            # Add the image for Theme 1
            if i == 1:
                image_label = QLabel()
                image_path = os.path.join(get_base_path(), "contents", "WC3UI", "theme1.png")
                if os.path.exists(image_path):
                    pixmap = QPixmap(image_path)
                    image_label.setPixmap(pixmap.scaledToHeight(40, Qt.TransformationMode.SmoothTransformation))
                theme_layout.addWidget(image_label, 2) # Give image some space

            theme_layout.addStretch(7)  # The rest of the space is empty
            ui_layout.addLayout(theme_layout)
        ui_layout.addStretch()  # Push everything to the top

        # Populate other tabs with placeholders
        other_tabs = [self.font_tab, self.background_tab, self.hp_bar_tab, self.reticle_tab, self.apply_tab]
        for tab in other_tabs:
            tab_name = self.tab_widget.tabText(self.tab_widget.indexOf(tab))
            layout = QVBoxLayout(tab)
            layout.addWidget(QLabel(f"Content for {tab_name} tab."))
            layout.addStretch()