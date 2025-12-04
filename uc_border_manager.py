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
        self.preview_rect_ids = [] # DEFINITIVE FIX: Track multiple preview items

        # --- UI-related state variables ---
        self.selected_preset = tk.StringVar()
        self.selected_style = tk.StringVar()
        self.border_thickness = tk.IntVar(value=10)
        self.border_width = tk.IntVar(value=100) # NEW: For adjusting border component width as a percentage
        self.border_feather = tk.IntVar(value=0)
        self.preview_tk_images = [] # DEFINITIVE FIX: Hold multiple PhotoImage objects
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
                "shape_data": [0.0390625, 0.431640625, 0.5390625, 0.5390625]
            },
            "Action Bar Top Edge": {
                "target_tile": "humanuitile02",
                "shape_type": "relative_rect",
                "shape_data": [0.0, 0.0, 1.0, 0.05] # Thin bar across the top
            },
            # --- DEFINITIVE FIX: Correctly define the full top border path ---
            "Top Border": {
                "shape_type": "multi_span_path",
                "segments": [
                    # Segment 1: Straight line across humanuitile05
                    {
                        "type": "line",
                        "start_tile": "humanuitile05", "start_coords": [0, 44],
                        "end_tile": "humanuitile05", "end_coords": [511, 44]
                    },
                    # Segment 2: Straight line across humanuitile01
                    {
                        "type": "line",
                        "start_tile": "humanuitile01", "start_coords": [0, 44],
                        "end_tile": "humanuitile01", "end_coords": [511, 44]
                    },
                    # Segment 3: Line on humanuitile02 leading to the arc
                    {
                        "type": "line",
                        "start_tile": "humanuitile02", "start_coords": [0, 44],
                        "end_tile": "humanuitile02", "end_coords": [229, 44]
                    },
                    # Segment 4: The semi-circular arc over the clock on humanuitile02
                    {
                        "type": "path",
                        "target_tile": "humanuitile02",
                        "path_coords": [
                            [229, 44], [231, 46], [233, 48], [235, 50], [237, 53], [240, 56], [243, 59], [246, 62],
                            [249, 65], [253, 68], [257, 71], [261, 74], [265, 77], [270, 80], [275, 83], [280, 86],
                            [285, 88], [291, 88], [296, 87], [301, 85], [306, 83], [311, 80], [316, 77], [320, 74],
                            [324, 71], [328, 68], [332, 65], [335, 62], [338, 59], [341, 56], [343, 53], [345, 50],
                            [347, 48], [347, 44]
                        ]
                    },
                    # Segment 5: Line on humanuitile02 after the arc
                    {
                        "type": "line",
                        "start_tile": "humanuitile02", "start_coords": [347, 44],
                        "end_tile": "humanuitile06", "end_coords": [511, 44]
                    }
                ]
            },
            # --- FIX: I'm removing the duplicate "Top Border" and "HP Frame" definitions
            # to avoid conflicts and keep the preset list clean. The multi-span and span_rect
            # versions are the correct ones to use.
            # "Top Border": {
            #     "target_tile": "humanuitile05", "shape_type": "relative_rect", "shape_data": [0.0, 0.0, 1.0, 0.08]
            # },
            # "HP Frame": { # Spans from humanuitile01 to humanuitile02
            #     "target_tile": "humanuitile01", "shape_type": "relative_rect", "shape_data": [0.83984375, 0.888671875, 1.255859375, 0.046875]
            # },
            "Bottom Border": {
                "target_tile": "humanuitile05", "shape_type": "relative_rect", "shape_data": [0.0, 0.92, 1.0, 0.08]
            },
            "Minimap Buttons": {
                "target_tile": "humanuitile01",
                "shape_type": "multi_rect",
                "shapes": [
                    { "shape_form": "rect", "shape_data": [0.6035, 0.4375, 0.0898, 0.0801] }, # Button 1
                    { "shape_form": "rect", "shape_data": [0.6035, 0.5234, 0.0898, 0.0781] }, # Button 2
                    { "shape_form": "rect", "shape_data": [0.6035, 0.6094, 0.0898, 0.0781] }, # Button 3
                    { "shape_form": "rect", "shape_data": [0.6035, 0.6953, 0.0898, 0.0781] }, # Button 4
                    { "shape_form": "circle", "shape_data": [0.6055, 0.8027, 0.0859, 0.0801] }  # Button 5 (Circle)
                ]
            },
            "Character Frame": {
                "target_tile": "humanuitile05", "shape_type": "relative_rect", "shape_data": [0.05, 0.1, 0.9, 0.15]
            },
            "Character Hub Frame": {
                "target_tile": "humanuitile06", "shape_type": "relative_rect", "shape_data": [0.0, 0.0, 1.0, 1.0]
            },
            "HP Frame": {
                "shape_type": "span_rect",
                "start_tile": "humanuitile01", "end_tile": "humanuitile02",
                "shape_data": [430, 455, 69, 24] # [start_x_offset, start_y_offset, end_x_offset, height_px]
            },
            "Mana Frame": {
                "shape_type": "span_rect",
                "start_tile": "humanuitile01", "end_tile": "humanuitile02",
                "shape_data": [430, 484, 69, 24] # [start_x_offset, start_y_offset, end_x_offset, height_px]
            },
            "Inventory Title": {
                "target_tile": "humanuitile-inventorycover", "shape_type": "relative_rect", "shape_data": [0.1, 0.05, 0.8, 0.1]
            },
            "Inventory Slots": {
                "target_tile": "humanuitile-inventorycover", "shape_type": "relative_rect", "shape_data": [0.1, 0.2, 0.8, 0.75]
            },
            "Spells Slots": {
                "target_tile": "humanuitile02", "shape_type": "relative_rect", "shape_data": [0.05, 0.1, 0.9, 0.8]
            },
            "Time Indicator Border": {
                "target_tile": "humanuitile-timeindicatorframe", "shape_type": "relative_rect", "shape_data": [0.0, 0.0, 1.0, 1.0]
            }
        }
        # --- Texture Loading ---
        self.border_textures = {}
        self._load_border_textures()
        self._create_procedural_textures()

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

    def _create_procedural_textures(self):
        """Creates simple, built-in border textures programmatically to offer more default options."""
        try:
            # Checkerboard
            size = 16
            c1 = (60, 60, 60, 255)  # Dark gray
            c2 = (80, 80, 80, 255)  # Lighter gray
            checker_img = Image.new("RGBA", (size, size), (0,0,0,0))
            draw = ImageDraw.Draw(checker_img)
            for y in range(0, size, size // 2):
                for x in range(0, size, size // 2):
                    color = c1 if (x // (size // 2) + y // (size // 2)) % 2 == 0 else c2
                    draw.rectangle([x, y, x + size // 2, y + size // 2], fill=color)
            self.border_textures["Checkerboard"] = checker_img

            # Diagonal Lines
            diag_img = Image.new("RGBA", (size, size), (0,0,0,0))
            draw = ImageDraw.Draw(diag_img)
            line_color = (100, 100, 100, 255)
            for i in range(-size, size, 4):
                draw.line([(i, 0), (i + size, size)], fill=line_color, width=1)
            self.border_textures["Diagonal Lines"] = diag_img

            # Vertical Stripes
            v_stripes_img = Image.new("RGBA", (size, size), c1)
            draw = ImageDraw.Draw(v_stripes_img)
            draw.rectangle([size // 2, 0, size, size], fill=c2)
            self.border_textures["Vertical Stripes"] = v_stripes_img
            print("Created procedural border textures.")
        except Exception as e:
            print(f"Could not create procedural textures: {e}")

    def apply_preset_border(self):
        """Applies the selected border preset to the canvas."""
        preset_name = self.selected_preset.get()
        # --- NEW: Clear the preview when applying the border ---
        self.clear_preset_preview()

        if not preset_name:
            messagebox.showwarning("Preset Required", "Please select a border preset.")
            return

        preset = self.border_presets[preset_name]

        # --- NEW: Handle multi-shape presets ---
        if preset.get("shape_type") == "multi_rect":
            shapes_to_create = preset.get("shapes", [])
        elif preset.get("shape_type") == "relative_rect":
            # For backward compatibility, treat single presets as a list with one item
            shapes_to_create = [{"shape_data": preset.get("shape_data")}]
        elif preset.get("shape_type") == "multi_span_path":
            # For the new complex path type, we create one component per segment
            shapes_to_create = preset.get("segments", [])
        else:
            shapes_to_create = []

        for shape in shapes_to_create:
            # --- NEW: Handle different shape data structures ---
            shape_data = shape.get("shape_data")
            shape_type = preset.get("shape_type")

            if shape_type == "multi_span_path":
                # For paths, the logic is different. We'll handle it inside the loop.
                pass
            elif not shape_data:
                continue

            # Determine the target component
            # --- FIX: Correctly determine the target tile for error messages and parenting ---
            target_tile_name = preset.get("target_tile") or shape.get("target_tile") or shape.get("start_tile")
            target_comp = self.app.components.get(target_tile_name)

            if not target_comp:
                messagebox.showerror("Error", f"Target tile '{target_tile_name}' for preset not found on canvas.")
                continue # Use continue to skip the problematic segment instead of stopping the whole process

            parent_w = target_comp.world_x2 - target_comp.world_x1
            parent_h = target_comp.world_y2 - target_comp.world_y1
            rel_x, rel_y, rel_w, rel_h = shape["shape_data"]
            thickness = self.border_thickness.get()
            growth_direction = self.border_growth_direction.get()

            if shape_type == "multi_span_path":
                segment_type = shape.get("type")
                if segment_type == "line":
                    start_tile = self.app.components.get(shape["start_tile"])
                    end_tile = self.app.components.get(shape["end_tile"])
                    if not start_tile or not end_tile: continue

                    start_x_world = start_tile.world_x1 + shape["start_coords"][0]
                    start_y_world = start_tile.world_y1 + shape["start_coords"][1]
                    end_x_world = end_tile.world_x1 + shape["end_coords"][0]
                    end_y_world = end_tile.world_y1 + shape["end_coords"][1]

                    border_x = min(start_x_world, end_x_world)
                    border_y = min(start_y_world, end_y_world)
                    border_w = abs(end_x_world - start_x_world)
                    border_h = abs(end_y_world - start_y_world) if abs(end_y_world - start_y_world) > 0 else thickness
                    render_w, render_h = border_w, border_h
                    shape_form = "rect"

                elif segment_type == "path":
                    path_coords = shape["path_coords"]
                    path_tile = self.app.components.get(shape["target_tile"])
                    if not path_tile or not path_coords: continue

                    world_path = [(path_tile.world_x1 + x, path_tile.world_y1 + y) for x, y in path_coords]
                    min_x = min(p[0] for p in world_path)
                    max_x = max(p[0] for p in world_path)
                    min_y = min(p[1] for p in world_path)
                    max_y = max(p[1] for p in world_path)

                    border_x, border_y = min_x, min_y
                    border_w, border_h = max_x - min_x, max_y - min_y
                    render_w, render_h = border_w, border_h
                    shape_form = "path"
            else: # Existing rect/circle logic
                width_multiplier = self.border_width.get() / 100.0
                border_w = (parent_w * rel_w) * width_multiplier
                border_h = (parent_h * rel_h) * width_multiplier
                border_x = target_comp.world_x1 + (parent_w * rel_x)
                border_y = target_comp.world_y1 + (parent_h * rel_y)
                render_w, render_h = border_w, border_h
                shape_form = shape.get("shape_form", "rect")

            if growth_direction == 'out':
                border_x -= thickness; border_y -= thickness
                render_w += thickness * 2; render_h += thickness * 2

            border_tag = f"preset_border_{self.next_border_id}"
            self.next_border_id += 1
            border_comp = DraggableComponent(self.app, border_tag, border_x, border_y, border_x + render_w, border_y + render_h, "blue", "BORDER")
            border_comp.is_draggable = False
            border_comp.parent_tag = target_comp.tag # Assign parent

            # --- FIX: Use the determined shape_form, not the one from the shape dictionary ---
            border_image = self._render_border_image((border_w, border_h), (render_w, render_h), shape_form)
            if not border_image: continue

            border_comp.set_image(border_image)
            self.app.components[border_tag] = border_comp
            self.app.canvas.tag_lower(border_tag, "draggable")
            self.app._save_undo_state({'type': 'add_component', 'tag': border_tag})

        self.app.redraw_all_zoomable()
        print(f"Applied preset '{preset_name}'.")

    def _get_shapes_from_preset(self, preset):
        """Helper to return a list of shapes from a preset, handling single and multi-shape types."""
        return preset.get("shapes", [{"shape_form": "rect", "shape_data": preset.get("shape_data")}])

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

        shapes_to_preview = []

        # --- DEFINITIVE FIX: Restructure logic to handle each shape type explicitly ---
        shape_type = preset.get("shape_type")

        if shape_type == "multi_span_path":
            for segment in preset.get("segments", []):
                thickness = self.border_thickness.get()
                if segment["type"] == "line":
                    start_tile = self.app.components.get(segment["start_tile"])
                    end_tile = self.app.components.get(segment["end_tile"])
                    if not start_tile or not end_tile: continue

                    start_x = start_tile.world_x1 + segment["start_coords"][0]
                    start_y = start_tile.world_y1 + segment["start_coords"][1]
                    end_x = end_tile.world_x1 + segment["end_coords"][0]
                    end_y = end_tile.world_y1 + segment["end_coords"][1]

                    shapes_to_preview.append({
                        'x': min(start_x, end_x), 'y': min(start_y, end_y),
                        'w': abs(end_x - start_x), 'h': abs(end_y - start_y) if abs(end_y - start_y) > 0 else thickness,
                        'form': 'rect'
                    })
                elif segment["type"] == "path":
                    path_tile = self.app.components.get(segment["target_tile"])
                    if not path_tile: continue
                    world_path = [(path_tile.world_x1 + x, path_tile.world_y1 + y) for x, y in segment["path_coords"]]
                    
                    min_x, max_x = min(p[0] for p in world_path), max(p[0] for p in world_path)
                    min_y, max_y = min(p[1] for p in world_path), max(p[1] for p in world_path)
                    
                    shapes_to_preview.append({
                        'x': min_x, 'y': min_y, 'w': max_x - min_x, 'h': max_y - min_y,
                        'form': 'path', 'path_data': world_path
                    })
        # --- DEFINITIVE FIX: Handle the new "span_rect" shape type ---
        elif shape_type == "span_rect":
            start_tile = self.app.components.get(preset["start_tile"])
            end_tile = self.app.components.get(preset["end_tile"])
            if not start_tile or not end_tile: return

            start_x_offset, start_y_offset, end_x_offset, height_px = preset["shape_data"]

            # --- LOGIC FIX: Correctly scale pixel offsets to world coordinates ---
            # Calculate scale factor based on the tile's original image size (e.g., 512x512) vs its current world size.
            start_tile_world_w = start_tile.world_x2 - start_tile.world_x1
            start_tile_world_h = start_tile.world_y2 - start_tile.world_y1
            start_scale_w = start_tile_world_w / (start_tile.original_pil_image.width if start_tile.original_pil_image else 512.0)
            start_scale_h = start_tile_world_h / (start_tile.original_pil_image.height if start_tile.original_pil_image else 512.0)

            end_tile_world_w = end_tile.world_x2 - end_tile.world_x1
            end_tile_world_h = end_tile.world_y2 - end_tile.world_y1
            end_scale_w = end_tile_world_w / (end_tile.original_pil_image.width if end_tile.original_pil_image else 512.0)
            end_scale_h = end_tile_world_h / (end_tile.original_pil_image.height if end_tile.original_pil_image else 512.0)

            # Calculate the final world coordinates using the scaled offsets
            border_x1 = start_tile.world_x1 + (start_x_offset * start_scale_w)
            border_y1 = start_tile.world_y1 + (start_y_offset * start_scale_h)
            border_x2 = end_tile.world_x1 + (end_x_offset * end_scale_w)
            border_y2 = border_y1 + (height_px * start_scale_h)

            border_w = (border_x2 - border_x1) + 1 # Add 1px to fix off-by-one rendering error
            border_h = border_y2 - border_y1
            
            # Since span_rect is a single shape, we wrap it in a list to use the common render logic below
            shapes_to_preview.append({'x': border_x1, 'y': border_y1, 'w': border_w, 'h': border_h, 'form': 'rect'})

        elif shape_type == "multi_rect":
            shapes_to_preview = []
            target_comp = self.app.components.get(preset["target_tile"])
            if not target_comp: return

            parent_w = target_comp.world_x2 - target_comp.world_x1
            parent_h = target_comp.world_y2 - target_comp.world_y1
            width_multiplier = self.border_width.get() / 100.0

            for i, shape in enumerate(preset.get("shapes", [])):
                if not shape.get("shape_data"): continue
                rel_x, rel_y, rel_w, rel_h = shape["shape_data"]

                border_w = (parent_w * rel_w) * width_multiplier
                border_h = (parent_h * rel_h) * width_multiplier
                border_x1 = target_comp.world_x1 + (parent_w * rel_x)
                border_y1 = target_comp.world_y1 + (parent_h * rel_y)
                
                shapes_to_preview.append({
                    'x': border_x1, 'y': border_y1,
                    'w': border_w, 'h': border_h,
                    'form': shape.get("shape_form", "rect") # Pass the shape form to the preview
                })
            
            if not shapes_to_preview: return # No valid shapes found

        elif shape_type == "relative_rect": # Handle the original "relative_rect"
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
            
            # Also wrap single rects in a list to use the common render logic
            shapes_to_preview.append({'x': border_x1, 'y': border_y1, 'w': border_w, 'h': border_h, 'form': 'rect'})

        # --- DEFINITIVE FIX: Render the actual border for the preview ---
        # This now loops through all shapes calculated above (even if it's just one)
        for shape_coords in shapes_to_preview:
            border_x1, border_y1, border_w, border_h, shape_form = shape_coords['x'], shape_coords['y'], shape_coords['w'], shape_coords['h'], shape_coords['form']
            
            growth_direction = self.border_growth_direction.get()
            thickness = self.border_thickness.get()
            
            render_w_world, render_h_world = border_w, border_h
            preview_x1, preview_y1 = border_x1, border_y1
            if growth_direction == 'out':
                preview_x1 -= thickness
                preview_y1 -= thickness
                render_w_world += thickness * 2
                render_h_world += thickness * 2

            preview_image = self._render_border_image((border_w, border_h), (render_w_world, render_h_world), shape_form, shape_coords.get('path_data'))
            if not preview_image: continue

            self.preview_tk_image = ImageTk.PhotoImage(preview_image)
            self.preview_tk_images.append(ImageTk.PhotoImage(preview_image))

            sx1, sy1 = self.app.camera.world_to_screen(preview_x1, preview_y1)
            preview_id = self.canvas.create_image(
                sx1, sy1,
                anchor=tk.NW,
                image=self.preview_tk_images[-1], # Use the most recently added image
                tags=("border_preview",)
            )
            self.preview_rect_ids.append(preview_id)

        # --- FIX: Ensure the preview is always drawn on top of other items ---
        self.canvas.tag_raise("border_preview")

    def apply_border_to_selection(self):
        pass # This method is now handled by the decal system

    def remove_border_from_selection(self):
        pass

    def _render_border_image(self, logical_size, render_size, shape_form="rect", path_data=None):
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

        # --- NEW: Handle path drawing ---
        if shape_form == "path" and path_data:
            # The path_data is in world coordinates. We need to make it relative to the render box.
            min_x = min(p[0] for p in path_data)
            min_y = min(p[1] for p in path_data)
            relative_path = [(p[0] - min_x, p[1] - min_y) for p in path_data]
            
            # Draw the path as a series of lines with the specified thickness
            draw.line(relative_path, fill=255, width=thickness, joint="curve")

        # --- NEW: Adjust mask based on growth direction ---
        elif growth_direction == 'in':
            if shape_form == "circle":
                draw.ellipse([0, 0, logical_w, logical_h], fill=255)
                if logical_w > thickness * 2 and logical_h > thickness * 2:
                    draw.ellipse([thickness, thickness, logical_w - thickness, logical_h - thickness], fill=0)
            elif shape_form == "rect":
                draw.rectangle([0, 0, logical_w, logical_h], fill=255)
                if logical_w > thickness * 2 and logical_h > thickness * 2:
                    draw.rectangle([thickness, thickness, logical_w - thickness, logical_h - thickness], fill=0)
            # Path with 'in' growth is complex and not fully supported in this simplified render.
            # The line drawing above serves as the primary shape.

        else: # 'out'
            if shape_form == "circle":
                draw.ellipse([0, 0, render_w, render_h], fill=255)
                if render_w > thickness * 2 and render_h > thickness * 2:
                    # The inner cutout is inset by the thickness.
                    draw.ellipse([thickness, thickness, render_w - thickness, render_h - thickness], fill=0)
            else: # Default to rectangle
                # Only draw the rectangle if it's not a path, to avoid overwriting the path mask
                if shape_form != "path":
                    draw.rectangle([0, 0, render_w, render_h], fill=255)
                    if render_w > thickness * 2 and render_h > thickness * 2:
                        draw.rectangle([thickness, thickness, render_w - thickness, render_h - thickness], fill=0)
                        
        # --- NEW: Apply feathering if requested ---
        feather_amount = self.border_feather.get()
        if feather_amount > 0:
            # Use GaussianBlur for a smooth, high-quality feathering effect.
            mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_amount))

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
        if self.preview_rect_ids:
            self.canvas.delete("border_preview")
            self.preview_rect_ids.clear()
            self.preview_tk_images.clear()