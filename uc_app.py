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

        # --- REFACTOR: Event Handling State ---
        self.dragged_item_tag = None
        self.last_drag_x = 0
        self.last_drag_y = 0
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
        self.ui_manager.bind_canvas_events() # Binds paint events

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

    def _bind_component_events(self, comp_tag):
        """Binds press, drag, and release events for a given component tag."""
        self.canvas.tag_bind(comp_tag, '<Button-1>', self.on_component_press)
        self.canvas.tag_bind(comp_tag, '<B1-Motion>', self.on_component_drag)
        self.canvas.tag_bind(comp_tag, '<ButtonRelease-1>', self.on_component_release)

    def _draw_placeholder(self, comp):
        """Draws the initial placeholder for a component and stores canvas IDs."""
        # Create the rectangle
        comp.rect_id = self.canvas.create_rectangle(
            comp.world_x1, comp.world_y1, comp.world_x2, comp.world_y2,
            fill=comp.placeholder_color,
            outline='white',
            width=2,
            tags=(comp.tag, "draggable", "zoom_target")
        )
        # Create the text
        comp.text_id = self.canvas.create_text(
            (comp.world_x1 + comp.world_x2) / 2, (comp.world_y1 + comp.world_y2) / 2,
            text=comp.placeholder_text,
            fill="white", font=("Inter", 16, "bold"), tags=(comp.tag, "draggable", "zoom_target")
        )

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
        comp = DraggableComponent(
            "humanuitile01",
            50, 50, 300, 350,  # W:250, H:300
            base_color, "UI TILE 01"
        )
        self.components['humanuitile01'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 02 (Row 1, Col 2)
        comp = DraggableComponent(
            "humanuitile02",
            350, 50, 600, 350,
            base_color, "UI TILE 02"
        )
        self.components['humanuitile02'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 03 (Row 1, Col 3)
        comp = DraggableComponent(
            "humanuitile03",
            650, 50, 900, 350,
            base_color, "UI TILE 03"
        )
        self.components['humanuitile03'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 04 (Row 1, Col 4)
        comp = DraggableComponent(
            "humanuitile04",
            950, 50, 980, 350,
            base_color, "UI TILE 04"
        )
        self.components['humanuitile04'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 05 (Row 2, Col 1)
        comp = DraggableComponent(
            "humanuitile05",
            50, 400, 300, 700,
            base_color, "UI TILE 05"
        )
        self.components['humanuitile05'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 06 (Row 2, Col 2)
        comp = DraggableComponent(
            "humanuitile06",
            350, 400, 600, 700,
            base_color, "UI TILE 06"
        )
        self.components['humanuitile06'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 07 (Row 2, Col 3) - Inventory Cover (Tag matches filename)
        comp = DraggableComponent(
            "humanuitile-inventorycover",
            650, 400, 770, 700,
            base_color, "INVENTORY COVER"
        )
        self.components['humanuitile-inventorycover'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 08 (Row 2, Col 4) - Time Indicator Frame (Tag matches filename)
        comp = DraggableComponent(
            "humanuitile-timeindicatorframe",
            950, 400, 1085, 475,
            base_color, "TIME FRAME"
        )
        self.components['humanuitile-timeindicatorframe'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

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

    def on_component_press(self, event):
        """Handles press events on any component."""
        # Find the component tag from the canvas item clicked
        item_id = self.canvas.find_closest(event.x, event.y)[0]
        tags = self.canvas.gettags(item_id)
        if not tags: return
        
        comp_tag = tags[0]
        comp = self.components.get(comp_tag)
        if not comp: return

        if comp.is_dock_asset:
            # Dock asset logic is handled by the dock canvas, not here.
            return

        self.dragged_item_tag = comp_tag
        self.last_drag_x = event.x
        self.last_drag_y = event.y
        
        world_x, world_y = self.camera.screen_to_world(event.x, event.y)
        print(f"[DEBUG] Pressed '{comp.tag}' | Screen: ({event.x}, {event.y}) | World: ({int(world_x)}, {int(world_y)})")

        self.canvas.tag_raise(comp.tag)

    def on_component_drag(self, event):
        """Handles drag events for the currently pressed component."""
        if not self.dragged_item_tag: return

        comp = self.components.get(self.dragged_item_tag)
        if not comp or not comp.is_draggable or (self.is_group_dragging and not comp.is_decal) or comp.is_dock_asset:
            return

        dx_world = (event.x - self.last_drag_x) / self.camera.zoom_scale
        dy_world = (event.y - self.last_drag_y) / self.camera.zoom_scale

        if not comp.is_decal:
            new_world_x1 = comp.world_x1 + dx_world
            new_world_y1 = comp.world_y1 + dy_world

            tile_w_world = comp.world_x2 - comp.world_x1
            tile_h_world = comp.world_y2 - comp.world_y1

            if new_world_x1 < self.COMP_AREA_X1: new_world_x1 = self.COMP_AREA_X1
            if new_world_x1 + tile_w_world > self.COMP_AREA_X2: new_world_x1 = self.COMP_AREA_X2 - tile_w_world
            if new_world_y1 < self.COMP_AREA_Y1: new_world_y1 = self.COMP_AREA_Y1
            if new_world_y1 + tile_h_world > self.COMP_AREA_Y2: new_world_y1 = self.COMP_AREA_Y2 - tile_h_world

            comp.world_x1, comp.world_y1 = new_world_x1, new_world_y1
            comp.world_x2, comp.world_y2 = new_world_x1 + tile_w_world, new_world_y1 + tile_h_world
        else: # It's a decal, allow free movement
            comp.world_x1 += dx_world; comp.world_y1 += dy_world
            comp.world_x2 += dx_world; comp.world_y2 += dy_world
        
        self.last_drag_x = event.x
        self.last_drag_y = event.y
        
        self.redraw_all_zoomable()

    def on_component_release(self, event):
        """Handles release events, finalizing the drag."""
        if self.dragged_item_tag:
            comp = self.components.get(self.dragged_item_tag)
            if comp:
                print(f"[DEBUG] Released '{comp.tag}' | Screen: ({event.x}, {event.y}) | New World TL: ({int(comp.world_x1)}, {int(comp.world_y1)})")
        self.dragged_item_tag = None
        self._keep_docks_on_top()

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
                    # REFACTOR: Logic moved from component to app/manager
                    pil_image = Image.open(full_path).convert("RGBA")
                    if not component.original_pil_image:
                        component.original_pil_image = pil_image.copy()
                    component.set_image(pil_image)
                    print(f"Image loaded for {tag}: {os.path.basename(full_path)}")
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

    def select_component(self, tag):
        """Selects a component and highlights it."""
        self.set_selected_component(tag)
        
        # Reset all borders first
        for comp in self.components.values():
            if comp.rect_id and comp.pil_image is None: # It's a placeholder
                 self.canvas.itemconfig(comp.rect_id, outline='white', width=2)
        
        # Highlight the selected one
        selected_comp = self.components.get(tag)
        if selected_comp and selected_comp.pil_image is None:
            self.canvas.itemconfig(selected_comp.rect_id, outline='yellow', width=3)
        
        print(f"[ACTION] Component '{tag}' selected via sidebar.")

    def set_selected_component(self, tag):
        """Updates the tracking variable for the currently selected component."""
        self.selected_component_tag = tag
        comp = self.components.get(tag)
        if comp: print(f"[DEBUG] Selected component: '{tag}' | World Coords: ({int(comp.world_x1)}, {int(comp.world_y1)})")
        else: print(f"[DEBUG] Selected component: {tag}")
    
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
                    self.components[tag].set_image(image)
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
            # REFACTOR: Check if the component has a canvas ID
            if comp.rect_id and "zoom_target" in self.canvas.gettags(comp.rect_id):
                # For components with an image, we need to resize the image itself
                # and then place it at the new screen coordinates.
                if comp.pil_image:
                    # --- FIX: Handle transition from placeholder to image ---
                    # If we have a PIL image but no TK image, it means we just loaded one. (tk_image is a canvas-specific attribute)
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
                        # Also delete the old text placeholder
                        if comp.text_id:
                            self.canvas.delete(comp.text_id); comp.text_id = None
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

                elif comp.text_id: # It's a placeholder
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
            
            # Select the component (which also handles highlighting)
            self.select_component(name)

            # Update resize entries when a component is selected
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
            comp.set_image(comp.pil_image) # This will trigger a redraw
        else:
            self.redraw_all_zoomable() # Just redraw the placeholder with new world coords
        
        # Redraw to apply the new size within the camera view
        self.redraw_all_zoomable()
        print(f"Resized '{comp.tag}' to {new_w}x{new_h}.")

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
            comp.set_image(comp.original_pil_image)
            print(f"Layer '{comp.tag}' has been reset to its original image.")
        else:
            messagebox.showinfo("No Image", f"Layer '{comp.tag}' does not have an original image to reset to.")

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
                target_comp.set_image(final_image)
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
    import traceback
    root = tk.Tk()
    app = ImageEditorApp(root)
    try:
        root.mainloop()
    except Exception as e:
        # --- FIX: Print the full error traceback to the console for debugging ---
        print("--- APPLICATION ERROR ---")
        traceback.print_exc()
        print("-------------------------")
        messagebox.showerror("Application Error", f"An error occurred: {e}")