import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import subprocess
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageEnhance, ImageChops
import os
import json

import numpy as np
from uc_border_manager2 import NUMPY_AVAILABLE # Import NUMPY_AVAILABLE
try:
    from wand.image import Image as WandImage
    import io
    WAND_AVAILABLE = True
except ImportError:
    WAND_AVAILABLE = False # type: ignore

from uc_component import DraggableComponent
from uc_camera import Camera
from uc_ui import UIManager
from uc_border_manager import BorderManager
from uc_image_manager import ImageManager
from uc_export_manager import ExportManager
from settings import SettingsManager # type: ignore
from utils import get_base_path # Import the centralized function

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

        # --- NEW: Initialize Settings Manager ---
        self.settings_manager = SettingsManager()
        master.protocol("WM_DELETE_WINDOW", self.save_on_exit)

        # Constants
        self.CANVAS_WIDTH = CANVAS_WIDTH
        self.CANVAS_HEIGHT = CANVAS_HEIGHT
        self.SIDEBAR_WIDTH = SIDEBAR_WIDTH

        # --- REFACTOR: Event Handling State ---
        self.dragged_item_tag = None
        self.last_drag_x = 0
        self.last_drag_y = 0
        self.selection_highlight_id = None # NEW: To track the selection highlight rectangle
        self.selected_component_tag = None
        self.tile_eraser_mode_active = False # NEW: For the tile eraser tool
        self.pre_move_state = {} # NEW: To store component positions before a move
        self.smart_border_mode_active = False # NEW: For the smart border tool
        
        self.resize_selector_buttons = {} # NEW: To hold references to the resize tab buttons
        # --- NEW: Painting Feature State ---
        self.resize_width = tk.StringVar()
        self.resize_height = tk.StringVar()
        self.maintain_aspect = tk.BooleanVar(value=True)
        self.move_amount = tk.IntVar(value=1) # NEW: For moving tiles by pixels
        self.mouse_coords_var = tk.StringVar(value="World: (0, 0)") # NEW: For coordinate display
        self.resize_width.trace_add("write", self.on_resize_entry_change)
        self.resize_height.trace_add("write", self.on_resize_entry_change)

        # --- NEW: Undo Stack ---
        self.export_all_tiles = tk.BooleanVar(value=True) # FIX: For the export checkbox

        self.undo_stack = []
        self.MAX_UNDO_STATES = 20 # Limit memory usage
        master.bind("<Control-z>", self.undo_last_action)

        # --- NEW: Dedicated layer for preset borders to improve performance ---
        self.border_layer_image = None
        self.border_layer_tk = None

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
        self.ui_creator_contents_path = os.path.join(self.base_path, "contents", "ui creator")
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
        self.camera = Camera(self, canvas)
        self.image_manager = ImageManager(self)
        self.export_manager = ExportManager(self)
        # --- Initialize Components BEFORE UI that might use them ---
        # This ensures self.components exists before any callbacks can be triggered.
        self._initialize_components()
        
        # Bind camera pan events directly to the canvas
        self.canvas.bind("<Control-Button-1>", self.camera.on_pan_press)
        self.canvas.bind("<Control-B1-Motion>", self.camera.on_pan_drag)

        self.canvas.bind("<Button-1>", self.on_canvas_press) # NEW: Generic canvas press handler

        self.bind_generic_drag_handler()
        self.ui_manager.create_ui()
        self.canvas.bind("<Motion>", self._update_mouse_coords) # NEW: Bind mouse motion to update coords

        # --- NEW: Bind focus events to handle cursor visibility ---
        # This ensures the custom cursor hides when the app loses focus.
        self.master.bind("<FocusIn>", self.on_app_focus_in)
        self.master.bind("<FocusOut>", self.on_app_focus_out)

    def bind_generic_drag_handler(self):
        def on_drag(event): # This is the generic B1-Motion handler
            # --- DEBUG: Announce which tool is handling the drag ---
            if self.border_manager.smart_manager.is_drawing:
                print("[DEBUG] Drag event routed to Smart Border tool.")
                self.border_manager.smart_manager.on_mouse_drag(event)
            else:
                # This case is for standard component dragging, which is handled by on_component_drag
                pass
        self.canvas.bind("<B1-Motion>", on_drag)
        print("[DEBUG] Generic drag handler (<B1-Motion>) has been bound.")

        # --- PREVIEW LAYOUT COORDINATES ---
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
            
        # --- 6. Reload saved dock assets ---
        self._reload_dock_assets()

        # --- 7. Schedule initial draw and layout ---
        # We schedule this to run after the main loop starts, ensuring the window
        # is fully initialized and visible before we try to draw anything. This
        # prevents a race condition where culling hides everything on startup.
        self.master.after(100, self.initial_draw)

    def initial_draw(self):
        """Performs the first layout application and redraw after the UI is ready."""
        self.apply_preview_layout()

    def save_settings(self):
        """Saves the current application settings to the settings file."""
        # --- DEFINITIVE FIX: Perform a safe read-modify-write to prevent data loss ---
        # 1. Load the most recent settings from the file.
        self.settings_manager.load()
        # 2. Get the current dock assets from the UI Creator.
        dock_assets_to_save = [{'path': asset.image_path, 'is_border': asset.is_border_asset} for asset in self.image_manager.dock_assets if asset.image_path]
        # 3. Update only the 'dock_assets' key in the loaded settings.
        self.settings_manager.settings['dock_assets'] = dock_assets_to_save
        # 4. Write the entire, updated settings object back to the file.
        with open(self.settings_manager.settings_path, 'w') as f:
            json.dump(self.settings_manager.settings, f, indent=4)
        print("[INFO] UI Creator settings saved.")

    def save_on_exit(self):
        """Saves settings and closes the application."""
        self.save_settings()
        # --- NEW: Explicitly destroy the cursor window on exit ---
        self.border_manager.smart_manager.cursor_window.destroy()
        self.master.destroy()

    def _reload_dock_assets(self):
        """Loads assets into the dock from paths saved in settings."""
        saved_assets = self.settings_manager.get("dock_assets", [])
        for asset_info in saved_assets:
            self.image_manager.load_asset_from_path(asset_info.get('path'), asset_info.get('is_border', False))

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
        self.components = {} # type: ignore
        base_color = "#1e40af"  # A more modern, vibrant blue

        # Define tile dimensions for the 4x2 grid (increased size)
        tile_width = 250
        tile_height = 300
        
        # Define starting coordinates for the 4x2 grid with 50px padding/spacing
        # C1_X=50, C2_X=350, C3_X=650, C4_X=950
        # R1_Y=50, R2_Y=400 (50 + 300 + 50)

        # TILE 01 (Row 1, Col 1)
        comp = DraggableComponent(
            self,
            "humanuitile01", 
            50, 50, 300, 350,  # W:250, H:300
            base_color, "UI TILE 01"
        )
        self.components['humanuitile01'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 02 (Row 1, Col 2)
        comp = DraggableComponent(
            self,
            "humanuitile02", 
            350, 50, 600, 350,
            base_color, "UI TILE 02"
        )
        self.components['humanuitile02'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 03 (Row 1, Col 3)
        comp = DraggableComponent(
            self,
            "humanuitile03", 
            650, 50, 900, 350,
            base_color, "UI TILE 03"
        )
        self.components['humanuitile03'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 04 (Row 1, Col 4)
        comp = DraggableComponent(
            self,
            "humanuitile04", 
            950, 50, 980, 350,
            base_color, "UI TILE 04"
        )
        self.components['humanuitile04'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 05 (Row 2, Col 1)
        comp = DraggableComponent(
            self,
            "humanuitile05", 
            50, 400, 300, 700,
            base_color, "UI TILE 05"
        )
        self.components['humanuitile05'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 06 (Row 2, Col 2)
        comp = DraggableComponent(
            self,
            "humanuitile06", 
            350, 400, 600, 700,
            base_color, "UI TILE 06"
        )
        self.components['humanuitile06'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 07 (Row 2, Col 3) - Inventory Cover (Tag matches filename)
        comp = DraggableComponent(
            self,
            "humanuitile-inventorycover", 
            650, 400, 770, 700,
            base_color, "INVENTORY COVER"
        )
        self.components['humanuitile-inventorycover'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag)

        # TILE 08 (Row 2, Col 4) - Time Indicator Frame (Tag matches filename)
        comp = DraggableComponent(
            self,
            "humanuitile-timeindicatorframe", 
            950, 400, 1085, 475,
            base_color, "TIME FRAME"
        )
        self.components['humanuitile-timeindicatorframe'] = comp
        self._draw_placeholder(comp)
        self._bind_component_events(comp.tag) # type: ignore

    def on_canvas_press(self, event):
        """
        Handles a click directly on the canvas, which is crucial for initiating
        actions like painting that don't start on a specific component.
        """
        # If any paint tool is active, route the event to the paint manager.
        # This ensures that the first dot of a stroke is drawn even on an empty canvas area.
        pass

    def on_component_press(self, event):
        """Handles press events on any component."""

        # Find the component tag from the canvas item clicked
        item_id = self.canvas.find_closest(event.x, event.y)[0]
        tags = self.canvas.gettags(item_id)
        if not tags: return
        
        comp_tag = tags[0]
        comp = self.components.get(comp_tag)
        if not comp: return

        # --- NEW: Handle Tile Eraser ---
        if self.tile_eraser_mode_active:
            # We don't want to erase the main tiles, only clones, decals, or borders.
            if not comp.is_decal and not comp.tag.startswith("preset_border_"):
                messagebox.showwarning("Action Not Allowed", "The Tile Eraser can only remove temporary images and preset borders, not the main layout tiles.")
                return
            self.delete_component(comp.tag)
            return # Stop further processing
        
        # --- NEW: Handle Smart Border Tool ---
        if self.smart_border_mode_active:
            # --- FIX: Directly call the drawing logic from the generic press handler ---
            # This ensures the is_drawing flag is set, allowing the generic drag
            # handler (<B1-Motion>) to correctly delegate to the border manager.
            self.border_manager.start_drawing_stroke(event)
            return # Stop further processing

        if comp.is_dock_asset:
            # This is a click on a dock asset, which creates a clone.
            # It's not a move operation, so we don't save a move state.
            # Dock asset logic is handled by the dock canvas, not here.
            return

        print(f"[DEBUG] Initiating drag for component '{comp_tag}'.")
        self.dragged_item_tag = comp_tag
        
        # --- DEFINITIVE FIX: Initialize last_drag coordinates on press ---
        # This prevents the component from jumping on the first drag motion by
        # ensuring the delta calculation in on_component_drag starts from the correct point.
        self.last_drag_x, self.last_drag_y = event.x, event.y
        
        world_x, world_y = self.camera.screen_to_world(event.x, event.y)
        print(f"[DEBUG] Pressed '{comp.tag}' | Screen: ({event.x}, {event.y}) | World: ({int(world_x)}, {int(world_y)})")

        # --- NEW: Save pre-move state for single tile drag ---
        if not comp.is_decal:
            self._save_pre_move_state([comp.tag])

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

        # --- REFACTOR: Call the correct update function for the component type ---
        # The transform function now handles its own redraw, ensuring no race conditions.
        if comp.is_decal:
            self.image_manager._update_active_decal_transform()
        elif not comp.is_dock_asset:
            # --- DEFINITIVE FIX: Move child components (borders) along with the parent tile ---
            for child_comp in self.components.values():
                if child_comp.parent_tag == self.dragged_item_tag:
                    child_comp.world_x1 += dx_world; child_comp.world_y1 += dy_world
                    child_comp.world_x2 += dx_world; child_comp.world_y2 += dy_world
            self.redraw_all_zoomable()
        else:
            self.redraw_all_zoomable()

    def on_component_release(self, event):
        """Handles release events, finalizing the drag."""
        if self.dragged_item_tag:
            comp = self.components.get(self.dragged_item_tag)
            if comp:
                print(f"[DEBUG] Released '{comp.tag}' | Screen: ({event.x}, {event.y}) | New World TL: ({int(comp.world_x1)}, {int(comp.world_y1)})")
        
        # --- NEW: Handle Smart Border Tool ---
        if self.smart_border_mode_active:
            self.border_manager.on_mouse_up(event)

        self.dragged_item_tag = None

        # --- NEW: Finalize move operation for undo ---
        if self.pre_move_state:
            self._save_undo_state({'type': 'move', 'positions': self.pre_move_state})
            self.pre_move_state = {} # Clear the temporary state

        self._keep_docks_on_top()

    def move_all_main_tiles(self, dx_world, dy_world):
        """Moves all primary component tiles by a delta in world coordinates."""
        for comp in self.components.values():
            if not comp.is_dock_asset and not comp.is_decal:
                comp.world_x1 += dx_world; comp.world_y1 += dy_world
                comp.world_x2 += dx_world; comp.world_y2 += dy_world

                # --- DEFINITIVE FIX: Also move any borders attached to this tile ---
                for child_comp in self.components.values():
                    if child_comp.parent_tag == comp.tag:
                        child_comp.world_x1 += dx_world; child_comp.world_y1 += dy_world
                        child_comp.world_x2 += dx_world; child_comp.world_y2 += dy_world

    def _save_pre_move_state(self, tags_to_save=None):
        """Saves the world coordinates of specified components before a move operation."""
        self.pre_move_state = {}
        
        components_to_save = []
        if tags_to_save:
            components_to_save = [self.components.get(tag) for tag in tags_to_save if tag in self.components]
        else: # Save all non-decal, non-dock components
            components_to_save = [c for c in self.components.values() if not c.is_decal and not c.is_dock_asset]

        for comp in components_to_save:
            if comp:
                self.pre_move_state[comp.tag] = (comp.world_x1, comp.world_y1, comp.world_x2, comp.world_y2)


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

    def toggle_tile_eraser_mode(self):
        """Toggles the tile eraser mode on or off."""
        self.tile_eraser_mode_active = not self.tile_eraser_mode_active
        if self.tile_eraser_mode_active:
            self.ui_manager.tile_eraser_btn.config(text="Tile Eraser (Active)", bg='#ef4444', relief='sunken')
            self.canvas.config(cursor="X_cursor")
            print("Tile Eraser mode ENABLED.")
        else:
            self.ui_manager.tile_eraser_btn.config(text="Tile Eraser", bg='#991b1b', relief='flat')
            self.canvas.config(cursor="")
            print("Tile Eraser mode DISABLED.")

    def delete_component(self, tag_to_delete):
        """Deletes a component from the canvas and the application state."""
        comp_to_delete = self.components.get(tag_to_delete)
        if not comp_to_delete:
            return

        print(f"Deleting component '{tag_to_delete}'...")

        # --- NEW: Save state for Undo ---
        # We save all necessary data to fully reconstruct the component.
        undo_data = {
            'type': 'delete_component',
            'component_data': {
                'tag': comp_to_delete.tag, 'x1': comp_to_delete.world_x1, 'y1': comp_to_delete.world_y1,
                'x2': comp_to_delete.world_x2, 'y2': comp_to_delete.world_y2, 'color': comp_to_delete.placeholder_color,
                'text': comp_to_delete.placeholder_text, 'is_decal': comp_to_delete.is_decal,
                'is_border_asset': comp_to_delete.is_border_asset, 'parent_tag': comp_to_delete.parent_tag,
                'pil_image': comp_to_delete.pil_image.copy() if comp_to_delete.pil_image else None,
                'original_pil_image': comp_to_delete.original_pil_image.copy() if comp_to_delete.original_pil_image else None
            }
        }
        self._save_undo_state(undo_data)

        self.image_manager._remove_stamp_source_component(comp_to_delete)
        print(f"Component '{tag_to_delete}' deleted.")

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
        # --- DEBUG: Log what is being saved ---
        if isinstance(undo_data, dict) and 'type' in undo_data:
            print(f"[DEBUG] Saving undo state for action: '{undo_data['type']}'.")
        
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

        if isinstance(last_state, dict): # It's a component image state
            action_type = last_state.get('type')

            print(f"[DEBUG] Undoing action of type: '{action_type}'.")
            if action_type == 'move':
                for move_tag, pos in last_state.get('positions', {}).items():
                    if move_tag in self.components:
                        comp = self.components[move_tag]
                        comp.world_x1, comp.world_y1, comp.world_x2, comp.world_y2 = pos
                self.redraw_all_zoomable()
            elif action_type == 'add_component':
                tag_to_remove = last_state.get('tag')
                if tag_to_remove and tag_to_remove in self.components:
                    comp_to_remove = self.components[tag_to_remove]
                    self.canvas.delete(comp_to_remove.tag)
                    if comp_to_remove.rect_id: self.canvas.delete(comp_to_remove.rect_id)
                    del self.components[tag_to_remove]
                    self.redraw_all_zoomable()
                    print(f"Undid component addition for '{tag_to_remove}'.")
            elif action_type == 'delete_component':
                data = last_state.get('component_data')
                if data:
                    # Re-create the component from the saved data
                    new_comp = DraggableComponent(
                        self, data['tag'], data['x1'], data['y1'], data['x2'], data['y2'],
                        data['color'], data['text']
                    )
                    new_comp.is_decal = data['is_decal']
                    new_comp.is_border_asset = data['is_border_asset']
                    new_comp.parent_tag = data['parent_tag']
                    new_comp.original_pil_image = data['original_pil_image']
                    
                    self.components[data['tag']] = new_comp
                    self._bind_component_events(data['tag'])
                    
                    # Set the image, which will trigger a redraw
                    if data['pil_image']:
                        new_comp.set_image(data['pil_image'])
                    print(f"Undid component deletion for '{data['tag']}'.")
            else: # It's a component image state (original implementation)
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
        self.COMP_AREA_X2 = new_width # type: ignore
        self.COMP_AREA_Y2 = new_height # type: ignore

    # --- NEW: Camera Transformation Functions ---
    def redraw_all_zoomable(self, use_fast_preview=False):
        """
        The main rendering loop. Coordinates drawing all components and overlays.
        This function is refactored to delegate tasks to helper methods.
        """
        zoom_scale = self.camera.zoom_scale
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        view_wx1, view_wy1 = self.camera.screen_to_world(0, 0)
        view_wx2, view_wy2 = self.camera.screen_to_world(canvas_w, canvas_h)

        # 1. Draw the main components (tiles, decals), excluding preset borders which are handled separately.
        self._draw_components(use_fast_preview, view_wx1, view_wy1, view_wx2, view_wy2, canvas_w, canvas_h)

        # 2. Draw all preset borders onto a single dedicated layer for performance.
        self._draw_preset_borders(view_wx1, view_wy1, view_wx2, view_wy2, canvas_w, canvas_h)

        # 3. Draw other overlays (smart border highlights, tool previews) on top.
        self._draw_overlays(zoom_scale, view_wx1, view_wy1, view_wx2, view_wy2, canvas_w, canvas_h)

        # 4. Ensure UI elements like docks are always on top
        self._keep_docks_on_top()
        
        # 4. Cache the zoom level to optimize future redraws
        self.camera.last_redraw_zoom = zoom_scale

    def _draw_components(self, use_fast_preview, view_wx1, view_wy1, view_wx2, view_wy2, canvas_w, canvas_h):
        """
        Helper for `redraw_all_zoomable`. Handles drawing all `DraggableComponent`
        objects, including culling, resizing, and image caching.
        """
        for comp in self.components.values():
            # --- NEW: Skip preset borders, as they are now drawn on a separate layer ---
            if comp.tag.startswith("preset_border_"):
                continue

            sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
            sx2, sy2 = self.camera.world_to_screen(comp.world_x2, comp.world_y2)

            if sx2 < 0 or sx1 > canvas_w or sy2 < 0 or sy1 > canvas_h:
                if comp.rect_id: self.canvas.itemconfigure(comp.rect_id, state='hidden')
                continue
            else:
                if comp.rect_id: self.canvas.itemconfigure(comp.rect_id, state='normal')

            if not comp.rect_id:
                if comp.pil_image:
                    sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
                    comp.rect_id = self.canvas.create_image(
                        sx1, sy1,
                        anchor=tk.NW,
                        tags=(comp.tag, "draggable", "zoom_target")
                    )
                    print(f"[DEBUG] Created initial canvas image for new component '{comp.tag}'.")

            if comp.rect_id:
                if comp.pil_image:
                    if comp.tk_image is None:
                        self.canvas.delete(comp.rect_id)
                        sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
                        comp.rect_id = self.canvas.create_image(
                            sx1, sy1,
                            anchor=tk.NW,
                            tags=(comp.tag, "draggable", "zoom_target")
                        )
                        if comp.text_id:
                            self.canvas.delete(comp.text_id); comp.text_id = None
                        comp._cached_screen_w, comp._cached_screen_h = -1, -1

                    screen_w, screen_h = sx2 - sx1, sy2 - sy1

                    if screen_w > 0 and screen_h > 0 and (int(screen_w) != comp._cached_screen_w or int(screen_h) != comp._cached_screen_h or comp.tk_image is None):
                        comp._cached_screen_w = int(screen_w); comp._cached_screen_h = int(screen_h)
                        if comp._cached_screen_w <= 0 or comp._cached_screen_h <= 0: continue
                        
                        source_img = comp.display_pil_image if comp.display_pil_image is not None else comp.pil_image
                        if not source_img: continue

                        resample_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.LANCZOS
                        resized_img = source_img.resize((comp._cached_screen_w, comp._cached_screen_h), resample_quality)
                        comp.tk_image = ImageTk.PhotoImage(resized_img)
                        self.canvas.itemconfigure(comp.rect_id, image=comp.tk_image)

                    self.canvas.coords(comp.rect_id, sx1, sy1)

                elif comp.text_id:
                    self.canvas.coords(comp.rect_id, sx1, sy1, sx2, sy2)
                    self.canvas.coords(comp.text_id, (sx1 + sx2) / 2, (sy1 + sy2) / 2)

    def _draw_preset_borders(self, view_wx1, view_wy1, view_wx2, view_wy2, canvas_w, canvas_h):
        """
        Helper for `redraw_all_zoomable`. Draws all preset borders onto a single
        transparent layer for significantly better performance.
        """
        # 1. Initialize or clear the border layer image.
        if self.border_layer_image is None or self.border_layer_image.size != (canvas_w, canvas_h):
            self.border_layer_image = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        else:
            # Fast clear of the existing image
            self.border_layer_image.paste((0, 0, 0, 0), [0, 0, canvas_w, canvas_h])

        # 2. Find all visible preset border components.
        visible_borders = [
            comp for comp in self.components.values()
            if comp.tag.startswith("preset_border_") and
               comp.world_x1 < view_wx2 and comp.world_x2 > view_wx1 and
               comp.world_y1 < view_wy2 and comp.world_y2 > view_wy1
        ]

        if not visible_borders:
            # If no borders are visible, ensure any old image is cleared from the canvas.
            if self.border_layer_tk:
                self.border_layer_tk.paste(self.border_layer_image)
            return

        # 3. Draw each visible border onto the single PIL image layer.
        for comp in visible_borders:
            if not comp.pil_image:
                continue

            sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
            sx2, sy2 = self.camera.world_to_screen(comp.world_x2, comp.world_y2)
            screen_w, screen_h = sx2 - sx1, sy2 - sy1

            if screen_w > 0 and screen_h > 0:
                resized_border = comp.pil_image.resize((screen_w, screen_h), Image.Resampling.LANCZOS)
                self.border_layer_image.paste(resized_border, (sx1, sy1), resized_border)

        # 4. Update the single Tkinter PhotoImage on the canvas.
        if self.border_layer_tk is None:
            self.border_layer_tk = ImageTk.PhotoImage(self.border_layer_image)
            self.canvas.create_image(0, 0, image=self.border_layer_tk, anchor=tk.NW, tags="preset_border_layer")
        else:
            self.border_layer_tk.paste(self.border_layer_image)

    def _draw_overlays(self, zoom_scale, view_wx1, view_wy1, view_wx2, view_wy2, canvas_w, canvas_h):
        """
        Helper for `redraw_all_zoomable`. Handles drawing all non-component visual
        aids like selection highlights and tool previews.
        """
        self._update_selection_highlight()

        # --- OPTIMIZATION: Redraw smart border highlights using a cached world-space image ---
        if self.smart_border_mode_active and self.border_manager.smart_manager.highlight_layer_id:
            bm = self.border_manager.smart_manager
            zoom_changed = bm.last_known_zoom != zoom_scale

            # 1. Re-render the world-space cache if points were added/removed or zoom changed.
            if bm.highlights_are_dirty or zoom_changed:
                if bm.raw_border_points:
                    # Find the bounding box of all points in world coordinates
                    min_x = min(p[0] for p in bm.raw_border_points)
                    min_y = min(p[1] for p in bm.raw_border_points)
                    max_x = max(p[0] for p in bm.raw_border_points)
                    max_y = max(p[1] for p in bm.raw_border_points)
                    bm.highlight_world_bounds = (min_x, min_y, max_x, max_y)

                    # Create the world image, scaled by the current zoom
                    world_img_w = int((max_x - min_x) * zoom_scale)
                    world_img_h = int((max_y - min_y) * zoom_scale)

                    if world_img_w > 0 and world_img_h > 0:
                        bm.highlight_world_image = Image.new("RGBA", (world_img_w, world_img_h), (0,0,0,0))
                        draw = ImageDraw.Draw(bm.highlight_world_image)
                        # Translate each point from world space to local image space and draw it
                        points_to_draw = [
                            (int((p[0] - min_x) * zoom_scale), int((p[1] - min_y) * zoom_scale))
                            for p in bm.raw_border_points
                        ]
                        draw.point(points_to_draw, fill=bm.highlight_color)
                else:
                    bm.highlight_world_image = None
                    bm.highlight_world_bounds = None

                bm.highlights_are_dirty = False
                bm.last_known_zoom = zoom_scale

            # 2. Draw the (now cached) world image onto the canvas.
            if bm.highlight_world_image and bm.highlight_world_bounds:
                # Find the top-left screen coordinate of the cached world image
                sx, sy = self.camera.world_to_screen(bm.highlight_world_bounds[0], bm.highlight_world_bounds[1])

                # Create or update the PhotoImage and canvas item
                if bm.highlight_layer_tk is None:
                    bm.highlight_layer_tk = ImageTk.PhotoImage(bm.highlight_world_image)
                    self.canvas.itemconfigure(bm.highlight_layer_id, image=bm.highlight_layer_tk, state='normal')
                else:
                    # The 'paste' method is much faster than creating a new PhotoImage object
                    bm.highlight_layer_tk.paste(bm.highlight_world_image)

                self.canvas.coords(bm.highlight_layer_id, sx, sy)
            else:
                # If there are no points, hide the canvas item
                self.canvas.itemconfigure(bm.highlight_layer_id, state='hidden')

            # Ensure the layer is positioned correctly
            self.canvas.coords(bm.highlight_layer_id, 0, 0)
            self.canvas.tag_raise(bm.highlight_layer_id)

    def on_tab_changed(self, event):
        """Handles the event when the user clicks a different main tab."""
        selected_tab_text = self.ui_manager.notebook.tab(self.ui_manager.notebook.select(), "text")
        print(f"\n[DEBUG] Tab changed to: '{selected_tab_text}'. Deactivating context-specific tools.")

        # --- FIX: Deactivate all context-specific tools when changing tabs ---
        # This prevents tools like Paint or Smart Border from staying active
        # when the user navigates to a different part of the UI.

        # Deactivate Smart Border tool
        if self.smart_border_mode_active:
            print("[DEBUG] Deactivating Smart Border tool due to tab change.")
            self.border_manager.toggle_smart_border_mode()

        # --- FIX: Deactivate the Tile Eraser tool if it's active ---
        if self.tile_eraser_mode_active:
            self.toggle_tile_eraser_mode()

        # --- NEW: Clear any active border previews when switching context ---
        # Also, if the user is switching *to* the border tab, show the preview.
        if not self.is_border_tab_active():
            self.border_manager.clear_preset_preview()

        # --- NEW: Update the selection highlight when changing tabs ---
        # This will show/hide the highlight when entering/leaving the Tile Control tab.
        self._update_selection_highlight()

    def handle_tab_click(self, name):
        """Handles the logic when a sidebar button is clicked."""
        print("-" * 30)

        # This function is for the "Tiles" tab buttons, not the main notebook tabs.
        # The border preview logic is handled by on_tab_changed.

        # --- MODIFICATION START: Implement isolation mode ---
        if name == "Show All":
            self.set_selected_component(None)
            self.apply_preview_layout()
        
        elif name in self.components:
            # Hide all other components to isolate the selected one
            for tag, comp in self.components.items():
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

    def handle_resize_selector_click(self, name):
        """Handles clicks on the new tile selector buttons in the resize tab."""
        if name in self.components:
            # Set the selected component
            self.set_selected_component(name)
            # Update the resize entry boxes with the new component's dimensions
            self.update_resize_entries()
            # Update the button visuals to show the current selection
            self._update_resize_selector_visuals()
            # --- NEW: Update the visual highlight on the canvas ---
            self._update_selection_highlight()

    def _update_resize_selector_visuals(self):
        """Updates the background color of the resize selector buttons."""
        for name, button in self.resize_selector_buttons.items():
            bg_color = '#3b82f6' if name == self.selected_component_tag else '#6b7280'
            button.config(bg=bg_color)

    def _update_selection_highlight(self):
        """Draws or removes a highlight rectangle over the selected component."""
        # First, remove any existing highlight
        if self.selection_highlight_id:
            self.canvas.delete(self.selection_highlight_id)
            self.selection_highlight_id = None

        # Only draw a new highlight if a component is selected AND the Tile Control tab is active
        if self.selected_component_tag and self.is_tile_control_tab_active():
            comp = self.components.get(self.selected_component_tag)
            if comp:
                # Get the component's current screen coordinates
                sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
                sx2, sy2 = self.camera.world_to_screen(comp.world_x2, comp.world_y2)

                # Draw a new semi-transparent rectangle
                self.selection_highlight_id = self.canvas.create_rectangle(
                    sx1, sy1, sx2, sy2,
                    fill="",             # No fill
                    outline="#22c55e",   # A nice green color
                    width=1,             # A thinner, solid outline
                    tags=("selection_highlight",)
                )

    def is_border_tab_active(self, event=None):
        """Checks if the 'Border' tab is the currently selected tab in the sidebar."""
        try:
            notebook = self.ui_manager.notebook # Get the notebook widget
            selected_tab_index = notebook.index(notebook.select())
            selected_tab_text = notebook.tab(selected_tab_index, "text")
            return selected_tab_text == 'Border'
        except Exception:
            return False

    def is_tile_control_tab_active(self, event=None):
        """Checks if the 'Tile Control' tab is the currently selected tab."""
        try:
            notebook = self.ui_manager.notebook
            selected_tab_index = notebook.index(notebook.select())
            selected_tab_text = notebook.tab(selected_tab_index, "text")
            return selected_tab_text == 'Tile Control'
        except Exception:
            return False

    def update_resize_entries(self):
        """Updates the width and height entry boxes with the selected component's dimensions."""
        if not self.selected_component_tag:
            self.resize_width.set("")
            self.resize_height.set("")
            return

        # --- NEW: Update the resize selector visuals when the selection changes ---
        self._update_resize_selector_visuals()

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

        # --- NEW: Save pre-resize state for Undo ---
        undo_data = {
            'type': 'move', # Re-use the 'move' undo type as it restores all 4 world coordinates
            'positions': {comp.tag: (comp.world_x1, comp.world_y1, comp.world_x2, comp.world_y2)}
        }
        self._save_undo_state(undo_data)
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

    def move_selected_component(self, direction: str):
        """Moves the selected component by the amount specified in the UI."""
        if not self.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a tile to move.")
            return

        comp = self.components.get(self.selected_component_tag)
        if not comp: return

        try:
            amount = self.move_amount.get()
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid Input", "Please enter a valid number for the move amount.")
            return

        # Save state for undo
        undo_data = {
            'type': 'move',
            'positions': {comp.tag: (comp.world_x1, comp.world_y1, comp.world_x2, comp.world_y2)}
        }
        self._save_undo_state(undo_data)

        dx, dy = 0, 0
        if direction == 'up': dy = -amount
        elif direction == 'down': dy = amount
        elif direction == 'left': dx = -amount
        elif direction == 'right': dx = amount

        comp.world_x1 += dx
        comp.world_y1 += dy
        comp.world_x2 += dx
        comp.world_y2 += dy

        self.redraw_all_zoomable()
        print(f"Moved '{comp.tag}' {direction} by {amount} pixels.")

    def apply_border_to_selection(self):
        """Applies a loaded border image to the currently selected component."""
        self.border_manager.apply_border_to_selection()

    def remove_border_from_selection(self):
        """Removes the border from the currently selected component."""
        self.border_manager.remove_border_from_selection()

    def _keep_docks_on_top(self):
        """Raises the dock canvases to ensure they are always visible."""
        if self.ui_manager.image_dock_canvas:
            self.ui_manager.image_dock_canvas.master.master.lift()
        if self.ui_manager.border_dock_canvas:
            self.ui_manager.border_dock_canvas.master.master.lift()

    def apply_preview_layout(self):
        """Makes all components visible and moves them to the 'Show All' layout positions."""
        print("Action: Applying 'Preview All' layout.")
        for tag, comp in self.components.items():
            if comp.rect_id:
                self.canvas.itemconfig(comp.rect_id, state='normal')
            if tag in self.preview_layout and "coords" in self.preview_layout[tag]:
                target_x1, target_y1, _, _ = self.preview_layout[tag]["coords"]
                width = comp.world_x2 - comp.world_x1
                height = comp.world_y2 - comp.world_y1
                comp.world_x1, comp.world_y1 = target_x1, target_y1
                comp.world_x2, comp.world_y2 = target_x1 + width, target_y1 + height
            if comp.pil_image is None and comp.rect_id:
                self.canvas.itemconfig(comp.rect_id, outline='white', width=2)
        self.redraw_all_zoomable()

    def open_export_folder(self, export_format: str):
        """Opens the specified export folder."""
        self.export_manager.open_export_folder(export_format)

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
        # REFACTOR: This logic is now correctly handled entirely by the ImageManager.
        self.image_manager.apply_decal_to_underlying_layer()
        self._keep_docks_on_top()

    def _update_mouse_coords(self, event):
        """Updates the world coordinate display based on mouse position."""
        world_x, world_y = self.camera.screen_to_world(event.x, event.y)
        self.mouse_coords_var.set(f"World: ({int(world_x)}, {int(world_y)})")

    def on_app_focus_in(self, event):
        """Handles the application window gaining focus."""
        # If the smart border tool is active when we regain focus, show the cursor.
        if self.smart_border_mode_active:
            print("[DEBUG] App gained focus, showing smart border cursor.")
            self.border_manager.smart_manager.cursor_window.show()

    def on_app_focus_out(self, event):
        """Handles the application window losing focus."""
        # If the smart border tool is active when we lose focus, hide the cursor.
        if self.smart_border_mode_active:
            print("[DEBUG] App lost focus, hiding smart border cursor.")
            self.border_manager.smart_manager.cursor_window.hide()


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