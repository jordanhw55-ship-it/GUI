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
        self.preview_rect_id = None # NEW: To track the preview rectangle

        # --- UI-related state variables ---
        self.selected_preset = tk.StringVar()
        self.selected_style = tk.StringVar()
        self.border_thickness = tk.IntVar(value=10)
        self.border_width = tk.IntVar(value=100) # NEW: For adjusting border component width as a percentage
        self.border_growth_direction = tk.StringVar(value="in") # NEW: 'in' or 'out'

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
        # --- NEW: Clear the preview when applying the border ---
        self.clear_preset_preview()

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

        # --- FIX: Adjust component position and size for outward growth ---
        thickness = self.border_thickness.get()
        growth_direction = self.border_growth_direction.get()
        
        border_x = target_comp.world_x1 + (parent_w * rel_x)
        border_y = target_comp.world_y1 + (parent_h * rel_y)
        
        render_w, render_h = border_w, border_h
        if growth_direction == 'out':
            border_x -= thickness
            border_y -= thickness
            render_w += thickness * 2
            render_h += thickness * 2

        # Create a new component for the border
        border_tag = f"preset_border_{self.next_border_id}"
        self.next_border_id += 1
        border_comp = DraggableComponent(self.app, border_tag, border_x, border_y, border_x + render_w, border_y + render_h, "blue", "BORDER")
        border_comp.is_draggable = False # Borders are not draggable by default
        border_comp.parent_tag = target_comp.tag # Link the border to its parent tile

        # Render the border image using the selected style and thickness
        border_image = self._render_border_image((border_w, border_h), (render_w, render_h))
        if not border_image: return

        border_comp.set_image(border_image)
        self.app.components[border_tag] = border_comp
        self.app.canvas.tag_lower(border_tag, "draggable") # Send behind other components

        # --- NEW: Save state for Undo ---
        self.app._save_undo_state({'type': 'add_component', 'tag': border_tag})

        self.app.redraw_all_zoomable()
        print(f"Applied preset '{preset_name}' to '{target_comp.tag}'.")

    def show_preset_preview(self, event=None):
        """Draws a temporary, semi-transparent rectangle to preview the preset border."""
        # --- FIX: Do not show preview if the border tab is not the active context ---
        # This prevents the preview from appearing unexpectedly during startup or tab switching.
        if not self.app.is_border_tab_active():
            return

        # First, clear any existing preview
        self.clear_preset_preview()

        preset_name = self.selected_preset.get()
        if not preset_name:
            return

        preset = self.border_presets.get(preset_name)
        if not preset:
            return

        target_comp = self.app.components.get(preset["target_tile"])
        if not target_comp:
            return

        # Calculate absolute coordinates from relative data
        parent_w = target_comp.world_x2 - target_comp.world_x1
        parent_h = target_comp.world_y2 - target_comp.world_y1
        rel_x, rel_y, rel_w, rel_h = preset["shape_data"]

        width_multiplier = self.border_width.get() / 100.0
        border_w = (parent_w * rel_w) * width_multiplier
        border_h = (parent_h * rel_h) * width_multiplier

        border_x1 = target_comp.world_x1 + (parent_w * rel_x)
        border_y1 = target_comp.world_y1 + (parent_h * rel_y)
        border_x2 = border_x1 + border_w
        border_y2 = border_y1 + border_h

        # Convert world coordinates to screen coordinates for drawing
        sx1, sy1 = self.app.camera.world_to_screen(border_x1, border_y1)
        sx2, sy2 = self.app.camera.world_to_screen(border_x2, border_y2)

        # --- DEFINITIVE FIX: Draw two rectangles to represent an inward-growing border ---
        # The outer rectangle is the semi-transparent fill.
        self.preview_rect_id = self.canvas.create_rectangle(
            sx1, sy1, sx2, sy2,
            fill="#22c55e",  # A nice green color
            stipple="gray50", # This gives a semi-transparent effect
            outline="", # No outline on the fill itself
            tags=("border_preview", "fill")
        )

        # The inner rectangle is the white outline, inset from the outer edge.
        # --- DEFINITIVE FIX: Inset the outline's coordinates by half its width ---
        # This ensures the outline draws fully *inside* the green area, not centered on its edge.
        growth_direction = self.border_growth_direction.get()
        thickness_screen = self.border_thickness.get() * self.app.camera.zoom_scale
        
        # --- NEW: Adjust inset based on growth direction ---
        if growth_direction == 'in':
            inset = thickness_screen / 2
            ox1, oy1, ox2, oy2 = sx1 + inset, sy1 + inset, sx2 - inset, sy2 - inset
        else: # 'out'
            outset = thickness_screen / 2
            ox1, oy1, ox2, oy2 = sx1 - outset, sy1 - outset, sx2 + outset, sy2 + outset

        self.canvas.create_rectangle(
            ox1, oy1, ox2, oy2,
            outline="white",
            width=thickness_screen,
            tags=("border_preview", "outline")
        )

        # --- FIX: Ensure the preview is always drawn on top of other items ---
        self.canvas.tag_raise(self.preview_rect_id)

    def apply_border_to_selection(self):
        pass # This method is now handled by the decal system

    def remove_border_from_selection(self):
        pass

    def _render_border_image(self, logical_size, render_size):
        """Renders the selected border style onto a PIL image."""
        logical_w, logical_h = int(logical_size[0]), int(logical_size[1])
        render_w, render_h = int(render_size[0]), int(render_size[1])
        style = self.selected_style.get()
        texture = self.border_textures.get(style)

        if not texture or logical_w <= 0 or logical_h <= 0:
            messagebox.showwarning("Render Error", f"Could not render border. Style '{style}' not found or size is invalid.")
            return None

        final_image = Image.new("RGBA", (render_w, render_h), (0,0,0,0))
        thickness = self.border_thickness.get()
        growth_direction = self.border_growth_direction.get()

        # --- DEFINITIVE FIX: Create a mask that grows inward ---
        # 1. Create a mask for the border by drawing a filled rectangle and then
        #    drawing a smaller, empty rectangle inside it.
        mask = Image.new("L", (render_w, render_h), 0)
        draw = ImageDraw.Draw(mask)

        # --- NEW: Adjust mask based on growth direction ---
        if growth_direction == 'in':
            # FIX: Expand the outer shape by 1px to ensure the edge is solid.
            draw.rectangle([(0, 0), (logical_w, logical_h)], fill=255)
            draw.rectangle([(thickness, thickness), (logical_w - thickness, logical_h - thickness)], fill=0) # Inner cutout
        else: # 'out'
            # For outward growth, the render size is larger.
            draw.rectangle([(0, 0), (render_w, render_h)], fill=255)
            # FIX: Shrink the inner cutout by 1px to ensure the inner edge is solid.
            draw.rectangle([(thickness, thickness), (render_w - thickness - 1, render_h - thickness - 1)], fill=0)

        # 2. Create a layer with the tiled texture
        tiled_texture_layer = Image.new("RGBA", (render_w, render_h))
        for y in range(0, render_h, texture.height):
            for x in range(0, render_w, texture.width):
                tiled_texture_layer.paste(texture, (x, y))

        # 3. Composite the tiled texture onto the final image using the mask
        final_image.paste(tiled_texture_layer, (0, 0), mask)
        return final_image

    def clear_preset_preview(self):
        """Removes the preset preview rectangle from the canvas if it exists."""
        if self.preview_rect_id:
            self.canvas.delete("border_preview") # Delete all parts of the preview
            self.preview_rect_id = None