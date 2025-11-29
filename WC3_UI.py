import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton, QGridLayout, QHBoxLayout, QLineEdit, QFileDialog, QMessageBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from utils import get_base_path
class WC3UITab(QWidget):
    """A widget for the 'WC3 UI' tab, containing various UI customization options."""
    def __init__(self, parent=None):
        super().__init__(parent)
        
        main_layout = QHBoxLayout(self)
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Right-side panel for path and actions
        right_panel = QWidget()
        right_panel.setFixedWidth(200)
        right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel)

        # Path finder
        path_group = QWidget()
        path_layout = QVBoxLayout(path_group)
        path_layout.setContentsMargins(0,0,0,0)
        path_layout.addWidget(QLabel("Warcraft III Path:"))
        self.path_edit = QLineEdit(r"C:\Program Files (x86)\Warcraft III\_retail_")
        self.browse_button = QPushButton("Browse...")
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.browse_button)

        # Button to create folder structure
        self.create_folders_button = QPushButton("Create Folders")

        right_layout.addWidget(self.create_folders_button)
        right_layout.addWidget(path_group)
        right_layout.addStretch()

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

        self.browse_button.clicked.connect(self.browse_for_wc3_path)
        self.create_folders_button.clicked.connect(self.create_interface_folders)

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
            image_path = os.path.join(get_base_path(), "contents", "WC3UI", "UI", theme_folder, image_name)
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                image_label.setPixmap(pixmap.scaled(300, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

            ui_layout.addWidget(image_label, i - 1, 1) # Add image label to column 1

        # Set column stretches to define the layout proportions
        ui_layout.setColumnStretch(0, 1)  # Button column
        ui_layout.setColumnStretch(1, 5)  # Image column (5 times wider)
        ui_layout.setRowStretch(6, 1)     # Add stretch below the last row

        # HP Bar Tab
        hp_bar_layout = QGridLayout(self.hp_bar_tab)
        hp_bar_layout.setVerticalSpacing(10)
        self.hp_bar_buttons = []
        hp_bar_options = ["4Bar", "8Bar", "30Bar"]

        for i, option_name in enumerate(hp_bar_options):
            button = QPushButton(option_name)
            self.hp_bar_buttons.append(button)
            hp_bar_layout.addWidget(button, i, 0)

            # Create a label for the image
            image_label = QLabel()
            
            # Check for both .jpg and .png extensions to be safe
            image_path_jpg = os.path.join(get_base_path(), "contents", "WC3UI", "HP Bar", option_name, f"{option_name}.jpg")
            image_path_png = os.path.join(get_base_path(), "contents", "WC3UI", "HP Bar", option_name, f"{option_name}.png")
            
            image_path = ""
            if os.path.exists(image_path_jpg):
                image_path = image_path_jpg
            elif os.path.exists(image_path_png):
                image_path = image_path_png

            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                image_label.setPixmap(pixmap.scaled(300, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            
            hp_bar_layout.addWidget(image_label, i, 1)

        hp_bar_layout.setColumnStretch(0, 1)
        hp_bar_layout.setColumnStretch(1, 5)
        hp_bar_layout.setRowStretch(len(hp_bar_options), 1)

        # Populate other tabs with placeholders
        other_tabs = [self.font_tab, self.background_tab, self.reticle_tab, self.apply_tab]
        for tab in other_tabs:
            tab_name = self.tab_widget.tabText(self.tab_widget.indexOf(tab))
            layout = QVBoxLayout(tab)
            layout.addWidget(QLabel(f"Content for {tab_name} tab."))
            layout.addStretch()

    def browse_for_wc3_path(self):
        """Opens a dialog to select the Warcraft III directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Warcraft III Folder", self.path_edit.text())
        if directory:
            self.path_edit.setText(directory)

    def create_interface_folders(self):
        """Creates a standard UI modding folder structure inside the selected WC3 path."""
        base_path = self.path_edit.text()
        if not os.path.isdir(base_path):
            QMessageBox.warning(self, "Invalid Path", "The specified Warcraft III path does not exist.")
            return

        ui_path = os.path.join(base_path, "UI")
        # Define the folder structure, including nested folders
        subfolders_to_create = [
            os.path.join("console", "human"),
            "Cursor",
            os.path.join("Feedback", "HpBarConsole"),
            os.path.join("ReplaceableTextures", "Selection")
        ]

        try:
            # Create the main UI folder and all specified subdirectories
            for folder_path in subfolders_to_create:
                full_path = os.path.join(ui_path, folder_path)
                os.makedirs(full_path, exist_ok=True)

            QMessageBox.information(self, "Success",
                                    f"Successfully created folder structure inside:\n{ui_path}")

        except OSError as e:
            QMessageBox.critical(self, "Error", f"Failed to create folders. Please check permissions.\n\nError: {e}")