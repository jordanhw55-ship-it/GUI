from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

class OverlayStatus(QLabel):
    """A floating, self-hiding label to show automation status."""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool  # This flag prevents the widget from appearing in the taskbar
        )
        self.setFont(QFont("Arial", 14, QFont.Bold))
        self.setAlignment(Qt.AlignCenter)
        self.setAutoFillBackground(True)
        self.resize(180, 40)  # The size of the status box
        self.move(0, 0)       # Positioned at the top-left of the screen

    def show_status(self, enabled: bool):
        """Shows the status with appropriate color and text, then hides it."""
        palette = self.palette()
        if enabled:
            self.setText("Automation ON")
            palette.setColor(QPalette.Window, QColor("#228B22")) # ForestGreen
            palette.setColor(QPalette.WindowText, QColor("white"))
        else:
            self.setText("Automation OFF")
            palette.setColor(QPalette.Window, QColor("#B22222")) # FireBrick
            palette.setColor(QPalette.WindowText, QColor("white"))
        self.setPalette(palette)
        self.show()
        # Hide the overlay after 1.5 seconds
        QTimer.singleShot(1500, self.hide)

class QuickcastStatus(QLabel):
    """A floating, self-hiding label to show quickcast status."""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setFont(QFont("Arial", 14, QFont.Bold))
        self.setAlignment(Qt.AlignCenter)
        self.setAutoFillBackground(True)
        self.resize(180, 40)
        self.move(0, 45) # Positioned below the automation status

    def show_status(self, enabled: bool):
        """Shows the status with appropriate color and text, then hides it."""
        palette = self.palette()
        if enabled:
            self.setText("Quickcast ON")
            palette.setColor(QPalette.Window, QColor("#228B22")) # ForestGreen
        else:
            self.setText("Quickcast OFF")
            palette.setColor(QPalette.Window, QColor("#B22222")) # FireBrick
        palette.setColor(QPalette.WindowText, QColor("white"))
        self.setPalette(palette)
        self.show()
        QTimer.singleShot(1500, self.hide)