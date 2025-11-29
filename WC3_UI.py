import os
import shutil
import subprocess
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton, QGridLayout, QHBoxLayout, QLineEdit, QFileDialog, QMessageBox, QGroupBox, QListWidget
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from utils import get_base_path
class WC3UITab(QWidget):
    """A widget for the 'WC3 UI' tab, containing various UI customization options."""
    def __init__(self, parent=None):
        super().__init__(parent)

        # State variables to track selections
        self.selected_theme = None
        self.selected_hp_bar = None
        self.selected_unit_select = None
        
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

        # Summary box for selected changes
        self.summary_group = QGroupBox("Changes to Apply")
        summary_group_layout = QVBoxLayout(self.summary_group)
        
        # Add a small reset button inside the group box
        self.reset_summary_button = QPushButton("Reset Selections")
        
        self.summary_list = QListWidget()
        self.summary_list.setFixedHeight(120)  # Set a fixed height for the summary box
        summary_group_layout.addWidget(self.summary_list)
        summary_group_layout.addWidget(self.reset_summary_button)
        right_layout.addWidget(self.summary_group)
        right_layout.addStretch()

        # Apply and Reset buttons at the bottom
        self.apply_wc3_ui_button = QPushButton("Apply")
        self.reset_default_button = QPushButton("Reset Default")
        right_layout.addWidget(self.apply_wc3_ui_button)
        right_layout.addWidget(self.reset_default_button)

        # Guide button
        self.guide_button = QPushButton("Guide")
        right_layout.addWidget(self.guide_button)

        # Reg On and Reg Off buttons
        reg_buttons_layout = QHBoxLayout()
        self.reg_on_button = QPushButton("Reg On")
        self.reg_off_button = QPushButton("Reg Off")
        reg_buttons_layout.addWidget(self.reg_on_button)
        reg_buttons_layout.addWidget(self.reg_off_button)
        right_layout.addLayout(reg_buttons_layout)

        # Create the sub-tabs
        self.ui_tab = QWidget()
        self.unit_select_tab = QWidget()
        self.hp_bar_tab = QWidget()
        self.reticle_tab = QWidget()

        # Add sub-tabs to the tab widget
        self.tab_widget.addTab(self.ui_tab, "UI")
        self.tab_widget.addTab(self.unit_select_tab, "Unit Select")
        self.tab_widget.addTab(self.hp_bar_tab, "HP Bar")
        self.tab_widget.addTab(self.reticle_tab, "Reticle")

        self._populate_tabs()

        self.browse_button.clicked.connect(self.browse_for_wc3_path)
        self.create_folders_button.clicked.connect(self.create_interface_folders)
        self.apply_wc3_ui_button.clicked.connect(self.apply_all_changes)
        self.reset_summary_button.clicked.connect(self.reset_summary_selections)
        self.guide_button.clicked.connect(self.show_guide_prompt)
        self.reg_on_button.clicked.connect(self.run_reg_on)
        self.reg_off_button.clicked.connect(self.run_reg_off)
        self.reset_default_button.clicked.connect(self.reset_to_default)

    def _populate_tabs(self):
        """Adds content to the sub-tabs."""
        # UI Tab
        ui_layout = QGridLayout(self.ui_tab)
        ui_layout.setVerticalSpacing(10)  # Add vertical space between rows
        self.theme_buttons = []

        for i in range(1, 7):
            button = QPushButton(f"Theme {i}")
            button.setCheckable(True)
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
            button.setCheckable(True)
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

        # Unit Select Tab
        unit_select_layout = QGridLayout(self.unit_select_tab)
        unit_select_layout.setVerticalSpacing(10)
        self.unit_select_buttons = []
        unit_select_options = ["Chain", "Dragon", "Eye", "Skeleton", "Square", "Sun", "Target"]

        for i, option_name in enumerate(unit_select_options):
            button = QPushButton(option_name)
            button.setCheckable(True)
            self.unit_select_buttons.append(button)
            unit_select_layout.addWidget(button, i, 0)

            # Create a label for the image
            image_label = QLabel()
            image_path_jpg = os.path.join(get_base_path(), "contents", "WC3UI", "UnitSelection", option_name, f"{option_name}.jpg")
            image_path_png = os.path.join(get_base_path(), "contents", "WC3UI", "UnitSelection", option_name, f"{option_name}.png")

            image_path = ""
            if os.path.exists(image_path_jpg):
                image_path = image_path_jpg
            elif os.path.exists(image_path_png):
                image_path = image_path_png

            if image_path:
                pixmap = QPixmap(image_path)
                image_label.setPixmap(pixmap.scaled(300, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            
            unit_select_layout.addWidget(image_label, i, 1)

        unit_select_layout.setColumnStretch(0, 1)
        unit_select_layout.setColumnStretch(1, 5)
        unit_select_layout.setRowStretch(len(unit_select_options), 1)

        # Connect button signals after they are created
        for i, button in enumerate(self.theme_buttons):
            button.clicked.connect(lambda checked, b=button: self.on_option_selected(b, self.theme_buttons, 'theme'))
        for button in self.hp_bar_buttons:
            button.clicked.connect(lambda checked, b=button: self.on_option_selected(b, self.hp_bar_buttons, 'hp_bar'))
        for button in self.unit_select_buttons:
            button.clicked.connect(lambda checked, b=button: self.on_option_selected(b, self.unit_select_buttons, 'unit_select'))

        # Populate other tabs with placeholders
        other_tabs = [self.reticle_tab]
        for tab in other_tabs:
            tab_name = self.tab_widget.tabText(self.tab_widget.indexOf(tab))
            layout = QVBoxLayout(tab)
            layout.addWidget(QLabel(f"Content for {tab_name} tab."))
            layout.addStretch()

    def on_option_selected(self, clicked_button: QPushButton, button_group: list, category: str):
        """Handles the logic when an option button is clicked, ensuring only one is selected."""
        # Uncheck all other buttons in the same group
        for button in button_group:
            if button is not clicked_button:
                button.setChecked(False)

        # Update the state variable for the corresponding category
        if clicked_button.isChecked():
            selection_name = clicked_button.text()
            if category == 'theme': self.selected_theme = selection_name
            elif category == 'hp_bar': self.selected_hp_bar = selection_name
            elif category == 'unit_select': self.selected_unit_select = selection_name
        else: # If the user unchecks the button
            if category == 'theme': self.selected_theme = None
            elif category == 'hp_bar': self.selected_hp_bar = None
            elif category == 'unit_select': self.selected_unit_select = None

        self._update_summary_list()

    def _update_summary_list(self):
        """Updates the summary list on the right with the current selections."""
        self.summary_list.clear()
        
        if self.selected_theme:
            self.summary_list.addItem(f"UI: {self.selected_theme}")
            
        if self.selected_hp_bar:
            self.summary_list.addItem(f"HP Bar: {self.selected_hp_bar}")

        if self.selected_unit_select:
            self.summary_list.addItem(f"Unit Select: {self.selected_unit_select}")

    def reset_summary_selections(self):
        """Resets all selections in the UI and clears the summary box."""
        # Uncheck all buttons in every group
        for button in self.theme_buttons:
            button.setChecked(False)
        for button in self.hp_bar_buttons:
            button.setChecked(False)
        for button in self.unit_select_buttons:
            button.setChecked(False)

        # Reset the state variables
        self.selected_theme = None
        self.selected_hp_bar = None
        self.selected_unit_select = None

        # Update the UI
        self._update_summary_list()

    def show_guide_prompt(self):
        """Displays a message box with a step-by-step guide."""
        guide_text = """
1. Click "Create Folders" after finding your _retail_ folder (if it isnt already selected)

2. Click "Reg on" to enable customization of WC3, alternatively you can do the CMD "reg add "HKCU\SOFTWARE\Blizzard Entertainment\Warcraft III" /v "Allow Local Files" /t REG_DWORD /d 1 /f"

3. Select 1 of each option and click Apply. Restart WC3 to see changes. 

4. Reg off will hide any customizations, if you want to delete the folder find the UI folder in "C:\Program Files (x86)\Warcraft III\\_retail_"
        """.strip()

        QMessageBox.information(self, "Guide", guide_text)


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

    def apply_all_changes(self):
        """Applies all selected changes from the various sub-tabs."""
        wc3_path = self.path_edit.text()
        if not os.path.isdir(wc3_path):
            QMessageBox.warning(self, "Invalid Path", "The specified Warcraft III path does not exist. Please set it correctly before applying changes.")
            return

        changes_applied = []

        # Apply HP Bar change
        if self.selected_hp_bar:
            source_dir = os.path.join(get_base_path(), "contents", "WC3UI", "HP Bar", self.selected_hp_bar)
            dest_dir = os.path.join(wc3_path, "UI", "Feedback", "HpBarConsole")
            if self._copy_file("human-healthbar-fill.blp", source_dir, dest_dir):
                changes_applied.append(f"HP Bar: {self.selected_hp_bar}")

        # Apply UI Theme change
        if self.selected_theme:
            theme_folder_name = self.selected_theme.lower().replace(" ", "")
            source_dir = os.path.join(get_base_path(), "contents", "WC3UI", "UI", theme_folder_name)
            dest_dir = os.path.join(wc3_path, "UI", "console", "human")

            if os.path.isdir(source_dir):
                files_copied_count = 0
                for filename in os.listdir(source_dir):
                    if filename.lower().endswith(".blp"):
                        if self._copy_file(filename, source_dir, dest_dir):
                            files_copied_count += 1
                if files_copied_count > 0:
                    changes_applied.append(f"UI: {self.selected_theme} ({files_copied_count} files)")
            else:
                QMessageBox.warning(self, "Source Directory Not Found", f"Could not find the source directory for '{self.selected_theme}'.")

        # Apply Unit Select change
        if self.selected_unit_select:
            source_dir = os.path.join(get_base_path(), "contents", "WC3UI", "UnitSelection", self.selected_unit_select)
            dest_dir = os.path.join(wc3_path, "UI", "ReplaceableTextures", "Selection")
            
            if os.path.isdir(source_dir):
                files_copied_count = 0
                for filename in os.listdir(source_dir):
                    if filename.lower().endswith(".blp"):
                        if self._copy_file(filename, source_dir, dest_dir):
                            files_copied_count += 1
                if files_copied_count > 0:
                    changes_applied.append(f"Unit Select: {self.selected_unit_select} ({files_copied_count} files)")
            else:
                QMessageBox.warning(self, "Source Directory Not Found", f"Could not find the source directory for '{self.selected_unit_select}'.")

        if changes_applied:
            QMessageBox.information(self, "Success", "The following changes have been applied:\n\n- " + "\n- ".join(changes_applied))
        else:
            QMessageBox.information(self, "No Changes", "No options were selected to apply.")

    def _copy_file(self, filename: str, source_dir: str, dest_dir: str) -> bool:
        """Helper function to copy a file and handle errors."""
        source_path = os.path.join(source_dir, filename)
        dest_path = os.path.join(dest_dir, filename)

        if not os.path.exists(source_path):
            QMessageBox.warning(self, "File Not Found", f"Could not find the source file:\n{source_path}")
            return False
        try:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            return True
        except (OSError, shutil.Error) as e:
            QMessageBox.critical(self, "Copy Error", f"Failed to copy file to:\n{dest_path}\n\nError: {e}")
            return False

    def reset_to_default(self):
        """Functionality for the 'Reset Default' button will be added here."""
        QMessageBox.information(self, "Not Implemented", "The 'Reset Default' functionality is not yet implemented.")

    def run_reg_on(self):
        """Runs the reg_on.reg file after confirmation."""
        self._run_reg_file("reg_on.reg")

    def run_reg_off(self):
        """Runs the reg_off.reg file after confirmation."""
        self._run_reg_file("reg_off.reg")

    def _run_reg_file(self, filename: str):
        """Shows a confirmation and then runs the specified .reg file."""
        confirm = QMessageBox.question(self, "Confirm Registry Edit",
                                       "This will edit your registry. Confirm?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

        if confirm == QMessageBox.StandardButton.Yes:
            reg_file_path = os.path.join(get_base_path(), "contents", "WC3UI", filename)

            if not os.path.exists(reg_file_path):
                QMessageBox.critical(self, "File Not Found", f"The registry file could not be found:\n{reg_file_path}")
                return

            try:
                # Use 'reg import' for a standard way to import .reg files.
                subprocess.run(["reg", "import", reg_file_path], check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                QMessageBox.information(self, "Success", f"Successfully executed {filename}.")
            except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
                error_output = e.stderr if hasattr(e, 'stderr') else str(e)
                QMessageBox.critical(self, "Registry Error", f"Failed to execute registry file.\n\nError: {error_output}")