import tkinter as tk
from tkinter import colorchooser, messagebox
from PIL import Image, ImageDraw

class BorderManager:
    """Manages loading and applying border assets."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.border_color = "#ffffff" # Default to white
        self.border_thickness = tk.IntVar(value=5)

    def choose_border_color(self):
        """Opens a color chooser and sets the border color."""
        color_code = colorchooser.askcolor(title="Choose Border Color", initialcolor=self.border_color)
        if color_code and color_code[1]:
            self.border_color = color_code[1]
            # Update the UI to show the new color
            self.app.ui_manager.border_color_btn.config(bg=self.border_color)
            print(f"Border color set to: {self.border_color}")

    def load_border_to_dock(self):
        """Calls the generic asset loader, specifying that this is a border."""
        self.app.image_manager._load_asset_to_dock_generic(is_border=True)

    def apply_dynamic_border_to_selection(self):
        """Draws a simple, vector-based border around the selected component."""
        if not self.app.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a tile from the 'Tiles' tab to apply a border to.")
            return

        comp = self.app.components.get(self.app.selected_component_tag)
        if not comp or not comp.pil_image:
            messagebox.showwarning("No Image", "The selected tile does not have an image to draw on.")
            return

        # Save state for undo
        self.app._save_undo_state({comp.tag: comp.pil_image.copy()})

        # Create a new transparent layer for the border
        border_layer = Image.new("RGBA", comp.pil_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(border_layer)

        thickness = self.border_thickness.get()
        
        # Draw the rectangle outline on the transparent layer
        draw.rectangle(
            [(0, 0), (comp.pil_image.width - 1, comp.pil_image.height - 1)],
            outline=self.border_color,
            width=thickness
        )

        # Composite the border layer onto the component's image
        final_image = Image.alpha_composite(comp.pil_image.copy(), border_layer)
        comp.set_image(final_image)
        print(f"Applied dynamic border to '{comp.tag}'.")

    def apply_asset_border_to_selection(self):
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