import tkinter as tk
from tkinter import messagebox, simpledialog
from PIL import Image, ImageDraw, ImageFilter, ImageTk
import math
import os
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("[WARNING] NumPy not found. Smart Border tool performance will be significantly degraded.")
    
from uc_border_manager2 import SmartBorderManager
from uc_component import DraggableComponent

class BorderManager:
    """Manages tracing, creating, and applying borders to the canvas."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas

        # Instantiate the sub-managers
        self.smart_manager = SmartBorderManager(app, self)

        self.next_border_id = 0

        self.preview_rect_ids = [] # DEFINITIVE FIX: Track multiple preview items
        self.preview_tk_images = [] # DEFINITIVE FIX: Hold multiple PhotoImage objects

        # --- NEW: State for finalized smart borders ---
        self.finalized_borders = {} # Stores tag -> DraggableComponent mapping
        self.finalized_border_names = ["No saved borders"]
        self.selected_finalized_border = tk.StringVar(value=self.finalized_border_names[0])

        # --- Texture Loading ---
        self.border_textures = {}
        self._load_border_textures()
        self._create_procedural_textures()

        # Set default selections for the UI

    def _load_border_textures(self):
        """Loads default border textures into memory from the images directory."""
        # In a real app, this could scan a specific 'border_textures' folder.
        # For now, we'll explicitly load a known texture.
        try:
            brick_path = os.path.join(self.app.image_base_dir, "brick.png")
            if os.path.exists(brick_path):
                self.border_textures["Brick"] = Image.open(brick_path).convert("RGBA")
                print("Loaded 'Brick' border texture.")
            # Add more textures here, e.g., "stone.png" # type: ignore
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

    # --- Method Delegation ---

    def remove_border_from_selection(self):
        pass

    def _render_border_image(self, logical_size, render_size, shape_form="rect", path_data=None, is_segmented=False, relative_to=(0,0)):
        """Renders the selected border style onto a PIL image."""
        logical_w, logical_h = int(logical_size[0]), int(logical_size[1])
        render_w, render_h = int(render_size[0]), int(render_size[1])
        texture = list(self.border_textures.values())[0] if self.border_textures else None

        if not texture or (logical_w <= 0 and logical_h <= 0):
            messagebox.showwarning("Render Error", f"Could not render border. No texture found or size is invalid.")
            return None

        final_image = Image.new("RGBA", (render_w, render_h), (0,0,0,0))

        # --- DEFINITIVE FIX: Create a mask that grows inward ---
        # 1. Create a mask for the border by drawing a filled rectangle and then
        #    drawing a smaller, empty rectangle inside it.
        mask = Image.new("L", (render_w, render_h), 0)
        draw = ImageDraw.Draw(mask)

        # --- NEW: Handle path drawing ---

        # --- NEW: Adjust mask based on growth direction ---
        if shape_form == "path" and path_data:
            if is_segmented:
                for segment in path_data:
                    if len(segment) > 1:
                        relative_segment = [(p[0] - relative_to[0], p[1] - relative_to[1]) for p in segment]
                        draw.line(relative_segment, fill=255, width=1, joint='curve')

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
        pass

    # --- NEW: Smart Border Tool Methods ---

    def toggle_smart_border_mode(self):
        self.smart_manager.toggle_smart_border_mode()

    def start_drawing_stroke(self, event):
        self.smart_manager.start_drawing_stroke(event)

    def on_mouse_drag(self, event):
        self.smart_manager.on_mouse_drag(event)

    def on_mouse_up(self, event):
        self.smart_manager.on_mouse_up(event)

    # --- NEW: Preview Canvas Event Handlers ---
    def on_preview_down(self, event):
        self.smart_manager.on_preview_down(event)

    def on_preview_drag(self, event):
        self.smart_manager.on_preview_drag(event)

    def on_preview_up(self, event):
        self.smart_manager.on_preview_up(event)

    def on_preview_leave(self, event):
        self.smart_manager.on_preview_leave(event)

    def on_preview_move(self, event):
        self.smart_manager.on_preview_move(event)

    def update_preview_canvas(self, *args):
        self.smart_manager.update_preview_canvas(*args)

    def clear_detected_points(self):
        self.smart_manager.clear_detected_points()

    def on_erase_mode_toggle(self):
        self.smart_manager.on_erase_mode_toggle()

    def _update_canvas_brush_size(self, event=None):
        self.smart_manager._update_canvas_brush_size(event)

    # --- NEW: Preview Area Selection Methods ---
    def toggle_preview_selection_mode(self):
        self.smart_manager.toggle_preview_selection_mode()

    def finalize_border(self):
        self.smart_manager.finalize_border()

    def add_finalized_border(self, border_component):
        """Adds a newly created smart border to the manager and updates the UI dropdown."""
        border_tag = border_component.tag
        self.finalized_borders[border_tag] = border_component

        # If this is the first border, remove the placeholder text
        if self.finalized_border_names == ["No saved borders"]:
            self.finalized_border_names.clear()

        self.finalized_border_names.append(border_tag)
        self.selected_finalized_border.set(border_tag)

        # Update the OptionMenu in the UI
        self.app.ui_manager.update_saved_borders_dropdown()

    def place_saved_border(self):
        """Creates a new clone of the selected saved border and places it on the canvas."""
        selected_tag = self.selected_finalized_border.get()
        if not selected_tag or selected_tag == "No saved borders":
            messagebox.showwarning("No Selection", "Please select a saved border from the dropdown to place.")
            return

        original_border_comp = self.finalized_borders.get(selected_tag)
        if not original_border_comp:
            messagebox.showerror("Error", f"Could not find the original component for '{selected_tag}'.")
            return

        # --- NEW: Create a new component at the original saved position ---
        # 1. Generate a unique tag for the new instance.
        new_tag = f"{selected_tag}_instance_{self.app.image_manager.next_dynamic_id}"
        self.app.image_manager.next_dynamic_id += 1

        # 2. Create a new DraggableComponent using the original's coordinates and image.
        new_comp = DraggableComponent(
            self.app,
            new_tag,
            original_border_comp.world_x1,
            original_border_comp.world_y1,
            original_border_comp.world_x2,
            original_border_comp.world_y2,
            "green",
            new_tag
        )
        new_comp.is_decal = True
        new_comp.original_pil_image = original_border_comp.original_pil_image.copy()
        new_comp.image_path = original_border_comp.image_path

        # 3. Add the new component to the application and draw it.
        self.app.components[new_tag] = new_comp
        self.app._bind_component_events(new_tag)
        new_comp.set_image(new_comp.original_pil_image) # This will handle the initial draw
        print(f"Placed a new instance of saved border '{selected_tag}' at its original position.")

    def rename_saved_border(self):
        """Renames the currently selected saved border."""
        selected_tag = self.selected_finalized_border.get()
        if not selected_tag or selected_tag == "No saved borders":
            messagebox.showwarning("No Selection", "Please select a saved border from the dropdown to rename.")
            return

        new_name = simpledialog.askstring("Rename Border", "Enter the new name for the border:", initialvalue=selected_tag)

        if not new_name or new_name.strip() == "":
            return # User cancelled or entered empty name

        new_name = new_name.strip()

        if new_name == selected_tag:
            return # Name is unchanged

        # Check for invalid characters or if the name is already in use by another component
        if new_name in self.app.components and new_name != selected_tag:
            messagebox.showerror("Name In Use", f"The name '{new_name}' is already in use. Please choose a different name.")
            return

        border_to_rename = self.finalized_borders.get(selected_tag)
        if not border_to_rename:
            messagebox.showerror("Error", f"Could not find the component data for '{selected_tag}'.")
            return

        # 1. Rename the image file
        old_path = border_to_rename.image_path
        if old_path and os.path.exists(old_path):
            dir_name = os.path.dirname(old_path)
            new_filename = f"{new_name}.png"
            new_path = os.path.join(dir_name, new_filename)
            try:
                os.rename(old_path, new_path)
                print(f"Renamed border file from '{os.path.basename(old_path)}' to '{new_filename}'")
            except OSError as e:
                messagebox.showerror("File Error", f"Could not rename the border file:\n{e}")
                return
        else:
            new_path = None

        # 2. Update the component object itself
        border_to_rename.tag = new_name
        border_to_rename.image_path = new_path

        # 3. Update the main application's component dictionary
        del self.app.components[selected_tag]
        self.app.components[new_name] = border_to_rename

        # 4. Update the BorderManager's state
        del self.finalized_borders[selected_tag]
        self.finalized_borders[new_name] = border_to_rename

        # 5. Update the list of names for the dropdown
        idx = self.finalized_border_names.index(selected_tag)
        self.finalized_border_names[idx] = new_name

        # 6. Update the UI
        self.selected_finalized_border.set(new_name)
        self.app.ui_manager.update_saved_borders_dropdown()
        messagebox.showinfo("Rename Successful", f"Border '{selected_tag}' has been renamed to '{new_name}'.")

    def delete_saved_border(self):
        """Deletes the currently selected saved border from the dropdown and the filesystem."""
        selected_tag = self.selected_finalized_border.get()
        if not selected_tag or selected_tag == "No saved borders":
            messagebox.showwarning("No Selection", "Please select a saved border from the dropdown to delete.")
            return

        if not messagebox.askyesno("Confirm Deletion", f"Are you sure you want to permanently delete the border '{selected_tag}'?"):
            return

        border_to_delete = self.finalized_borders.get(selected_tag)
        if not border_to_delete:
            messagebox.showerror("Error", f"Could not find the component data for '{selected_tag}'.")
            return

        # 1. Delete the image file from disk
        if border_to_delete.image_path and os.path.exists(border_to_delete.image_path):
            try:
                os.remove(border_to_delete.image_path)
                print(f"Deleted border file: {border_to_delete.image_path}")
            except OSError as e:
                messagebox.showerror("File Error", f"Could not delete the border file:\n{e}")
                return

        # 2. Remove from the application state
        del self.finalized_borders[selected_tag]
        self.finalized_border_names.remove(selected_tag)

        # 3. Reset the dropdown if it's now empty
        if not self.finalized_border_names:
            self.finalized_border_names.append("No saved borders")
        self.selected_finalized_border.set(self.finalized_border_names[0])

        self.app.ui_manager.update_saved_borders_dropdown()

    def load_finalized_border_from_path(self, image_path: str):
        """
        Recreates a finalized border component from a saved image path and adds it to the manager.
        This is used on application startup.
        """
        if not image_path or not os.path.exists(image_path):
            print(f"[WARNING] Could not reload saved border. File not found: {image_path}")
            return

        try:
            border_image = Image.open(image_path).convert("RGBA")
            border_tag = os.path.splitext(os.path.basename(image_path))[0]

            # Create a new component. The initial coordinates don't matter much as it's a template.
            new_border_comp = DraggableComponent(
                self.app, border_tag, 0, 0, border_image.width, border_image.height, "green", border_tag
            )
            new_border_comp.is_decal = True
            new_border_comp.original_pil_image = border_image.copy()
            new_border_comp.image_path = image_path # Store the path for re-saving

            # Add it to the manager's state and update the UI dropdown
            self.add_finalized_border(new_border_comp)
            print(f"[INFO] Reloaded saved border '{border_tag}' from {os.path.basename(image_path)}")

        except Exception as e:
            print(f"[ERROR] Failed to reload saved border from path '{image_path}': {e}")