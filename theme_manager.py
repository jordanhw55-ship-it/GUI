from PySide6.QtWidgets import QGridLayout, QVBoxLayout, QLabel, QColorDialog
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from utils import DARK_STYLE, LIGHT_STYLE, FOREST_STYLE, OCEAN_STYLE

class ThemeManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.themes = [
            {"name": "Black/Orange", "style": DARK_STYLE, "preview_color": "#FF7F50", "is_dark": True, "title_image": "title.png"},
            {"name": "White/Pink", "style": LIGHT_STYLE, "preview_color": "#FFC0CB", "is_dark": False, "title_image": "title1.png"},
            {"name": "Black/Blue", "style": FOREST_STYLE, "preview_color": "#1E90FF", "is_dark": True, "title_image": "title2.png"},
            {"name": "White/Blue", "style": OCEAN_STYLE, "preview_color": "#87CEEB", "is_dark": False, "title_image": "title3.png"},
        ]
        self.theme_previews = []

    def create_theme_grid(self, layout: QGridLayout):
        """Populates the provided grid layout with theme preview widgets."""
        from __main__ import ThemePreview # Avoid circular import

        row, col = 0, 0
        for i, theme in enumerate(self.themes):
            preview = ThemePreview()
            preview.setFixedSize(150, 120)
            preview.setCursor(Qt.CursorShape.PointingHandCursor)
            preview.setObjectName("ThemePreview")
            preview.clicked.connect(lambda idx=i: self.apply_theme(idx))

            preview_layout = QVBoxLayout(preview)
            color_block = QLabel()
            color_block.setFixedHeight(80)
            color_block.setStyleSheet(f"background-color: {theme['preview_color']}; border-radius: 5px;")
            name_label = QLabel(theme['name'])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            preview_layout.addWidget(color_block)
            preview_layout.addWidget(name_label)
            layout.addWidget(preview, row, col)
            self.theme_previews.append(preview)

            col += 1
            if col >= 4:
                col = 0
                row += 1
        layout.setRowStretch(row + 1, 1)
        layout.setColumnStretch(col + 1, 1)

    def apply_theme(self, theme_index: int):
        """Applies a preset theme to the main window."""
        self.main_window.current_theme_index = theme_index
        theme = self.themes[theme_index]

        self.main_window.dark_mode = theme["is_dark"]
        self.main_window.setStyleSheet(theme["style"])
        self.main_window.custom_tab_bar.apply_style(theme['name'], self.main_window.dark_mode)
        self.main_window.set_title_image(theme.get("title_image"))

        for i, preview in enumerate(self.theme_previews):
            border_style = "border: 2px solid #FF7F50;" if i == theme_index else "border: 2px solid transparent;"
            preview.setStyleSheet(f"#ThemePreview {{ {border_style} border-radius: 8px; background-color: {'#2A2A2C' if self.main_window.dark_mode else '#D8DEE9'}; }}")

        self.main_window.update_ping_button_styles()

    def build_custom_stylesheet(self) -> str:
        """Builds the full stylesheet string from the custom theme colors."""
        custom_theme = self.main_window.custom_theme
        bg, fg, accent = custom_theme["bg"], custom_theme["fg"], custom_theme["accent"]
        # This is a simplified version of your builder. You can move the full string here.
        return f"""
            QWidget {{ background-color: {bg}; color: {fg}; outline: none; }}
            QMainWindow, #CustomTitleBar {{ background-color: {bg}; }}
            #CustomTitleBar QLabel, #CustomTitleBar QPushButton {{ background-color: transparent; border: none; color: {fg}; font-size: 18px; }}
            #CustomTitleBar QPushButton:hover {{ background-color: {accent}; }}
            QPushButton {{ background-color: {accent}; color: {bg}; border: 1px solid {accent}; padding: 5px; border-radius: 6px; }}
            QPushButton:hover {{ background-color: {bg}; color: {accent}; }}
            QLineEdit, QTextEdit, QTableWidget, QListWidget {{ background-color: #2E2E2E; color: {fg}; border: 1px solid {accent}; border-radius: 6px; padding: 6px; }}
            QGroupBox {{ border: 1px solid {accent}; border-radius: 8px; margin-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top center; padding: 0 10px; font-weight: bold; }}
            QHeaderView::section {{ background-color: #2E2E2E; color: {fg}; border: 1px solid {accent}; padding: 4px; }}
            QCheckBox::indicator {{ border: 1px solid {accent}; }}
        """

    def apply_custom_theme(self):
        """Applies the custom theme to the main window."""
        self.main_window.current_theme_index = -1
        custom_theme = self.main_window.custom_theme
        
        bg_color = QColor(custom_theme.get("bg", "#121212"))
        self.main_window.dark_mode = bg_color.lightness() < 128

        self.main_window.setStyleSheet(self.build_custom_stylesheet())
        self.main_window.set_title_image(self.main_window.custom_title_image_path)
        self.main_window.custom_tab_bar.setStyleSheet(f"""            
            QPushButton {{ background-color: {custom_theme['bg']}; border: 1px solid {custom_theme['fg']}; padding: 8px; border-radius: 6px; color: {custom_theme['fg']}; font-size: 16px; }}
            QPushButton:hover {{ background-color: {custom_theme['accent']}; }}
            QPushButton:checked {{ background-color: {custom_theme['accent']}; color: {custom_theme['bg']}; border-color: {custom_theme['accent']}; }}
        """)
        
        for preview in self.theme_previews:
            preview.setStyleSheet(f"#ThemePreview {{ border: 2px solid transparent; border-radius: 8px; background-color: {'#2A2A2C' if self.main_window.dark_mode else '#D8DEE9'}; }}")
        
        self.update_custom_theme_preview()
        self.main_window.update_ping_button_styles()

    def reapply_current_theme(self):
        """Re-applies the currently active theme (preset or custom)."""
        if self.main_window.current_theme_index == -1:
            self.apply_custom_theme()
        else:
            self.apply_theme(self.main_window.current_theme_index)

    def update_custom_theme_preview(self):
        """Updates the live preview widget with the current custom theme colors."""
        custom_theme = self.main_window.custom_theme
        bg, fg, accent = custom_theme.get('bg', '#121212'), custom_theme.get('fg', '#F0F0F0'), custom_theme.get('accent', '#FF7F50')
        
        self.main_window.custom_theme_preview.setStyleSheet(f"#CustomThemePreview {{ background-color: {bg}; border: 1px solid {accent}; border-radius: 8px; }}")
        self.main_window.preview_label.setStyleSheet(f"color: {fg}; background-color: transparent; border: none;")
        self.main_window.preview_button.setStyleSheet(f"background-color: {accent}; color: {bg}; border: 1px solid {accent}; padding: 5px; border-radius: 6px;")

    def pick_color(self, key: str):
        """Opens a color dialog and updates the custom theme dictionary."""
        initial = QColor(self.main_window.custom_theme[key])
        color = QColorDialog.getColor(initial, self.main_window, f"Pick {key} color")
        if color.isValid():
            self.main_window.custom_theme[key] = color.name()
            self.update_custom_theme_preview()

    def reset_custom_theme_to_defaults(self):
        """Resets custom theme colors to their default values and applies them."""
        self.main_window.custom_theme = { "bg": "#121212", "fg": "#F0F0F0", "accent": "#FF7F50" }
        self.main_window.custom_title_image_path = ""
        self.apply_custom_theme()