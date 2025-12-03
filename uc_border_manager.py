import tkinter as tk
from tkinter import colorchooser, messagebox
from PIL import Image, ImageDraw
import os

class BorderManager:
    """Manages loading and applying border assets."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas

    def load_border_to_dock(self):
        """Calls the generic asset loader, specifying that this is a border."""
        self.app.image_manager._load_asset_to_dock_generic(is_border=True)

    def apply_border_to_selection(self):
        """
        Applies the selected border from the dock to the selected tile on the canvas.
        This re-uses the decal/cloning mechanism.
        """
        # 1. Find the selected tile on the main canvas
        if not self.app.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a tile from the 'Tiles' tab to apply a border to.")
            return
        target_comp = self.app.components.get(self.app.selected_component_tag)
        if not target_comp or target_comp.is_dock_asset:
            messagebox.showwarning("Invalid Selection", "Please select a valid tile on the main canvas.")
            return

        # 2. Find the selected border in the border dock
        # This is a simplification; for now, we'll use the decal system.
        # The user should click a border in the dock, which creates a decal, then click this button.
        border_decal = self.app.image_manager._find_topmost_stamp_source(clone_type='border_')
        if not border_decal:
            messagebox.showwarning("Border Required", "Please click on a border in the dock to activate it before applying.")
            return

        # 3. Use the ImageManager's existing logic to apply the decal
        self.app.image_manager.apply_decal_to_underlying_layer()