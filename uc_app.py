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
        self.paint_manager = PaintManager(self)
        self.camera = Camera(self, canvas)
        self.image_manager = ImageManager(self)
        # --- Initialize Components BEFORE UI that might use them ---
        # This resolves the AttributeError by ensuring self.components exists
        # before any callbacks (like on_image_set_changed) can be triggered.
        self._initialize_components()
        
        # Bind camera pan events directly to the canvas
        self.canvas.bind("<Control-Button-1>", self.camera.on_pan_press)
        self.canvas.bind("<Control-B1-Motion>", self.camera.on_pan_drag)
        # --- NEW: Bind right-click for tracing ---
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)


        # Bind canvas events now that all managers are initialized
        self.ui_manager.bind_canvas_events() # Binds paint events
        # --- NEW: Bind the universal eraser event ---
        self.bind_generic_drag_handler()
        self.ui_manager.create_ui()
        self.canvas.bind("<Motion>", self._update_mouse_coords) # NEW: Bind mouse motion to update coords

    def bind_generic_drag_handler(self):
        def on_drag(event): # This is the generic B1-Motion handler
            # If border tracing is active, it has its own drag handler, so we do nothing here.
            if self.border_manager.is_tracing or getattr(self.border_manager, 'is_magic_trace_active', False) or self.border_manager.is_magic_wand_active:
                return

            # Otherwise, delegate to the paint and eraser managers.
            if self.paint_manager.paint_mode_active or self.paint_manager.eraser_mode_active:
                self.paint_manager.paint_on_canvas(event)
            if self.paint_manager.universal_eraser_mode_active:
                self.paint_manager.erase_on_components(event)
        self.canvas.bind("<B1-Motion>", on_drag)

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
        self.border_manager.show_preset_preview()

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

    def on_component_press(self, event):
        """Handles press events on any component."""
        # --- NEW: Divert click to border tracer if active ---
        # --- FIX: Check all interactive border modes ---
        if self.border_manager.is_tracing or getattr(self.border_manager, 'is_magic_trace_active', False):
            # This mode has its own bindings, so we just stop propagation.
            return "break"

        if self.border_manager.is_magic_wand_active:
            self.border_manager.run_magic_wand(event)
            return

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

        if comp.is_dock_asset:
            # This is a click on a dock asset, which creates a clone.
            # It's not a move operation, so we don't save a move state.
            # Dock asset logic is handled by the dock canvas, not here.
            return

        self.dragged_item_tag = comp_tag
        self.last_drag_x = event.x
        self.last_drag_y = event.y
        
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
        else:
            self.redraw_all_zoomable()

        # --- FIX: If a border preview is active, update it when its parent moves ---
        if self.border_manager.preview_rect_ids:
            self.border_manager.show_preset_preview()

    def on_component_release(self, event):
        """Handles release events, finalizing the drag."""
        if self.dragged_item_tag:
            comp = self.components.get(self.dragged_item_tag)
            if comp:
                print(f"[DEBUG] Released '{comp.tag}' | Screen: ({event.x}, {event.y}) | New World TL: ({int(comp.world_x1)}, {int(comp.world_y1)})")
        self.dragged_item_tag = None

        # --- NEW: Finalize move operation for undo ---
        if self.pre_move_state:
            self._save_undo_state({'type': 'move', 'positions': self.pre_move_state})
            self.pre_move_state = {} # Clear the temporary state

        self._keep_docks_on_top()

    def on_canvas_right_click(self, event):
        """Handles right-click events on the canvas, primarily for border tracing."""
        if self.border_manager.is_tracing:
            self.border_manager.remove_last_trace_point(event)

    def move_all_main_tiles(self, dx_world, dy_world):
        """Moves all primary component tiles by a delta in world coordinates."""
        for comp in self.components.values():
            if not comp.is_dock_asset and not comp.is_decal:
                comp.world_x1 += dx_world; comp.world_y1 += dy_world
                comp.world_x2 += dx_world; comp.world_y2 += dy_world

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
            # Deactivate other modes
            self.paint_manager.toggle_paint_mode('off')
            
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
            action_type = last_state.get('type')

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
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        # Redraw all components that are meant to be zoomed/panned
        for comp in self.components.values():
            # --- DEFINITIVE FIX: Implement View Frustum Culling ---
            # 1. Calculate the component's on-screen bounding box.
            sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
            sx2, sy2 = self.camera.world_to_screen(comp.world_x2, comp.world_y2)

            # 2. Check if the component is outside the visible canvas area.
            if sx2 < 0 or sx1 > canvas_w or sy2 < 0 or sy1 > canvas_h:
                # If it's off-screen, hide it and skip all expensive processing.
                if comp.rect_id: self.canvas.itemconfig(comp.rect_id, state='hidden')
                continue # Go to the next component
            else:
                # If it's on-screen, ensure it's visible.
                if comp.rect_id: self.canvas.itemconfig(comp.rect_id, state='normal')

            # --- FIX: Handle components that have not been drawn yet ---
            # If a component (like a new clone) has no rect_id, it means it's not on the canvas.
            if not comp.rect_id:
                if comp.pil_image: # It's an image component (like a clone)
                    sx1, sy1 = self.camera.world_to_screen(comp.world_x1, comp.world_y1)
                    comp.rect_id = self.canvas.create_image(
                        sx1, sy1,
                        anchor=tk.NW,
                        tags=(comp.tag, "draggable", "zoom_target")
                    )
                    print(f"[DEBUG] Created initial canvas image for new component '{comp.tag}'.")

            if comp.rect_id: # Now, proceed with updating the component on the canvas
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

                    # --- DEFINITIVE FIX for GAPS ---
                    # Calculate screen coordinates first, then derive width/height from them.
                    screen_w, screen_h = sx2 - sx1, sy2 - sy1

                    # Only regenerate the Tkinter image if the size has actually changed.
                    if screen_w > 0 and screen_h > 0 and (int(screen_w) != comp._cached_screen_w or int(screen_h) != comp._cached_screen_h or comp.tk_image is None):
                        comp._cached_screen_w = int(screen_w); comp._cached_screen_h = int(screen_h)
                        if comp._cached_screen_w <= 0 or comp._cached_screen_h <= 0: continue
                        
                        source_img = comp.display_pil_image if comp.display_pil_image is not None else comp.pil_image # type: ignore
                        if not source_img: continue

                        resample_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.LANCZOS
                        resized_img = source_img.resize((comp._cached_screen_w, comp._cached_screen_h), resample_quality)
                        comp.tk_image = ImageTk.PhotoImage(resized_img)
                        self.canvas.itemconfig(comp.rect_id, image=comp.tk_image)

                    # Always update the item's screen coordinates.
                    self.canvas.coords(comp.rect_id, sx1, sy1)

                elif comp.text_id: # It's a placeholder
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

        # --- FIX: Redraw the border preview last to ensure it's on top ---
        # Only redraw the preview if the border tab is the one being displayed.
        if self.border_manager.preview_rect_ids and self.is_border_tab_active():
            self.border_manager.show_preset_preview()

        # --- NEW: Redraw the selection highlight ---
        self._update_selection_highlight()
            
        # Finally, ensure the status box is not obscured.
        self.canvas.tag_raise("status_box_frame") # This is not a real tag, but create_window items are always on top.
        self._keep_docks_on_top()

    def on_tab_changed(self, event):
        """Handles the event when the user clicks a different main tab."""
        # --- NEW: Clear any active border previews when switching context ---
        # Also, if the user is switching *to* the border tab, show the preview.
        if self.is_border_tab_active():
            self.master.after(10, lambda: self.border_manager.show_preset_preview()) # Use 'after' to ensure tab has changed
        else:
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

    def _export_modified_images(self, export_format):
        """Generic export function to save modified layers as either PNG or DDS."""
        print("-" * 30)
        print(f"Starting export process for {export_format.upper()}...")
        if export_format not in ['png', 'dds']:
            messagebox.showerror("Export Error", f"Unsupported export format: {export_format}")
            return

        save_dir = os.path.join(self.output_dir, f"export_{export_format}")
        os.makedirs(save_dir, exist_ok=True)

        paint_layer = self.paint_manager.paint_layer_image
        if paint_layer:
            # Create a full-canvas sized paint layer to composite with.
            paint_layer = paint_layer.resize((self.CANVAS_WIDTH, self.CANVAS_HEIGHT), Image.Resampling.LANCZOS)

        exported_count = 0

        # --- NEW: Pre-calculate which borders belong to which tiles ---
        borders_by_parent = {}
        for comp in self.components.values():
            # Find all created preset borders that have a parent.
            if comp.tag.startswith("preset_border_") and comp.parent_tag:
                parent_tag = comp.parent_tag
                if parent_tag not in borders_by_parent:
                    borders_by_parent[parent_tag] = []
                borders_by_parent[parent_tag].append(comp)

        for tag, comp in self.components.items():
            # We only export primary tiles, not assets, clones, or the borders themselves.
            if not comp.pil_image or comp.is_dock_asset or tag.startswith("clone_") or tag.startswith("preset_border_"):
                continue

            final_image = comp.pil_image.copy()
            has_paint = False
            has_borders = False
            if paint_layer:
                # Composite the paint layer onto the component's image
                final_image, has_paint = self.image_manager._composite_decal_onto_image(comp, paint_layer, 0, 0, self.CANVAS_WIDTH, self.CANVAS_HEIGHT, is_border=False)

            # --- NEW: Conditionally skip unmodified tiles based on UI checkbox ---
            if not self.export_all_tiles.get():
                is_modified = (comp.original_pil_image is not None and not self.image_manager._are_images_identical(comp.pil_image, comp.original_pil_image)) or has_paint
                if not is_modified:
                    # Also check if the only modification is an applied border
                    if tag not in borders_by_parent:
                        continue # Skip if not modified and has no borders

            # --- NEW: Composite any borders onto the final image ---
            if tag in borders_by_parent:
                for border_comp in borders_by_parent[tag]:
                    # Pass the current state of final_image to be drawn on
                    final_image, has_borders = self.image_manager._composite_border_onto_image(final_image, comp, border_comp)

            save_path = os.path.join(save_dir, f"{tag}.{export_format}")
            try:
                if export_format == 'dds':
                    texconv_path = os.path.join(self.tools_dir, "texconv.exe")
                    if not os.path.exists(texconv_path):
                        messagebox.showerror("DDS Export Error", f"texconv.exe not found at:\n{texconv_path}")
                        return

                    temp_png_path = os.path.join(save_dir, f"{tag}.png")
                    final_image.save(temp_png_path, format='PNG')

                    command = [texconv_path, "-f", "BC3_UNORM", "-o", save_dir, "-y", temp_png_path]
                    result = subprocess.run(command, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

                    if result.returncode != 0:
                        error_message = f"texconv.exe failed.\nSTDOUT:\n{result.stdout.strip()}\n\nSTDERR:\n{result.stderr.strip()}"
                        raise RuntimeError(error_message)
                    os.remove(temp_png_path)
                else:
                    final_image.save(save_path)

                exported_count += 1
                print(f"Saved modified image to: {save_path}")
            except (Exception, RuntimeError) as e:
                messagebox.showerror("DDS Export Error", f"Could not save '{os.path.basename(save_path)}'.\n\nDetails:\n{e}")

        if exported_count > 0:
            messagebox.showinfo("Export Complete", f"Successfully exported {exported_count} modified files.")
        else:
            messagebox.showinfo("Export Info", "No modified layers found to export.")

    def open_export_folder(self, export_format: str):
        """Opens the specified export folder."""
        folder_path = os.path.join(self.output_dir, f"export_{export_format}")
        if not os.path.isdir(folder_path):
            messagebox.showinfo("Folder Not Found", "The export folder does not exist yet. Please export images first.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

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