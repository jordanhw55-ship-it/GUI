import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageTk
import os

from uc_component import DraggableComponent

class PresetBorderManager:
    """Manages preset-based border creation and previews."""
    def __init__(self, app, border_manager):
        self.app = app
        self.canvas = app.canvas
        self.border_manager = border_manager # Main manager for shared resources

        # --- Preset Definitions ---
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
            "Top Border": {
                "shape_type": "multi_rect",
                "shapes": [
                    { "target_tile": "humanuitile05", "shape_form": "rect", "shape_data": [0.0, 0.0859, 1.0, 0] },
                    { "target_tile": "humanuitile01", "shape_form": "rect", "shape_data": [0.0, 0.0859, 1.0, 0] },
                    { "target_tile": "humanuitile02", "shape_form": "rect", "shape_data": [0.0, 0.0859, 0.4238, 0] },
                    { "target_tile": "humanuitile02", "shape_form": "rect", "shape_data": [0.701171875, 0.0859, 0.298828125, 0] },
                    { "target_tile": "humanuitile03", "shape_form": "rect", "shape_data": [0.0, 0.0859, 1.0, 0] },
                    { "target_tile": "humanuitile04", "shape_form": "rect", "shape_data": [0.0, 0.0859, 2.1, 0] },
                    { "target_tile": "humanuitile06", "shape_form": "rect", "shape_data": [0.0, 0.0859, 1.0, 0] }
                ]
            },
            "Bottom Border": {
                "shape_type": "multi_rect",
                "shapes": [
                    { "target_tile": "humanuitile05", "shape_form": "rect", "shape_data": [0.9355, 0.3808, 0, 0.6172] },
                    { "target_tile": "humanuitile01", "shape_form": "rect", "shape_data": [0.7773, 0.3808, 0, 0.1055] },
                    { "target_tile": "humanuitile02", "shape_form": "rect", "shape_data": [0.9726, 0.4843, 0, 0] },
                    { "target_tile": "humanuitile03", "shape_form": "rect", "shape_data": [0.3339, 0.4004, 0, 0.0605] },
                    { "target_tile": "humanuitile06", "shape_form": "rect", "shape_data": [0.0605, 0.4004, 0, 0.6055] },
                    { "target_tile": "humanuitile05", "shape_form": "rect", "shape_data": [0.0, 0.92, 1.0, 0.08] }
                ]
            },
            "Side Frame": {
                "shape_type": "multi_span_path",
                "segments": [
                    { "type": "path", "path_coords": [(479, 511), (479, 186), (512, 186)] }
                ]
            },
            "Minimap Buttons": {
                "target_tile": "humanuitile01",
                "shape_type": "multi_rect",
                "shapes": [
                    { "shape_form": "rect", "shape_data": [0.6035, 0.4375, 0.0898, 0.0801] },
                    { "shape_form": "rect", "shape_data": [0.6035, 0.5234, 0.0898, 0.0781] },
                    { "shape_form": "rect", "shape_data": [0.6035, 0.6094, 0.0898, 0.0781] },
                    { "shape_form": "rect", "shape_data": [0.6035, 0.6953, 0.0898, 0.0781] },
                    { "shape_form": "circle", "shape_data": [0.6055, 0.8027, 0.0859, 0.0801] }
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
                "shape_data": [430, 455, 69, 24]
            },
            "Mana Frame": {
                "shape_type": "span_rect",
                "start_tile": "humanuitile01", "end_tile": "humanuitile02",
                "shape_data": [430, 484, 69, 24]
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

    def apply_preset_border(self):
        """Applies the selected border preset to the canvas."""
        preset_name = self.border_manager.selected_preset.get()
        self.clear_preset_preview()

        if not preset_name or preset_name == "None":
            messagebox.showwarning("Preset Required", "Please select a border preset.")
            return

        preset = self.border_presets[preset_name]

        shapes_to_create = []
        if preset.get("shape_type") == "multi_rect":
            shapes_to_create = preset.get("shapes", [])
        elif preset.get("shape_type") == "relative_rect":
            shapes_to_create = [{"shape_data": preset.get("shape_data")}]
        elif preset.get("shape_type") == "multi_span_path":
            shapes_to_create = preset.get("segments", [])
        

        for shape in shapes_to_create:
            shape_data = shape.get("shape_data")
            shape_type = preset.get("shape_type")
            world_path = None
            target_comp = None

            if shape_type == "multi_span_path":
                pass
            elif not shape_data:
                continue

            thickness = self.border_manager.border_thickness.get()
            growth_direction = self.border_manager.border_growth_direction.get()

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
                    path_tile = self.app.components.get(shape.get("target_tile"))
                    if not path_coords: continue

                    offset_x = path_tile.world_x1 if path_tile else 0
                    offset_y = path_tile.world_y1 if path_tile else 0
                    world_path = [(offset_x + x, offset_y + y) for x, y in path_coords]

                    min_x = min(p[0] for p in world_path)
                    max_x = max(p[0] for p in world_path)
                    max_y = max(p[1] for p in world_path)
                    min_y = min(p[1] for p in world_path)

                    border_x, border_y = min_x, min_y
                    border_w, border_h = max_x - min_x, max_y - min_y
                    render_w, render_h = border_w, border_h
                    shape_form = "path"
                    target_comp = path_tile
            else:
                target_tile_name = shape.get("target_tile") or preset.get("target_tile")
                target_comp = self.app.components.get(target_tile_name)

                if not target_comp:
                    messagebox.showerror("Error", f"Target tile '{target_tile_name}' for preset not found on canvas.")
                    continue

                rel_x, rel_y, rel_w, rel_h = shape["shape_data"]
                parent_w = target_comp.world_x2 - target_comp.world_x1
                parent_h = target_comp.world_y2 - target_comp.world_y1
                width_multiplier = self.border_manager.border_width.get() / 100.0
                border_w = (parent_w * rel_w) * width_multiplier if rel_w > 0 else self.border_manager.border_thickness.get()
                border_h = (parent_h * rel_h) if rel_h > 0 else self.border_manager.border_thickness.get()
                border_x = target_comp.world_x1 + (parent_w * rel_x)
                border_y = target_comp.world_y1 + (parent_h * rel_y)
                render_w, render_h = border_w, border_h
                shape_form = shape.get("shape_form", "rect")

            if growth_direction == 'out':
                border_x -= thickness
                border_y -= thickness
                render_w += thickness * 2
                render_h += thickness * 2

            border_tag = f"preset_border_{self.border_manager.next_border_id}"
            self.border_manager.next_border_id += 1
            border_comp = DraggableComponent(self.app, border_tag, border_x, border_y, border_x + render_w, border_y + render_h, "blue", "BORDER")
            border_comp.is_draggable = False
            if target_comp: border_comp.parent_tag = target_comp.tag

            border_image = self.border_manager._render_border_image((border_w, border_h), (render_w, render_h), shape_form, path_data=world_path)
            if not border_image: continue

            border_comp.set_image(border_image)
            self.app.components[border_tag] = border_comp
            self.app.canvas.tag_lower(border_tag, "draggable")
            self.app._save_undo_state({'type': 'add_component', 'tag': border_tag})

        self.app.redraw_all_zoomable()
        print(f"Applied preset '{preset_name}'.")

    def show_preset_preview(self, event=None):
        """Draws a temporary, semi-transparent rectangle to preview the preset border."""
        if not self.app.is_border_tab_active():
            return

        self.clear_preset_preview()

        preset_name = self.border_manager.selected_preset.get()
        if not preset_name or preset_name == "None":
            return

        preset = self.border_presets.get(preset_name)
        if not preset:
            return

        shapes_to_preview = []
        shape_type = preset.get("shape_type")

        if shape_type == "multi_span_path":
            for segment in preset.get("segments", []):
                thickness = self.border_manager.border_thickness.get()
                if segment["type"] == "line":
                    start_tile = self.app.components.get(segment["start_tile"])
                    end_tile = self.app.components.get(segment["end_tile"])
                    if not start_tile or not end_tile: continue

                    start_x_world = start_tile.world_x1 + segment["start_coords"][0]
                    start_y_world = start_tile.world_y1 + segment["start_coords"][1]
                    end_x_world = end_tile.world_x1 + segment["end_coords"][0]
                    end_y_world = end_tile.world_y1 + segment["end_coords"][1]

                    shapes_to_preview.append({
                        'x': min(start_x_world, end_x_world), 'y': min(start_y_world, end_y_world),
                        'w': abs(end_x_world - start_x_world), 'h': abs(end_y_world - start_y_world) if abs(end_y_world - start_y_world) > 0 else thickness,
                        'form': 'rect'
                    })
                elif segment["type"] == "path":
                    path_tile = self.app.components.get(segment.get("target_tile"))
                    if not segment.get("path_coords"): continue

                    offset_x = path_tile.world_x1 if path_tile else 0
                    offset_y = path_tile.world_y1 if path_tile else 0
                    world_path = [(offset_x + x, offset_y + y) for x, y in segment["path_coords"]]
                    
                    min_x, max_x = min(p[0] for p in world_path), max(p[0] for p in world_path)
                    min_y, max_y = min(p[1] for p in world_path), max(p[1] for p in world_path)
                    
                    shapes_to_preview.append({
                        'x': min_x, 'y': min_y, 'w': max_x - min_x, 'h': max_y - min_y,
                        'form': 'path', 'path_data': world_path
                    })
        elif shape_type == "span_rect":
            start_tile = self.app.components.get(preset["start_tile"])
            end_tile = self.app.components.get(preset["end_tile"])
            if not start_tile or not end_tile: return

            start_x_offset, start_y_offset, end_x_offset, height_px = preset["shape_data"]

            start_tile_world_w = start_tile.world_x2 - start_tile.world_x1
            start_tile_world_h = start_tile.world_y2 - start_tile.world_y1
            start_scale_w = start_tile_world_w / (start_tile.original_pil_image.width if start_tile.original_pil_image else 512.0)
            start_scale_h = start_tile_world_h / (start_tile.original_pil_image.height if start_tile.original_pil_image else 512.0)

            end_tile_world_w = end_tile.world_x2 - end_tile.world_x1
            end_scale_w = end_tile_world_w / (end_tile.original_pil_image.width if end_tile.original_pil_image else 512.0)

            border_x1 = start_tile.world_x1 + (start_x_offset * start_scale_w)
            border_y1 = start_tile.world_y1 + (start_y_offset * start_scale_h)
            border_x2 = end_tile.world_x1 + (end_x_offset * end_scale_w)
            border_y2 = border_y1 + (height_px * start_scale_h)

            border_w = (border_x2 - border_x1) + 1
            border_h = border_y2 - border_y1
            
            shapes_to_preview.append({'x': border_x1, 'y': border_y1, 'w': border_w, 'h': border_h, 'form': 'rect'})

        elif shape_type == "multi_rect":
            shapes_to_preview = []
            width_multiplier = self.border_manager.border_width.get() / 100.0

            global_target_comp = self.app.components.get(preset.get("target_tile"))

            for i, shape in enumerate(preset.get("shapes", [])):
                if not shape.get("shape_data"): continue

                shape_target_comp = self.app.components.get(shape.get("target_tile")) or global_target_comp
                if not shape_target_comp: continue

                shape_parent_w = shape_target_comp.world_x2 - shape_target_comp.world_x1
                shape_parent_h = shape_target_comp.world_y2 - shape_target_comp.world_y1

                rel_x, rel_y, rel_w, rel_h = shape["shape_data"]

                border_w = (shape_parent_w * rel_w) * width_multiplier if rel_w > 0 else self.border_manager.border_thickness.get()
                border_h = (shape_parent_h * rel_h) if rel_h > 0 else self.border_manager.border_thickness.get()
                border_x1 = shape_target_comp.world_x1 + (shape_parent_w * rel_x)
                border_y1 = shape_target_comp.world_y1 + (shape_parent_h * rel_y)
                
                shapes_to_preview.append({
                    'x': border_x1, 'y': border_y1,
                    'w': border_w, 'h': border_h,
                    'form': shape.get("shape_form", "rect")
                })
            
            if not shapes_to_preview: return

        elif shape_type == "relative_rect":
            target_comp = self.app.components.get(preset["target_tile"])
            if not target_comp:
                return

            parent_w = target_comp.world_x2 - target_comp.world_x1
            parent_h = target_comp.world_y2 - target_comp.world_y1
            rel_x, rel_y, rel_w, rel_h = preset["shape_data"]

            width_multiplier = self.border_manager.border_width.get() / 100.0
            border_w = (parent_w * rel_w) * width_multiplier if rel_w > 0 else self.border_manager.border_thickness.get()
            border_h = (parent_h * rel_h) if rel_h > 0 else self.border_manager.border_thickness.get()

            border_x1 = target_comp.world_x1 + (parent_w * rel_x)
            border_y1 = target_comp.world_y1 + (parent_h * rel_y)
            
            shapes_to_preview.append({'x': border_x1, 'y': border_y1, 'w': border_w, 'h': border_h, 'form': 'rect'})

        for shape_coords in shapes_to_preview:
            border_x1, border_y1, border_w, border_h, shape_form = shape_coords['x'], shape_coords['y'], shape_coords['w'], shape_coords['h'], shape_coords['form']
            
            growth_direction = self.border_manager.border_growth_direction.get()
            thickness = self.border_manager.border_thickness.get()
            
            render_w_world, render_h_world = border_w, border_h
            preview_x1, preview_y1 = border_x1, border_y1
            if growth_direction == 'out':
                preview_x1 -= thickness
                preview_y1 -= thickness
                render_w_world += thickness * 2
                render_h_world += thickness * 2

            preview_image = self.border_manager._render_border_image((border_w, border_h), (render_w_world, render_h_world), shape_form, shape_coords.get('path_data'))
            if not preview_image: continue

            self.border_manager.preview_tk_images.append(ImageTk.PhotoImage(preview_image))

            sx1, sy1 = self.app.camera.world_to_screen(preview_x1, preview_y1)
            preview_id = self.canvas.create_image(
                sx1, sy1,
                anchor=tk.NW,
                image=self.border_manager.preview_tk_images[-1],
                tags=("border_preview",)
            )
            self.border_manager.preview_rect_ids.append(preview_id)

        self.canvas.tag_raise("border_preview")

    def clear_preset_preview(self):
        """Removes the preset preview rectangle from the canvas if it exists."""
        if self.border_manager.preview_rect_ids:
            self.canvas.delete("border_preview")
            self.border_manager.preview_rect_ids.clear()
            self.border_manager.preview_tk_images.clear()