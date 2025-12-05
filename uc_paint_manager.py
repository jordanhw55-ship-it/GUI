import tkinter as tk
from PIL import Image, ImageDraw, ImageTk

class PaintManager:
    """Manages all painting and erasing functionality."""
    def __init__(self, app):
        self.app = app