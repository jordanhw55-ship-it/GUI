import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import os

class BorderManager:
    """Manages loading and applying border assets."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas

    def load_border_to_dock(self):
        """Loads a border image to the asset dock, marking it specifically as a border."""
        self.app.image_manager._load_asset_to_dock_generic(is_border=True) # This is now correct

    def apply_border_to_selection(self):
        """
        Applies a border to the underlying tile(s) by treating it as a decal stamp.
        This function finds the active border decal and stamps it onto any component
        it overlaps with.
        """
        self.app.apply_decal_to_underlying_layer()

    def remove_border_from_selection(self):
        """
        In the current decal-based workflow, removing a border is the same as
        resetting the tile's image. This provides user guidance.
        """
        if not self.app.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a tile to remove a border from.")
            return
        self.app.reset_selected_layer()
        messagebox.showinfo("Border Removed", f"The border has been removed from '{self.app.selected_component_tag}' by resetting the tile.")