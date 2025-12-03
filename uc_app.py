import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import subprocess
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageEnhance, ImageChops
import os
import json

try:
    from wand.image import Image as WandImage
    import io
    WAND_AVAILABLE = True
except ImportError:
    WAND_AVAILABLE = False # type: ignore

from uc_component import DraggableComponent
from uc_camera import Camera
from uc_ui import UIManager
from uc_paint_manager import PaintManager
from uc_border_manager import BorderManager
from uc_image_manager import ImageManager

# --- NEW: Centralized Path Management ---
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

# --- CONFIGURATION (SCALED UP FOR LARGER GUI) ---
CANVAS_WIDTH = 1440  # Increased by 20% for a wider GUI
CANVAS_HEIGHT = 850  # Adjusted to fit screen real estate
SIDEBAR_WIDTH = 300  # Increased by 20%


class ImageEditorApp:
    def __init__(self, master):
        self.master = master
        master.configure(bg="#1f2937") # NEW: Set a dark background for the root window
        master.title("UI Creator")
        master.state('zoomed') # NEW: Maximize the window on startup

        # Constants
        self.CANVAS_WIDTH = CANVAS_WIDTH
        self.CANVAS_HEIGHT = CANVAS_HEIGHT
        self.SIDEBAR_WIDTH = SIDEBAR_WIDTH

        self.selected_component_tag = None
        
        # --- NEW: Painting Feature State ---
        self.resize_width = tk.StringVar()
        self.resize_height = tk.StringVar()
        self.maintain_aspect = tk.BooleanVar(value=True)
        self.resize_width.trace_add("write", self.on_resize_entry_change)
        self.resize_height.trace_add("write", self.on_resize_entry_change)

        # --- NEW: Undo Stack ---
        self.undo_stack = []
        self.MAX_UNDO_STATES = 20 # Limit memory usage
        master.bind("<Control-z>", self.undo_last_action)

        self.is_group_dragging = False # Flag to prevent single-drag during group-pan
        
        # --- NEW: Composition Area Bounds ---
        # These define the draggable area for tiles.
        # DEFINITIVE REWRITE: The top half of the canvas is the composition area.
        self.COMP_AREA_X1 = 0
        self.COMP_AREA_Y1 = 0
        self.COMP_AREA_X2 = CANVAS_WIDTH 
        self.COMP_AREA_Y2 = CANVAS_HEIGHT # Use the full canvas height

        # --- NEW: Define base paths for UI Creator resources ---
        self.base_path = get_base_path()
        self.ui_creator_contents_path = os.path.join(self.base_path, "Contents", "ui creator")
        self.image_base_dir = os.path.join(self.ui_creator_contents_path, "images")
        self.tools_dir = os.path.join(self.ui_creator_contents_path, "tools")
        self.output_dir = os.path.join(self.ui_creator_contents_path, "output")
        self.layouts_dir = os.path.join(self.ui_creator_contents_path, "layouts")
        print(f"[DEBUG] Base path: {self.base_path}")
        print(f"[DEBUG] Image dir: {self.image_base_dir}")
        print(f"[DEBUG] Output dir: {self.output_dir}")


        self.image_sets = []
        self.component_list = [
            "Show All", 
            "humanuitile01", 
            "humanuitile02", 
            "humanuitile03", 
            "humanuitile04", 
            "humanuitile05", 
            "humanuitile06", 
            "humanuitile-inventorycover", 
            "humanuitile-timeindicatorframe"
        ]

        # --- Initialize UI and Camera First ---
        # This ensures the canvas exists before components are created.
        self.ui_manager = UIManager(self)

        # Create the canvas first, as other managers depend on it.
        # The UIManager's create_canvas method assigns the canvas to self.app.canvas.
        canvas = self.ui_manager.create_canvas()

        self.border_manager = BorderManager(self)
        # --- Initialize Managers ---
        self.paint_manager = PaintManager(self)
        self.camera = Camera(self, canvas)
        self.image_manager = ImageManager(self)
        # --- Initialize Components BEFORE UI that might use them ---
        # This resolves the AttributeError by ensuring self.components exists
        # before any callbacks (like on_image_set_changed) can be triggered.
        self._initialize_components()

        # Bind canvas events now that all managers are initialized
        self.ui_manager.bind_canvas_events()

        self.ui_manager.create_ui()

        # --- Setup Image Set Callbacks AFTER components are initialized ---
        if os.path.isdir(self.image_base_dir):
            self.image_sets = [d for d in os.listdir(self.image_base_dir) if os.path.isdir(os.path.join(self.image_base_dir, d))]
        self.selected_image_set = tk.StringVar()
        self.selected_image_set.trace_add("write", self.on_image_set_changed)


        # --- 4. Auto-Load Images ---
        # If there are image sets, select the first one by default.
        # Otherwise, fall back to loading from the base images directory.
        if self.image_sets:
            self.selected_image_set.set(self.image_sets[0])
        else:
            self._attempt_auto_load_images(self.image_base_dir)
            
        # --- 5. Apply Initial Layout ---
        self.apply_preview_layout()

    def _initialize_components(self):
        """Creates the initial set of draggable components on the canvas."""
        self.components = {}
        base_color = "#1e40af"  # A more modern, vibrant blue

        # Define tile dimensions for the 4x2 grid (increased size)
        tile_width = 250
        tile_height = 300

        # Define starting coordinates for the 4x2 grid with 50px padding/spacing
        # C1_X=50, C2_X=350, C3_X=650, C4_X=950
        # R1_Y=50, R2_Y=400 (50 + 300 + 50)

        # TILE 01 (Row 1, Col 1)
        self.components['humanuitile01'] = DraggableComponent(
            self.canvas, self, "humanuitile01",
            50, 50, 300, 350,  # W:250, H:300
            base_color, "UI TILE 01"
        )

        # TILE 02 (Row 1, Col 2)
        self.components['humanuitile02'] = DraggableComponent(
            self.canvas, self, "humanuitile02",
            350, 50, 600, 350,
            base_color, "UI TILE 02"
        )

        # TILE 03 (Row 1, Col 3)
        self.components['humanuitile03'] = DraggableComponent(
            self.canvas, self, "humanuitile03",
            650, 50, 900, 350,
            base_color, "UI TILE 03"
        )

        # TILE 04 (Row 1, Col 4)
        self.components['humanuitile04'] = DraggableComponent(
            self.canvas, self, "humanuitile04",
            950, 50, 980, 350,
            base_color, "UI TILE 04"
        )

        # TILE 05 (Row 2, Col 1)
        self.components['humanuitile05'] = DraggableComponent(
            self.canvas, self, "humanuitile05",
            50, 400, 300, 700,
            base_color, "UI TILE 05"
        )

        # TILE 06 (Row 2, Col 2)
        self.components['humanuitile06'] = DraggableComponent(
            self.canvas, self, "humanuitile06",
            350, 400, 600, 700,
            base_color, "UI TILE 06"
        )

        # TILE 07 (Row 2, Col 3) - Inventory Cover (Tag matches filename)
        self.components['humanuitile-inventorycover'] = DraggableComponent(
            self.canvas, self, "humanuitile-inventorycover",
            650, 400, 770, 700,
            base_color, "INVENTORY COVER"
        )

        # TILE 08 (Row 2, Col 4) - Time Indicator Frame (Tag matches filename)
        self.components['humanuitile-timeindicatorframe'] = DraggableComponent(
            self.canvas, self, "humanuitile-timeindicatorframe",
            950, 400, 1085, 475,
            base_color, "TIME FRAME"
        )

        self.preview_layout = {
            "humanuitile01": {"coords": [261, 57, 511, 357]},
            "humanuitile02": {"coords": [511, 57, 761, 357]},
            "humanuitile03": {"coords": [761, 57, 1011, 357]},
            "humanuitile04": {"coords": [1011, 57, 1041, 357]},
            "humanuitile05": {"coords": [11, 57, 261, 357]},
            "humanuitile06": {"coords": [1041, 57, 1291, 357]},
            "humanuitile-inventorycover": {"coords": [724, 57, 844, 357]},
            "humanuitile-timeindicatorframe": {"coords": [585, 57, 720, 132]}
        }

        # Set a default selected component
        self.set_selected_component('humanuitile01')

    def move_all_main_tiles(self, dx_world, dy_world):
        """Moves all primary component tiles by a delta in world coordinates."""
        for comp in self.components.values():
            if not comp.is_dock_asset and not comp.is_decal:
                comp.world_x1 += dx_world; comp.world_y1 += dy_world
                comp.world_x2 += dx_world; comp.world_y2 += dy_world


    def _attempt_auto_load_images(self, base_dir):
        """Attempts to load images into components based on their tag and expected file name."""
        print("-" * 30)
        print(f"Attempting to auto-load images from ABSOLUTE PATH: {base_dir}")
        loaded_count = 0
        
        for tag, component in self.components.items():
            # Construct the expected file name: tag + ".png"
            filename = f"{tag}.png"
            full_path = os.path.join(base_dir, filename)
            
            if os.path.exists(full_path):
                # If the file exists, attempt to load it into the component
                try:
                    component.set_image_from_path(full_path)
                    loaded_count += 1
                except Exception as e:
                    print(f"Error loading {full_path}: {e}")
            else:
                # IMPORTANT: Print the full path that failed to help with debugging
                print(f"File not found for {tag}: {full_path}")

        print(f"Auto-load complete. {loaded_count} images loaded.")
        print("-" * 30)

    def on_image_set_changed(self, *args):
        """Called when a new image set is selected from the dropdown."""
        set_name = self.selected_image_set.get()
        if not set_name:
            return
        
        new_image_dir = os.path.join(self.image_base_dir, set_name)
        print(f"\n--- Changing image set to: {set_name} ---")
        self._attempt_auto_load_images(new_image_dir)
        # Re-apply the layout to show the newly loaded images in their correct positions.
        self.apply_preview_layout()

    def set_selected_component(self, tag):
        """Updates the tracking variable for the currently selected component."""
        self.selected_component_tag = tag
        comp = self.components.get(tag)
        if comp:
            print(f"[DEBUG] Selected component: '{tag}' | World Coords: ({int(comp.world_x1)}, {int(comp.world_y1)})")
        else:
            print(f"[DEBUG] Selected component: {tag}")
    
    def move_layer(self, direction):
        """Raises or lowers the currently selected layer's Z-order."""
        if not self.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a component layer from the list to re-order.")
            return
        
        comp = self.components.get(self.selected_component_tag)
        if comp and comp.rect_id:
            if direction == 'up':
                self.canvas.tag_raise(comp.tag)
                print(f"Layer {comp.tag} raised.")
            elif direction == 'down':
                # Note: Tkinter raises above the item specified, so this effectively lowers the selected item.
                self.canvas.tag_lower(comp.tag)
                print(f"Layer {comp.tag} lowered.")
            
            # --- FIX: Exit isolation mode after reordering to prevent selection errors ---
            # This ensures all layers are visible and selectable again.
            self.apply_preview_layout()

    def save_layout(self):
        """Saves the current coordinates of all components to a JSON file."""
        if not self.components:
            messagebox.showwarning("Empty Canvas", "No components to save.")
            return

        layout_data = {}
        for tag, comp in self.components.items():
            bbox = self.canvas.bbox(comp.rect_id)
            if bbox:
                # Store coordinates (x1, y1, x2, y2)
                layout_data[tag] = {
                    "coords": bbox 
                    # Z-order is not stored as Tkinter does not expose it easily, 
                    # but coordinates are fully saved.
                }

        os.makedirs(self.layouts_dir, exist_ok=True)
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Save Component Layout",
            initialdir=self.layouts_dir # Start in the new layouts directory
        )
        
        if filepath:
            try:
                with open(filepath, 'w') as f:
                    json.dump(layout_data, f, indent=4)
                messagebox.showinfo("Success", f"Layout saved to {os.path.basename(filepath)}")
                print(f"Layout saved to {filepath}")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save layout: {e}")

    def load_layout(self):
        """Loads coordinates for all components from a JSON file and moves them."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Load Component Layout",
            initialdir=self.layouts_dir # Start in the new layouts directory
        )
        
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    layout_data = json.load(f)
                
                # Apply coordinates
                for tag, data in layout_data.items():
                    if tag in self.components and "coords" in data:
                        # For an image anchored at NW (top-left), bbox[0] and bbox[1] are its coordinates
                        target_x1, target_y1, _, _ = data["coords"]
                        comp = self.components[tag]
                        
                        current_bbox = self.canvas.bbox(comp.rect_id)
                        if not current_bbox:
                            continue # Skip if component isn't drawn yet

                        current_x1, current_y1, _, _ = current_bbox
                        
                        # Calculate movement required (delta)
                        dx = target_x1 - current_x1
                        dy = target_y1 - current_y1
                        
                        # Apply movement
                        self.canvas.move(comp.rect_id, dx, dy)
                        if comp.text_id:
                            self.canvas.move(comp.text_id, dx, dy)


                messagebox.showinfo("Success", f"Layout loaded from {os.path.basename(filepath)}")
                print(f"Layout loaded from {filepath}")
            except json.JSONDecodeError as e:
                messagebox.showerror("Load Error", f"Invalid layout file format: The file is corrupted or not valid JSON: {e}")
            except Exception as e:
                messagebox.showerror("Load Error", f"Failed to load layout: {e}")


    def _save_undo_state(self, undo_data):
        """
        Saves an action to the undo stack.
        - For paint actions, `undo_data` is the PIL image of the paint layer *before* the change.
        - For component changes, `undo_data` is a dictionary mapping component tags to their PIL images *before* the change.
        """
        self.undo_stack.append(undo_data)
        # Limit the stack size to save memory
        if len(self.undo_stack) > self.MAX_UNDO_STATES:
            self.undo_stack.pop(0) # Remove the oldest state
        # Enable the undo button
        self.undo_button.config(state='normal')


    def undo_last_action(self, event=None):
        """Reverts the last action from the undo stack."""
        if not self.undo_stack:
            print("Undo stack is empty.")
            return

        last_state = self.undo_stack.pop()

        if isinstance(last_state, Image.Image): # It's a paint layer state
             self.paint_manager.paint_layer_image = last_state
             self.redraw_all_zoomable()
        elif isinstance(last_state, dict): # It's a component image state
            for tag, image in last_state.items():
                if tag in self.components:
                    self.components[tag]._set_pil_image(image)
                    print(f"Reverted image for component '{tag}'.")

        print("Undo successful.")
        # Disable button if stack is now empty
        if not self.undo_stack:
            self.undo_button.config(state='disabled')

    def on_canvas_resize(self, event):
        """Handles the canvas being resized, updating composition area and paint layer."""
        new_width = event.width
        new_height = event.height

        # Update the logical composition area to match the new canvas size
        self.COMP_AREA_X2 = new_width
        self.COMP_AREA_Y2 = new_height

        # If the paint layer exists, it needs to be recreated to match the new size
        if self.paint_manager.paint_layer_image:
            # We can't just resize, as drawing is based on world coords.
            # It's safer to clear it, but for now, we'll just recreate it blank.
            self.paint_manager.paint_layer_image = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
            self.redraw_all_zoomable() # Redraw to update the paint layer display

    # --- NEW: Camera Transformation Functions ---
    def redraw_all_zoomable(self, use_fast_preview=False):
        """Redraws all zoomable items based on the current camera view."""
        zoom_scale = self.camera.zoom_scale

        # Redraw all components that are meant to be zoomed/panned
        for comp in self.components.values():
            if "zoom_target" in self.canvas.gettags(comp.rect_id):
                # For components with an image, we need to resize the image itself
                # and then place it at the new screen coordinates.
                if comp.pil_image:
                    # --- FIX: Handle transition from placeholder to image ---
                    # If we have a PIL image but no TK image, it means we just loaded one.
                    # We must delete the old rectangle and create a new image item.
                    if comp.tk_image is None:
                        self.canvas.delete(comp.rect_id) # Delete the placeholder rectangle
                        # Create the new image item, initially empty. It will be configured below.
                        sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
                        comp.rect_id = self.canvas.create_image(
                            sx1, sy1,
                            anchor=tk.NW,
                            tags=(comp.tag, "draggable", "zoom_target")
                        )
                        comp._cached_screen_w, comp._cached_screen_h = -1, -1 # Reset cache

                    screen_w = (comp.world_x2 - comp.world_x1) * zoom_scale
                    screen_h = (comp.world_y2 - comp.world_y1) * zoom_scale

                    # Only regenerate the Tkinter image if the size has actually changed.
                    if screen_w > 0 and screen_h > 0 and (int(screen_w) != comp._cached_screen_w or int(screen_h) != comp._cached_screen_h):
                        comp._cached_screen_w = int(screen_w)
                        comp._cached_screen_h = int(screen_h)

                        source_img = comp.pil_image
                        if not source_img: continue

                        resample_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.LANCZOS
                        resized_img = source_img.resize((comp._cached_screen_w, comp._cached_screen_h), resample_quality)
                        comp.tk_image = ImageTk.PhotoImage(resized_img)
                        self.canvas.itemconfig(comp.rect_id, image=comp.tk_image)

                    # Always update the item's screen coordinates.
                    sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
                    self.canvas.coords(comp.rect_id, sx1, sy1)

                elif comp.text_id:
                    sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
                    sx2, sy2 = self.camera.world_to_screen(comp.world_x2, comp.world_y2)
                    self.canvas.coords(comp.rect_id, sx1, sy1, sx2, sy2)
                    self.canvas.coords(comp.text_id, (sx1 + sx2) / 2, (sy1 + sy2) / 2)
        
        # Also redraw the paint layer if it exists
        if self.paint_manager.paint_layer_id and self.paint_manager.paint_layer_image:
            orig_w, orig_h = self.paint_manager.paint_layer_image.size
            new_w, new_h = int(orig_w * zoom_scale), int(orig_h * zoom_scale)
            if new_w > 0 and new_h > 0:
                resample_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.LANCZOS
                resized_paint_img = self.paint_manager.paint_layer_image.resize((new_w, new_h), resample_quality)
                self.paint_manager.paint_layer_tk = ImageTk.PhotoImage(resized_paint_img)
                self.canvas.itemconfig(self.paint_manager.paint_layer_id, image=self.paint_manager.paint_layer_tk)
                self.canvas.coords(self.paint_manager.paint_layer_id, self.camera.pan_offset_x, self.camera.pan_offset_y)

        # Finally, ensure the status box is not obscured.
        self.canvas.tag_raise("status_box_frame") # This is not a real tag, but create_window items are always on top.
        self._keep_docks_on_top()

    def handle_tab_click(self, name):
        """Handles the logic when a sidebar button is clicked."""
        print("-" * 30)

        # --- MODIFICATION START: Implement isolation mode ---
        if name == "Show All":
            self.set_selected_component(None)
            self.apply_preview_layout()
        
        elif name in self.components:
            # Hide all other components to isolate the selected one
            for tag, comp in self.components.items():
                # Also ensure the paint layer is visible
                if self.paint_manager.paint_layer_id:
                    self.canvas.itemconfig(self.paint_manager.paint_layer_id, state='normal')

                state_to_set = 'normal' if tag == name else 'hidden'
                if comp.rect_id:
                    self.canvas.itemconfig(comp.rect_id, state=state_to_set)
                if comp.text_id:
                    self.canvas.itemconfig(comp.text_id, state=state_to_set)
            
            # Select the component (which also handles highlighting)
            self.components[name].select(self)

            # NEW: Update resize entries when a component is selected
            self.update_resize_entries()


        
        else:
            # Fallback for any component names that might be added to the list later
            self.set_selected_component(name)
            messagebox.showinfo("Layer Control", f"Layer '{name}' selected. Use 'Load Image' to assign a visual component. Note: This tile is not currently initialized on the canvas.")
            print(f"Action: Selecting layer '{name}' for potential image loading (Placeholder).")
        # --- MODIFICATION END ---

    def update_resize_entries(self):
        """Updates the width and height entry boxes with the selected component's dimensions."""
        if not self.selected_component_tag:
            self.resize_width.set("")
            self.resize_height.set("")
            return

        comp = self.components.get(self.selected_component_tag)
        if not comp: return

        bbox = self.canvas.bbox(comp.rect_id)
        # Use world coordinates for the true size, not screen-projected size
        width = int(comp.world_x2 - comp.world_x1)
        height = int(comp.world_y2 - comp.world_y1)
        self.resize_width.set(str(width))
        self.resize_height.set(str(height))

    def on_resize_entry_change(self, *args):
        """Dynamically calculates one dimension if aspect ratio is locked."""
        if not self.maintain_aspect.get() or not self.selected_component_tag:
            return

        comp = self.components.get(self.selected_component_tag)
        if not comp or not comp.original_pil_image:
            return

        # Determine which entry was changed by checking which one is currently being focused
        try:
            focused_widget = self.master.focus_get()
            if not isinstance(focused_widget, tk.Entry): return
            
            original_w, original_h = comp.original_pil_image.size
            if original_w == 0 or original_h == 0: return
            aspect_ratio = original_w / original_h

            # Check if the focused widget is one of our resize entries
            if self.resize_width.get() and focused_widget.cget('textvariable') == str(self.resize_width):
                new_width = int(self.resize_width.get())
                new_height = int(new_width / aspect_ratio)
                self.resize_height.set(str(new_height))
            elif self.resize_height.get() and focused_widget.cget('textvariable') == str(self.resize_height):
                new_height = int(self.resize_height.get())
                new_width = int(new_height * aspect_ratio)
                self.resize_width.set(str(new_width))
        except (ValueError, TclError):
            # Ignore errors from invalid (non-integer) text in entry
            pass

    def resize_selected_component(self):
        """Applies the new width and height to the selected component."""
        if not self.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a tile to resize.")
            return

        comp = self.components.get(self.selected_component_tag)
        if not comp: return

        try:
            new_w = int(self.resize_width.get())
            new_h = int(self.resize_height.get())
            if new_w <= 0 or new_h <= 0:
                raise ValueError("Dimensions must be positive.")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid positive numbers for width and height.\n\nError: {e}")
            return

        # Update the component's internal size definition
        comp.world_x2 = comp.world_x1 + new_w
        comp.world_y2 = comp.world_y1 + new_h

        # If the component has an image, re-apply it to trigger the resize.
        # Otherwise, redraw the placeholder rectangle.
        if comp.pil_image:
            comp._set_pil_image(comp.pil_image, resize_to_fit=True)
        else:
            comp._draw_placeholder(comp.world_x1, comp.world_y1, comp.world_x2, comp.world_y2, comp.canvas.itemcget(comp.rect_id, "fill"), comp.canvas.itemcget(comp.text_id, "text"))
        
        # Redraw to apply the new size within the camera view
        self.redraw_all_zoomable()
        print(f"Resized '{comp.tag}' to {new_w}x{new_h}.")

    def apply_border_to_selection(self):
        """Applies a loaded border image to the currently selected component."""
        self.border_manager.apply_border_to_selection()


    def remove_border_from_selection(self):
        """Removes the border from the currently selected component."""
        self.border_manager.remove_border_from_selection()


    def _keep_docks_on_top(self):
        """Iterates through all components and raises any dock assets to the top of the Z-order."""

    def apply_preview_layout(self):
        """Makes all components visible and moves them to the 'Show All' layout positions."""
        print("Action: Applying 'Preview All' layout.")
        
        for tag, comp in self.components.items():
            # 1. Make the component visible
            if comp.rect_id:
                self.canvas.itemconfig(comp.rect_id, state='normal')
            if comp.text_id:
                self.canvas.itemconfig(comp.text_id, state='normal')

            # 2. Move the component to its saved layout position
            if tag in self.preview_layout and "coords" in self.preview_layout[tag]:
                target_x1, target_y1, _, _ = self.preview_layout[tag]["coords"]
                
                current_bbox = self.canvas.bbox(comp.rect_id)
                if not current_bbox:
                    continue # Skip if component isn't drawn
                
                # Update the world coordinates directly, then redraw
                width = comp.world_x2 - comp.world_x1
                height = comp.world_y2 - comp.world_y1
                comp.world_x1, comp.world_y1 = target_x1, target_y1
                comp.world_x2, comp.world_y2 = target_x1 + width, target_y1 + height
                
            # 3. Reset placeholder borders
            if comp.tk_image is None:
                self.canvas.itemconfig(comp.rect_id, outline='white', width=2)
    
        # Redraw everything with the new positions
        self.redraw_all_zoomable()

    def _export_modified_images(self, export_format):
        """
        Generic export function to save modified layers as either PNG or DDS.
        `export_format` should be 'png' or 'dds'.
        """
        print("-" * 30)
        print(f"Starting export process for {export_format.upper()}...")

        if export_format not in ['png', 'dds']:
            messagebox.showerror("Export Error", f"Unsupported export format: {export_format}")
            return

        # Determine save directory based on format
        save_dir = os.path.join(self.output_dir, f"export_{export_format}")
        try:
            # Create the output directory if it doesn't exist
            os.makedirs(save_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Export Error", f"Could not create save directory: {e}")
            return

        # Get the paint layer directly from the manager
        paint_layer = None
        if self.paint_manager.paint_layer_image:
            print(f"Found paint layer to process.")
            paint_layer = self.paint_manager.paint_layer_image

        exported_count = 0
        for tag, comp in self.components.items():
            # --- FIX: Skip dock assets and their clones during export ---
            if not comp.pil_image or comp.is_dock_asset or tag.startswith("clone_"):
                continue

            # --- REFACTOR: Use the centralized compositing logic from ImageManager ---
            # This ensures that paint application during export uses the same robust,
            # zoom-independent logic as decal application.
            final_image, has_paint = self.image_manager._composite_decal_onto_image(
                target_comp=comp,
                decal_stamp_image=paint_layer,
                stamp_world_x1=0,
                stamp_world_y1=0,
                stamp_world_x2=self.CANVAS_WIDTH,
                stamp_world_y2=self.CANVAS_HEIGHT,
                is_border=False # Treat paint as a regular decal
            )

            is_decal_changed = comp.pil_image is not comp.original_pil_image
            if not is_decal_changed and not has_paint:
                continue # Skip if no decals were applied and no paint was on it

            save_path = os.path.join(save_dir, f"{tag}.{export_format}")
            try:
                # For DDS, Pillow often requires dimensions to be powers of two.
                if export_format == 'dds':
                    # --- DEFINITIVE METHOD: Use texconv.exe ---
                    # This is the most reliable way to create game-ready DDS files.
                    texconv_path = os.path.join(self.tools_dir, "texconv.exe")

                    if not os.path.exists(texconv_path):
                        messagebox.showerror("DDS Export Error", f"texconv.exe not found at:\n{texconv_path}\nPlease download it from the DirectXTex GitHub and place it there.")
                        return # Stop the entire export process

                    # 1. Save the final image as a temporary PNG file. This correctly handles alpha.
                    # We name the temp file exactly what we want the final file to be, just with a .png extension.
                    temp_png_path = os.path.join(save_dir, f"{tag}.png")
                    final_image.save(temp_png_path, format='PNG')

                    # 2. Build the command for texconv.exe
                    # -f BC3_UNORM is the format for DXT5
                    # -o specifies the output directory
                    # -y overwrites existing files
                    # We remove the '-n' flag for compatibility with older texconv versions.
                    command = [
                        texconv_path,
                        "-f", "BC3_UNORM",
                        "-o", save_dir,
                        "-y",
                        temp_png_path
                    ]
                    # Execute the command and capture output
                    result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

                    # Check if the command failed
                    if result.returncode != 0:
                        # If it failed, raise an exception with detailed output from texconv.
                        # Some tools write errors to stdout, so we include both for diagnosis.
                        stdout = result.stdout.strip()
                        stderr = result.stderr.strip()
                        error_message = f"texconv.exe failed with exit code {result.returncode}.\n\n--- Details ---\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}"
                        raise RuntimeError(error_message)

                    # 3. Clean up the temporary PNG file
                    os.remove(temp_png_path)
                else:
                    final_image.save(save_path)

                exported_count += 1
                print(f"Saved modified image to: {save_path}")
            except (Exception, RuntimeError) as e:
                print(f"Failed to save {save_path}: {e}")
                messagebox.showerror("DDS Export Error", f"Could not save '{os.path.basename(save_path)}'.\n\nDetails:\n{e}")

        if exported_count > 0:
            messagebox.showinfo("Export Complete", f"Successfully exported {exported_count} modified {export_format.upper()} files to:\n{os.path.basename(save_dir)}")
        else:
            messagebox.showinfo("Export Info", "No modified layers (from decals or painting) found to export.")

    def open_export_folder(self, export_format: str):
        """Opens the specified export folder in the system's file explorer."""
        if export_format not in ['png', 'dds']:
            return

        folder_path = os.path.join(self.output_dir, f"export_{export_format}")

        if not os.path.isdir(folder_path):
            messagebox.showinfo("Folder Not Found", f"The {export_format.upper()} export folder does not exist yet.\n\nPlease export some images first to create it.")
            return

        try:
            # os.startfile is the most direct way on Windows
            if sys.platform == "win32":
                os.startfile(folder_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    def _create_and_place_clone(self, asset_comp, event, clone_tag):
        """Helper to create, configure, and place a clone component."""
        w, h = asset_comp.original_pil_image.size
        world_x, world_y = self.camera.screen_to_world(event.x, event.y)
        return DraggableComponent(self.canvas, self, clone_tag, world_x - w/2, world_y - h/2, world_x + w/2, world_y + h/2, "green", clone_tag)

    def reset_selected_layer(self):
        """Resets the currently selected layer to its original, unmodified image."""
        if not self.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a component layer to reset.")
            return
        
        # --- NEW: Save state for Undo ---
        comp_to_reset = self.components.get(self.selected_component_tag)
        if comp_to_reset and comp_to_reset.pil_image:
            undo_data = {
                comp_to_reset.tag: comp_to_reset.pil_image.copy()
            }
            self._save_undo_state(undo_data)

        comp = self.components.get(self.selected_component_tag)
        if not comp:
            messagebox.showerror("Error", f"Could not find the component '{self.selected_component_tag}'.")
            return

        if comp.original_pil_image:
            # Revert the current image back to the original one
            comp._set_pil_image(comp.original_pil_image)
            print(f"Layer '{comp.tag}' has been reset to its original image.")
        else:
            messagebox.showinfo("No Image", f"Layer '{comp.tag}' does not have an original image to reset to.")

    def create_clone_from_asset(self, asset_comp, event):
        """Creates a new draggable component by cloning an asset from the dock."""
        if not asset_comp.original_pil_image:
            return

        # Determine if we are cloning a regular asset or a border asset
        clone_prefix = "border_" if asset_comp.is_border_asset else "clone_"

        # --- NEW: Ensure only one active image exists at a time ---
        existing_active_image = self._find_topmost_stamp_source(show_warning=False, clone_type='any')
        if existing_active_image:
            self._remove_stamp_source_component(existing_active_image)

        # Create a unique tag for the new component based on its type
        clone_tag = f"{clone_prefix}{self.next_dynamic_id}"
        self.next_dynamic_id += 1
        
        # --- REFACTORED: Create the clone at the mouse's world position ---
        world_x, world_y = self.camera.screen_to_world(event.x, event.y)
        w, h = asset_comp.original_pil_image.size
        clone_comp = DraggableComponent(self.canvas, self, clone_tag, world_x - w/2, world_y - h/2, world_x + w/2, world_y + h/2, "green", clone_tag)
        
        # --- FIX: Carry over the border flag to the clone ---
        clone_comp.is_border_asset = asset_comp.is_border_asset
        clone_comp.is_decal = True # Mark it as a decal so it can be dragged individually

        # 1. Set the clone's original image to the full-resolution one for stamping.
        clone_comp.original_pil_image = asset_comp.original_pil_image
        
        # 2. Set the clone's display image to the original for now.
        # The transform function will create and apply the transparent, scaled version.
        clone_comp._set_pil_image(asset_comp.original_pil_image, resize_to_fit=False)
        
        # Add the new clone to the main components dictionary
        self.components[clone_tag] = clone_comp

        # 3. --- CRITICAL FIX: Now that the clone exists, call the transform function ---
        # This will correctly find the new clone and apply the initial semi-transparent transform.
        self._update_active_decal_transform()

        # --- FIX: Ensure the dock itself remains on top after creating a clone ---
        self._keep_docks_on_top()

        print(f"Created clone '{clone_tag}' from asset '{asset_comp.tag}'.")

    def load_border_to_dock(self):
        """Loads a border image to the asset dock, marking it specifically as a border."""
        self.border_manager.load_border_to_dock()

    def load_asset_to_dock(self):
        """Loads a regular image to the asset dock."""
        self._load_asset_to_dock_generic(is_border=False)

    def _load_asset_to_dock_generic(self, is_border: bool):
        """Loads an image, scales it, and places it in the asset dock as a new draggable component."""
        asset_type = "Border" if is_border else "Asset"
        image_path = filedialog.askopenfilename(
            title=f"Select {asset_type} Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif")],
            initialdir=self.image_base_dir # Start in the new images directory
        )
        if not image_path:
            return

        try:
            # Load the image
            full_res_image = Image.open(image_path).convert("RGBA")

            # Create a unique tag for the new asset
            asset_tag = f"dock_{'border' if is_border else 'asset'}_{self.next_dynamic_id}"
            self.next_dynamic_id += 1

            # --- MODIFIED: Define position in the correct dock CANVAS ---
            if is_border:
                target_canvas = self.ui_manager.border_dock_canvas
                # Count existing border assets to determine position
                item_index = sum(1 for asset in self.dock_assets if asset.is_border_asset)
            else:
                target_canvas = self.ui_manager.image_dock_canvas
                # Count existing non-border assets to determine position
                item_index = sum(1 for asset in self.dock_assets if not asset.is_border_asset)

            # --- NEW: Wrapping Grid Layout Logic ---
            items_per_row = 4
            padding = 10
            asset_width = 128 # Use a fixed size for dock assets
            asset_height = 128 # Use a fixed size for dock assets

            col = item_index % items_per_row
            row = item_index // items_per_row

            x = padding + col * (asset_width + padding)
            y = padding + row * (asset_height + padding)

            asset_comp = DraggableComponent(target_canvas, self, asset_tag, x, y, x + asset_width, y + asset_height, "blue", "ASSET")
            asset_comp.is_dock_asset = True # Mark it as a dock asset
            asset_comp.is_border_asset = is_border # NEW: Mark if it's a border

            # --- NEW: Override the on_press for dock assets to use main canvas coordinates ---
            target_canvas.tag_bind(asset_tag, '<Button-1>', 
                lambda event, comp=asset_comp: self.handle_dock_asset_press(event, comp))

            # Store both the original and a preview version
            asset_comp.original_pil_image = full_res_image
            asset_comp.preview_pil_image = full_res_image.copy()
            asset_comp.preview_pil_image.thumbnail((asset_width, asset_height), Image.Resampling.LANCZOS)
            
            # Set the image, which will use the preview because `is_dock_asset` is true
            asset_comp._set_pil_image(asset_comp.preview_pil_image, resize_to_fit=True)

            # Add to our list of assets and update the next position
            self.components[asset_tag] = asset_comp # Add to main components list
            self.dock_assets.append(asset_comp) # Also add to the specific dock asset list
            
            # --- NEW: Update the scroll region of the dock canvas ---
            target_canvas.config(scrollregion=target_canvas.bbox("all"))

            print(f"{asset_type} '{os.path.basename(image_path)}' loaded into dock.")

        except Exception as e:
            messagebox.showerror(f"{asset_type} Load Error", f"Could not load {asset_type.lower()} image: {e}")

    def handle_dock_asset_press(self, event, asset_comp):
        """
        A new handler for when a dock asset is clicked. It translates the click
        event to the main canvas's coordinate system before creating a clone.
        """
        # Get the dock canvas that was clicked
        dock_canvas = event.widget
        
        # Get the absolute screen coordinates of the click
        abs_x = dock_canvas.winfo_rootx() + event.x
        abs_y = dock_canvas.winfo_rooty() + event.y

        # Convert the absolute screen coordinates to be relative to the main canvas
        main_canvas_x = abs_x - self.canvas.winfo_rootx()
        main_canvas_y = abs_y - self.canvas.winfo_rooty()

        # Create a new synthetic event object with the corrected coordinates
        corrected_event = tk.Event()
        corrected_event.x, corrected_event.y = main_canvas_x, main_canvas_y
        self.create_clone_from_asset(asset_comp, corrected_event)


    def apply_decal_to_underlying_layer(self):
        """
        Finds the top-most draggable image (decal or clone) and stamps it onto all layers underneath.
        """
        # --- REFACTOR: Use the helper function to find any active clone source image ---
        stamp_source_comp = self._find_topmost_stamp_source(clone_type='any')
        
        if not stamp_source_comp:
            # The helper function now shows its own warning.
            # messagebox.showwarning("No Stamp Source", "Could not find a draggable image (decal or cloned asset) at the top of the layer stack to apply.")
            return

        # --- REWRITTEN FOR WORLD COORDINATES ---

        # 1. Get the transformed decal/stamp image and its world dimensions
        # Get the current scale and rotation from the sliders.
        scale_factor = self.decal_scale.get() / 100.0
        rotation_angle = self.decal_rotation.get()

        # Scale the original, full-resolution image.
        original_w, original_h = stamp_source_comp.original_pil_image.size
        new_w = int(original_w * scale_factor)
        new_h = int(original_h * scale_factor)
        resized_image = stamp_source_comp.original_pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Rotate the scaled image to create the final stamp.
        decal_stamp_image = resized_image.rotate(rotation_angle, expand=True, resample=Image.Resampling.BICUBIC)
        stamp_w, stamp_h = decal_stamp_image.size

        # 2. Get the stamp's world bounding box. Its center is the component's center.
        stamp_cx = (stamp_source_comp.world_x1 + stamp_source_comp.world_x2) / 2
        stamp_cy = (stamp_source_comp.world_y1 + stamp_source_comp.world_y2) / 2
        stamp_world_x1 = stamp_cx - stamp_w / 2
        stamp_world_y1 = stamp_cy - stamp_h / 2
        stamp_world_x2 = stamp_world_x1 + stamp_w
        stamp_world_y2 = stamp_world_y1 + stamp_h

        # --- NEW: Prepare for Undo ---
        undo_data = {}
        applied_count = 0

        # 3. Iterate through all components to find targets for stamping.
        for target_comp in self.components.values():
            # Skip if it's the stamp itself, a dock asset, or has no image to stamp onto.
            if target_comp.tag == stamp_source_comp.tag or target_comp.is_dock_asset or not target_comp.pil_image:
                continue

            # 4. Calculate the intersection in WORLD coordinates
            intersect_x1 = max(stamp_world_x1, target_comp.world_x1)
            intersect_y1 = max(stamp_world_y1, target_comp.world_y1)
            intersect_x2 = min(stamp_world_x2, target_comp.world_x2)
            intersect_y2 = min(stamp_world_y2, target_comp.world_y2)

            # If they overlap...
            if intersect_x1 < intersect_x2 and intersect_y1 < intersect_y2:
                # Save state for undo
                if target_comp.tag not in undo_data:
                    undo_data[target_comp.tag] = target_comp.pil_image.copy()

                # 5. --- CRITICAL FIX: Calculate paste position relative to the target's PIL image size ---
                # The target's pil_image may have different dimensions than its world coordinates.
                # We must scale the paste position accordingly.
                target_world_w = target_comp.world_x2 - target_comp.world_x1
                target_world_h = target_comp.world_y2 - target_comp.world_y1
                if target_world_w == 0 or target_world_h == 0: continue

                scale_x = target_comp.pil_image.width / target_world_w
                scale_y = target_comp.pil_image.height / target_world_h

                paste_x = int((intersect_x1 - target_comp.world_x1) * scale_x)
                paste_y = int((intersect_y1 - target_comp.world_y1) * scale_y)

                # 6. Determine which part of the stamp image to use.
                # This is the intersection's top-left corner relative to the stamp's top-left corner.
                crop_x1 = int(intersect_x1 - stamp_world_x1)
                crop_y1 = int(intersect_y1 - stamp_world_y1)
                crop_x2 = int(intersect_x2 - stamp_world_x1)
                crop_y2 = int(intersect_y2 - stamp_world_y1)
                
                # Crop the stamp to get the exact piece that overlaps.
                cropped_stamp = decal_stamp_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))

                # 7. Composite the images.
                # Start with a copy of the target's current image.
                final_image = target_comp.pil_image.copy()
                
                # --- BUG FIX: Use the correct size for the decal layer ---
                decal_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
                # Paste the cropped stamp onto this layer at the correct position.
                # --- FIX: The third argument (mask) must be the stamp itself to respect its transparency. ---
                
                # --- CRITICAL FIX: Resize the cropped stamp to match the target's image scale ---
                final_stamp_w = int(cropped_stamp.width * scale_x)
                final_stamp_h = int(cropped_stamp.height * scale_y)
                if final_stamp_w > 0 and final_stamp_h > 0:
                    cropped_stamp = cropped_stamp.resize((final_stamp_w, final_stamp_h), Image.Resampling.LANCZOS)

                decal_layer.paste(cropped_stamp, (paste_x, paste_y), cropped_stamp)

                # --- FIX: Conditionally respect transparency of the underlying tile ---
                # Regular images should respect the tile's transparency (e.g., for rounded corners),
                # but borders should be stamped on opaquely, ignoring the tile's alpha.
                if not stamp_source_comp.is_border_asset:
                    comp_alpha_mask = final_image.getchannel('A')
                    combined_alpha = ImageChops.multiply(decal_layer.getchannel('A'), comp_alpha_mask)
                    decal_layer.putalpha(combined_alpha)
                    
                # Composite the decal layer onto the final image.
                final_image = Image.alpha_composite(final_image, decal_layer)

                # 8. Apply the newly composited image back to the target component.
                target_comp._set_pil_image(final_image)
                applied_count += 1
                print(f"Stamped decal onto layer '{target_comp.tag}'.")
        
        if applied_count == 0:
            messagebox.showwarning("No Target", "Decal must be positioned over a valid layer to be applied.")
            return

        # --- NEW: Save the collected undo states ---
        if undo_data:
            self._save_undo_state(undo_data)

        # Clean up the temporary decal/clone and redraw everything.
        self._remove_stamp_source_component(stamp_source_comp)
        self.redraw_all_zoomable()

# --- EXECUTION ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageEditorApp(root)
    try:
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Application Error", f"An error occurred: {e}")