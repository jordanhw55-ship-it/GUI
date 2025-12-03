import tkinter as tk
from tkinter import colorchooser, messagebox
from PIL import Image, ImageDraw, ImageFilter

class BorderManager:
    """Manages loading and applying border assets."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        # Dynamic Border Properties
        self.border_color = "#ffffff" # Default to white
        self.border_thickness = tk.IntVar(value=5)
        self.border_style = tk.StringVar(value="Solid")
        # Effect Properties
        self.glow_enabled = tk.BooleanVar(value=False)
        self.shadow_enabled = tk.BooleanVar(value=False)
        self.effect_color = "#000000" # Default to black for shadow
        self.effect_size = tk.IntVar(value=5) # For glow radius or shadow offset

    def choose_border_color(self):
        """Opens a color chooser and sets the border color."""
        color_code = colorchooser.askcolor(title="Choose Border Color", initialcolor=self.border_color)
        if color_code and color_code[1]:
            self.border_color = color_code[1]
            # Update the UI to show the new color
            self.app.ui_manager.border_color_btn.config(bg=self.border_color)
            print(f"Border color set to: {self.border_color}")

    def choose_effect_color(self):
        """Opens a color chooser and sets the effect color."""
        color_code = colorchooser.askcolor(title="Choose Effect Color", initialcolor=self.effect_color)
        if color_code and color_code[1]:
            self.effect_color = color_code[1]
            # Update the UI to show the new color
            self.app.ui_manager.effect_color_btn.config(bg=self.effect_color)
            print(f"Effect color set to: {self.effect_color}")

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

        # Start with the original component image
        final_image = comp.pil_image.copy()
        thickness = self.border_thickness.get()
        effect_size = self.effect_size.get()
        width, height = final_image.size
        rect_bounds = [(thickness // 2, thickness // 2), (width - thickness // 2 -1, height - thickness // 2 - 1)]

        # 1. Apply Shadow (if enabled)
        if self.shadow_enabled.get():
            shadow_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow_layer)
            shadow_offset = effect_size
            shadow_bounds = [(rect_bounds[0][0] + shadow_offset, rect_bounds[0][1] + shadow_offset), 
                             (rect_bounds[1][0] + shadow_offset, rect_bounds[1][1] + shadow_offset)]
            shadow_draw.rectangle(shadow_bounds, fill=self.effect_color, width=thickness)
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_offset))
            final_image = Image.alpha_composite(final_image, shadow_layer)

        # 2. Draw the main border
        border_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(border_layer)

        if self.border_style.get() == "Solid":
            draw.rectangle(rect_bounds, outline=self.border_color, width=thickness)
        elif self.border_style.get() == "Dashed":
            dash_length = 10
            # Manually draw dashed lines for each side of the rectangle
            # Top
            for i in range(0, width, dash_length * 2):
                draw.line([(i, 0), (i + dash_length, 0)], fill=self.border_color, width=thickness)
            # Bottom
            for i in range(0, width, dash_length * 2):
                draw.line([(i, height - 1), (i + dash_length, height - 1)], fill=self.border_color, width=thickness)
            # Left
            for i in range(0, height, dash_length * 2):
                draw.line([(0, i), (0, i + dash_length)], fill=self.border_color, width=thickness)
            # Right
            for i in range(0, height, dash_length * 2):
                draw.line([(width - 1, i), (width - 1, i + dash_length)], fill=self.border_color, width=thickness)

        # 3. Apply Glow (if enabled)
        if self.glow_enabled.get():
            glow_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)
            
            # Draw a slightly thicker border on the glow layer
            glow_draw.rectangle(rect_bounds, outline=self.effect_color, width=thickness + effect_size)
            
            # Blur the glow layer
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=effect_size))
            
            # Composite the glow layer first, so the main border draws over it
            final_image = Image.alpha_composite(final_image, glow_layer)

        # 4. Composite the main border on top of everything else
        final_image = Image.alpha_composite(final_image, border_layer)

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