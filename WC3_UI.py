from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel, QPushButton
)

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
        self.theme1_button = QPushButton("theme 1")
        ui_layout.addWidget(self.theme1_button)
        ui_layout.addStretch() # Push button to the top

        # Populate other tabs with placeholders
        other_tabs = [self.font_tab, self.background_tab, self.hp_bar_tab, self.reticle_tab, self.apply_tab]
        for tab in other_tabs:
            tab_name = self.tab_widget.tabText(self.tab_widget.indexOf(tab))
            layout = QVBoxLayout(tab)
            layout.addWidget(QLabel(f"Content for {tab_name} tab."))
            layout.addStretch()