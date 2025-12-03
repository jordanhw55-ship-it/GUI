import tkinter as tk
from tkinter import colorchooser, messagebox
from PIL import Image, ImageDraw, ImageTk
import os

class BorderManager:
    """Manages loading and applying border assets (texture-based frames)."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.shape_color = "#ff0000"  # Default dynamic border color
        self.border_thickness = 10    # Default thickness
        self.loaded_borders = {}      # Dict of {name: PIL.Image}
        self.active_border_name = None
        self.active_border_image = None
        self.active_border_canvas_item = None

    def load_border_to_dock(self, folder="borders"):
        """
        Load all border textures from a folder into memory.
        Each texture should be a PNG (e.g., brick.png, stone.png).
        """
        if not os.path.exists(folder):
            messagebox.showwarning("No Borders Found", f"Folder '{folder}' does not exist.")
            return

        for fname in os.listdir(folder):
            if fname.lower().endswith(".png"):
                path = os.path.join(folder, fname)
                img = Image.open(path).convert("RGBA")
                self.loaded_borders[fname] = img

        if self.loaded_borders:
            self.active_border_name = list(self.loaded_borders.keys())[0]
            self.active_border_image = self.loaded_borders[self.active_border_name]
            print(f"Loaded borders: {list(self.loaded_borders.keys())}")

    def choose_border(self, name):
        """Switch active border style by name."""
        if name in self.loaded_borders:
            self.active_border_name = name
            self.active_border_image = self.loaded_borders[name]

    def apply_border_to_selection(self):
        """
        Apply the active border to the currently selected tile.
        - If no tile is selected, warn the user.
        - If a border asset is active, tile it along the bounding box edges.
        """
        if not self.app.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a tile first.")
            return

        target_comp = self.app.components.get(self.app.selected_component_tag)
        if not target_comp:
            return

        # Get bounding box of the tile
        x1, y1, x2, y2 = self.canvas.bbox(target_comp.tag)
        width, height = x2 - x1, y2 - y1

        if not self.active_border_image:
            messagebox.showwarning("No Border Selected", "Please load and select a border style first.")
            return

        # Create a new image for the border frame
        border_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        # Tile the border texture along edges
        tex = self.active_border_image
        tex_w, tex_h = tex.size

        # Top edge
        for i in range(0, width, tex_w):
            border_img.paste(tex, (i, 0), tex)

        # Bottom edge
        for i in range(0, width, tex_w):
            border_img.paste(tex, (i, height - tex_h), tex)

        # Left edge
        for j in range(0, height, tex_h):
            border_img.paste(tex, (0, j), tex)

        # Right edge
        for j in range(0, height, tex_h):
            border_img.paste(tex, (width - tex_w, j), tex)

        # Convert to Tk image and place on canvas
        tk_img = ImageTk.PhotoImage(border_img)
        self.active_border_canvas_item = self.canvas.create_image(x1, y1, anchor="nw", image=tk_img)
        target_comp.border_image = tk_img  # Keep reference alive

    def remove_border_from_selection(self):
        """Remove the active border from the selected tile."""
        if self.active_border_canvas_item:
            self.canvas.delete(self.active_border_canvas_item)
            self.active_border_canvas_item = None