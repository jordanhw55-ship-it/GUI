from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette

class OverlayStatus(QFrame):
    """A floating, self-hiding label to show automation status."""
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # The label will be a child of the QFrame, centered within it
        self.label = QLabel(self)
        self.label.setFont(QFont("Arial", 14, QFont.Bold))
        self.label.setAlignment(Qt.AlignCenter)

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

    def show_message(self, text: str, bg_color: str, fg_color: str = "white", timeout_ms: int | None = 1500):
        """Shows a custom always-on-top overlay message.
        If timeout_ms is None or 0, the overlay remains until explicitly hidden.
        """
        # Set the style on the QFrame itself
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color}CC; /* CC = 80% opacity */
                color: {fg_color};
                border-radius: 5px;
            }}
        """)
        self.label.setText(text)
        self.label.adjustSize() # Adjust label size to text
        self.setFixedSize(self.label.width() + 20, self.label.height() + 10) # Resize frame around label
        self.label.move(10, 5) # Center the label within the frame padding
        self.show()
        if timeout_ms and timeout_ms > 0:
            QTimer.singleShot(timeout_ms, self.hide)