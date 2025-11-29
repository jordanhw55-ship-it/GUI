from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QLabel
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
        self.apply_tab = QWidget()

        # Add sub-tabs to the tab widget
        self.tab_widget.addTab(self.ui_tab, "UI")
        self.tab_widget.addTab(self.font_tab, "Font")
        self.tab_widget.addTab(self.background_tab, "Background")
        self.tab_widget.addTab(self.hp_bar_tab, "HP Bar")
        self.tab_widget.addTab(self.apply_tab, "Apply")

        self._populate_tabs()

    def _populate_tabs(self):
        """Adds placeholder content to the sub-tabs."""
        for i in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(i)
            tab_name = self.tab_widget.tabText(i)
            layout = QVBoxLayout(tab)
            layout.addWidget(QLabel(f"Content for {tab_name} tab."))