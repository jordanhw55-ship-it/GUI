import tkinter as tk
from tkinter import colorchooser, messagebox
from PIL import Image, ImageDraw
import os

class BorderManager:
    """Manages loading and applying border assets."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.shape_color = "#ff0000" # Default to red

    def choose_shape_color(self):
        """Opens a color chooser and sets the shape color."""
        color_code = colorchooser.askcolor(title="Choose Shape Color", initialcolor=self.shape_color)
        if color_code and color_code[1]:
            self.shape_color = color_code[1]
            # Update the UI to show the new color
            self.app.ui_manager.shape_color_btn.config(bg=self.shape_color)
            print(f"Shape color set to: {self.shape_color}")

    def draw_rectangle_on_selection(self, x, y, width, height):
        """Draws a solid rectangle on the selected component's image."""
        if not self.app.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a tile to draw on.")
            return

        comp = self.app.components.get(self.app.selected_component_tag)
        if not comp or not comp.pil_image:
            messagebox.showwarning("No Image", "The selected tile does not have an image to draw on.")
            return

        try:
            x, y, width, height = int(x), int(y), int(width), int(height)
            if width <= 0 or height <= 0:
                raise ValueError("Dimensions must be positive.")
        except (ValueError, TypeError):
            messagebox.showerror("Invalid Input", "Please enter valid numbers for shape dimensions.")
            return

        # Save state for undo
        self.app._save_undo_state({comp.tag: comp.pil_image.copy()})

        # Draw directly on the image
        modified_image = comp.pil_image.copy()
        draw = ImageDraw.Draw(modified_image)
        draw.rectangle([x, y, x + width, y + height], fill=self.shape_color)

        # Apply the modified image back to the component
        comp.set_image(modified_image)
        print(f"Drew a rectangle on '{comp.tag}'.")

    def load_border_to_dock(self):
        """Placeholder for future border loading functionality."""
        pass

    def apply_border_to_selection(self):
        """Placeholder for future border application functionality."""
        pass

    def remove_border_from_selection(self):
        """Placeholder for future border removal functionality."""
        pass