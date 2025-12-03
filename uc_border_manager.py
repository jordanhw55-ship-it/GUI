import tkinter as tk
from tkinter import colorchooser, messagebox
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import numpy as np
import os

from uc_component import DraggableComponent

class BorderManager:
    """Manages tracing, creating, and applying borders to the canvas."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.next_border_id = 0

        # --- UI-related state variables ---
        self.selected_preset = tk.StringVar()
        self.selected_style = tk.StringVar()
        self.border_thickness = tk.IntVar(value=10)
        self.border_width = tk.IntVar(value=100) # NEW: For adjusting border component width as a percentage

        # --- Preset Definitions ---
        # A dictionary where each key is a preset name.
        # 'target_tile': The component tag the border is relative to.
        # 'shape_data': A list of ratios [x_offset, y_offset, width, height]
        #               relative to the target tile's dimensions.
        self.border_presets = {
            "Minimap Border": {
                "target_tile": "humanuitile01",
                "shape_type": "relative_rect",
                "shape_data": [0.0390625, 0.431640625, 0.5390625, 0.5390625] # High-precision values for the minimap cutout, shifted 1px right/down
            },
            "Action Bar Top Edge": {
                "target_tile": "humanuitile02",
                "shape_type": "relative_rect",
                "shape_data": [0.0, 0.0, 1.0, 0.05] # Thin bar across the top
            }
        }

        # --- Texture Loading ---
        self.border_textures = {}
        self._load_border_textures()

        # Set default selections for the UI
        if self.border_presets:
            self.selected_preset.set(list(self.border_presets.keys())[0])
        if self.border_textures:
            self.selected_style.set(list(self.border_textures.keys())[0])

    def _load_border_textures(self):
        """Loads default border textures into memory from the images directory."""
        # In a real app, this could scan a specific 'border_textures' folder.
        # For now, we'll explicitly load a known texture.
        try:
            brick_path = os.path.join(self.app.image_base_dir, "brick.png")
            if os.path.exists(brick_path):
                self.border_textures["Brick"] = Image.open(brick_path).convert("RGBA")
                print("Loaded 'Brick' border texture.")
            # Add more textures here, e.g., "stone.png"
        except Exception as e:
            print(f"Could not load default border textures: {e}")

    def apply_preset_border(self):
        """Applies the selected border preset to the canvas."""
        preset_name = self.selected_preset.get()
        if not preset_name:
            messagebox.showwarning("Preset Required", "Please select a border preset.")
            return

        preset = self.border_presets[preset_name]
        target_comp = self.app.components.get(preset["target_tile"])

        if not target_comp:
            messagebox.showerror("Error", f"Target tile '{preset['target_tile']}' for preset not found on canvas.")
            return

        # Calculate absolute coordinates from relative data
        parent_w = target_comp.world_x2 - target_comp.world_x1
        parent_h = target_comp.world_y2 - target_comp.world_y1
        rel_x, rel_y, rel_w, rel_h = preset["shape_data"]

        # NEW: Adjust border component size by the width slider value
        width_multiplier = self.border_width.get() / 100.0
        border_w = (parent_w * rel_w) * width_multiplier
        border_h = (parent_h * rel_h) * width_multiplier

        border_x = target_comp.world_x1 + (parent_w * rel_x)
        border_y = target_comp.world_y1 + (parent_h * rel_y)

        # Create a new component for the border
        border_tag = f"preset_border_{self.next_border_id}"
        self.next_border_id += 1
        border_comp = DraggableComponent(self.app, border_tag, border_x, border_y, border_x + border_w, border_y + border_h, "blue", "BORDER")
        border_comp.is_draggable = False # Borders are not draggable by default
        border_comp.parent_tag = target_comp.tag # Link the border to its parent tile

        # Render the border image using the selected style and thickness
        border_image = self._render_border_image((border_w, border_h))
        if not border_image: return

        border_comp.set_image(border_image)
        self.app.components[border_tag] = border_comp
        self.app.canvas.tag_lower(border_tag, "draggable") # Send behind other components

        # --- NEW: Save state for Undo ---
        self.app._save_undo_state({'type': 'add_component', 'tag': border_tag})

        self.app.redraw_all_zoomable()
        print(f"Applied preset '{preset_name}' to '{target_comp.tag}'.")

    def apply_border_to_selection(self):
        pass # This method is now handled by the decal system

    def remove_border_from_selection(self):
        pass

    def _render_border_image(self, size):
        """Renders the selected border style onto a PIL image."""
        width, height = int(size[0]), int(size[1])
        style = self.selected_style.get()
        texture = self.border_textures.get(style)

        if not texture or width <= 0 or height <= 0:
            messagebox.showwarning("Render Error", f"Could not render border. Style '{style}' not found or size is invalid.")
            return None

        final_image = Image.new("RGBA", (width, height), (0,0,0,0))
        thickness = self.border_thickness.get()

        # 1. Create a mask for the border outline
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        draw.rectangle([(0,0), (width-1, height-1)], fill=0, outline=255, width=thickness)

        # 2. Create a layer with the tiled texture
        tiled_texture_layer = Image.new("RGBA", (width, height))
        for y in range(0, height, texture.height):
            for x in range(0, width, texture.width):
                tiled_texture_layer.paste(texture, (x, y))

        # 3. Composite the tiled texture onto the final image using the mask
        final_image.paste(tiled_texture_layer, (0, 0), mask)
        return final_image