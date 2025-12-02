import tkinter as tk
from tkinter import messagebox, filedialog
import sys
import subprocess
from tkinter import ttk # Import for the Notebook widget
# Import Pillow components
from PIL import Image, ImageTk 

# --- NEW: Import Wand for better DDS support ---
try:
    from wand.image import Image as WandImage
    import io
    WAND_AVAILABLE = True
except ImportError:
    WAND_AVAILABLE = False
import os
from PIL import ImageDraw # NEW: For drawing on PIL images
import json # Required for saving and loading structured data
from PIL import ImageEnhance, ImageChops

# --- NEW: Centralized Path Management ---
def get_base_path():
    """ Get absolute path to resource, works for dev and for PyInstaller/Nuitka """
    if getattr(sys, 'frozen', False):
        # The application is frozen
        return os.path.dirname(sys.executable)
    else:
        # The application is not frozen, return the script's directory
        return os.path.dirname(os.path.abspath(__file__))

# --- CONFIGURATION (SCALED UP FOR LARGER GUI) ---
CANVAS_WIDTH = 1440  # Increased by 20% for a wider GUI
CANVAS_HEIGHT = 900  # Increased from 700
SIDEBAR_WIDTH = 300  # Increased by 20%

class DraggableComponent:
    """
    A class to represent and manage an independent, draggable element 
    on the Tkinter canvas, now supporting real images with transparency.
    """
    def __init__(self, canvas, app_instance, tag, x1, y1, x2, y2, color, text):
        self.canvas = canvas
        self.app = app_instance # NEW: Reference to the main app
        self.tag = tag
        self.last_x = 0
        self.last_y = 0
        self.tk_image = None # Reference to the PhotoImage object
        self.preview_pil_image = None # NEW: For dock previews
        self.pil_image = None # Reference to the PIL Image object
        self.border_pil_image = None # NEW: For storing the border image
        self.original_pil_image = None # NEW: For storing the pristine decal image
        self.rect_id = None
        self.text_id = None
        self.is_draggable = True # Control whether the component can be dragged
        self.is_decal = False # NEW: To identify temporary decals
        self.is_border_asset = False # NEW: To identify border assets
        
        # --- NEW: Caching for Performance ---
        self._cached_screen_w = -1
        self._cached_screen_h = -1

        self.is_dock_asset = False # NEW: To identify dock assets
        # Initialize with the colored box
        self._draw_placeholder(x1, y1, x2, y2, color, text)
        
        # 2. Bind the mouse events to all items with the 'draggable' tag
        self.canvas.tag_bind(self.tag, '<Button-1>', self.on_press)
        self.canvas.tag_bind(self.tag, '<B1-Motion>', self.on_drag)
        self.canvas.tag_bind(self.tag, '<ButtonRelease-1>', self.on_release)

    def _draw_placeholder(self, x1, y1, x2, y2, color, text):
        """Draws the initial colored rectangle and text."""
        # Clear previous items if they exist
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)

        self.rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, 
                                                     fill=color, 
                                                     outline='white',
                                                     width=2)
        
        self.text_id = self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, 
                                              text=text, 
                                              fill="white", 
                                              font=("Inter", 16, "bold"), # Increased font size
                                              tags=(self.tag, "draggable")) # Text needs draggable for selection
        
        # Add tags to the rectangle. Only non-dock assets are zoomable.
        tags_to_add = [self.tag, "draggable"]
        if not self.is_dock_asset:
            tags_to_add.append("zoom_target")
        self.canvas.addtag_withtag(tags_to_add[0], self.rect_id)
        for t in tags_to_add[1:]:
            self.canvas.addtag_withtag(t, self.rect_id)
        # Update bounding box of the component
        # self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        # With the camera system, the component's own coordinates are the world coordinates.
        self.world_x1, self.world_y1, self.world_x2, self.world_y2 = x1, y1, x2, y2


    def set_image_from_path(self, image_path):
        """Loads an image from a file path and applies it to the component."""
        try:
            pil_image = Image.open(image_path).convert("RGBA")
            self._set_pil_image(pil_image)
            print(f"Image loaded for {self.tag}: {os.path.basename(image_path)}")
        except Exception as e:
            messagebox.showerror("Image Error", f"Could not load image: {e}")

    def _set_pil_image(self, pil_image, resize_to_fit=True):
        """
        Core logic to apply a PIL image to this component.
        `resize_to_fit` determines if the image should be stretched to the component's bounds.
        """
        self.pil_image = pil_image
        
        # Store the very first image loaded as the 'original' for reset purposes
        if not self.original_pil_image:
            self.original_pil_image = pil_image

        # --- NEW: Composite border if it exists ---
        if self.border_pil_image:
            pil_image = self._composite_border(pil_image)

        # With the camera system, we use the world coordinates to determine size and position.
        x_start, y_start = self.app.world_to_screen(self.world_x1, self.world_y1)
        x_end, y_end = self.app.world_to_screen(self.world_x2, self.world_y2)

        if resize_to_fit:
            # Resize the PIL image to fit the current component's world size
            # For dock assets, use the specific preview image
            image_to_render = self.preview_pil_image if self.is_dock_asset else self.pil_image
            w, h = int(self.world_x2 - self.world_x1), int(self.world_y2 - self.world_y1)
            image_to_render = image_to_render.resize((w, h), Image.Resampling.LANCZOS) if w > 0 and h > 0 else image_to_render
        else:
            # Use the image at its original size
            image_to_render = self.pil_image

        # Convert PIL image to Tkinter PhotoImage
        new_tk_image = ImageTk.PhotoImage(image_to_render)

        # Delete old placeholder items if they exist
        self.canvas.delete(self.rect_id)
        if self.text_id:
            self.canvas.delete(self.text_id)
            self.text_id = None

        # Create new image item on canvas, anchored at the top-left
        self.rect_id = self.canvas.create_image(x_start, y_start,
                                                 image=new_tk_image,
                                                 anchor=tk.NW,
                                                 tags=(self.tag, "draggable"))
        # --- NEW: Conditionally add the zoom_target tag ---
        # Clones and main tiles should be zoomable, but dock assets should not.
        if not self.is_dock_asset:
            self.canvas.addtag_withtag("zoom_target", self.rect_id)

        # Must store a reference to avoid garbage collection
        self.tk_image = new_tk_image

    def set_border_image(self, border_image_path):
        """Loads and applies a border image from a file path."""
        if not self.pil_image:
            messagebox.showwarning("No Content", "Please apply a main image to the tile before adding a border.")
            return

        try:
            self.border_pil_image = Image.open(border_image_path).convert("RGBA")
            # Re-apply the main image to trigger the border composition
            self._set_pil_image(self.pil_image)
            print(f"Border '{os.path.basename(border_image_path)}' applied to {self.tag}")
        except Exception as e:
            messagebox.showerror("Border Error", f"Could not load border image: {e}")

    def remove_border(self):
        """Removes the border and redraws the component."""
        if self.border_pil_image:
            self.border_pil_image = None
            # Re-apply the main image to redraw without the border
            self._set_pil_image(self.pil_image)
            print(f"Border removed from {self.tag}")

    def _composite_border(self, base_image):
        """Composites the border image on top of the base image."""
        if not self.border_pil_image:
            return base_image
        border_resized = self.border_pil_image.resize(base_image.size, Image.Resampling.LANCZOS)
        return Image.alpha_composite(base_image.copy(), border_resized)

    def on_press(self, event):
        """Records the starting position and brings the element to the front."""
        # --- NEW: Clone-on-drag for dock assets ---
        if self.is_dock_asset:
            # --- FIX: Check for clicks on transparent areas ---
            bbox = self.canvas.bbox(self.rect_id)
            if not bbox: return

            # Check if click is within the bounding box
            if not (bbox[0] <= event.x <= bbox[2] and bbox[1] <= event.y <= bbox[3]):
                return

            # Calculate click position relative to the image's top-left corner
            rel_x = int(event.x - bbox[0])
            rel_y = int(event.y - bbox[1])

            try:
                # Get the alpha value of the pixel that was clicked
                alpha = (self.preview_pil_image or self.original_pil_image).getpixel((rel_x, rel_y))[3]
                if alpha > 10:  # Threshold to ignore near-transparent pixels
                    self.app.create_clone_from_asset(self, event)
            except (IndexError, TypeError):
                # This can happen if clicking right on the edge; ignore it.
                pass
            return  # Always stop processing for the dock asset itself

        # Store the current mouse position
        self.last_x = event.x
        self.last_y = event.y
        
        # Raise the entire component to the front (this allows dragging over other items)
        self.canvas.tag_raise(self.rect_id)
        if self.text_id:
            self.canvas.tag_raise(self.text_id)

    def on_drag(self, event):
        """Calculates the distance moved and updates the element's position."""
        if not self.is_draggable:
            return # Do not drag if painting is active

        # --- FIX: Prevent dock assets from being dragged directly ---
        if self.is_dock_asset:
            return # Do not drag if painting is active

        # --- REFACTORED for Camera System ---
        # Calculate movement in world space, not screen space.
        dx_screen = event.x - self.last_x
        dy_screen = event.y - self.last_y
        dx_world = dx_screen / self.app.zoom_scale
        dy_world = dy_screen / self.app.zoom_scale

        # --- FINAL REWRITE: Clamp movement to composition area ---
        # Calculate the potential new world coordinates
        new_world_x1 = self.world_x1 + dx_world
        new_world_y1 = self.world_y1 + dy_world

        # Get composition area bounds from the app instance
        bounds = self.app
        tile_w = self.world_x2 - self.world_x1
        tile_h = self.world_y2 - self.world_y1

        # Clamp X coordinates
        if new_world_x1 < bounds.COMP_AREA_X1:
            new_world_x1 = bounds.COMP_AREA_X1
        if new_world_x1 + tile_w > bounds.COMP_AREA_X2:
            new_world_x1 = bounds.COMP_AREA_X2 - tile_w

        # Clamp Y coordinates
        if new_world_y1 < bounds.COMP_AREA_Y1:
            new_world_y1 = bounds.COMP_AREA_Y1
        if new_world_y1 + tile_h > bounds.COMP_AREA_Y2:
            new_world_y1 = bounds.COMP_AREA_Y2 - tile_h

        # Update the component's world coordinates with the final clamped values
        self.world_x1, self.world_y1 = new_world_x1, new_world_y1
        self.world_x2, self.world_y2 = new_world_x1 + tile_w, new_world_y1 + tile_h
        
        # Update the last screen position for the next drag event
        self.last_x = event.x
        self.last_y = event.y
        
        # Redraw all zoomable items to reflect the change in world coordinates
        self.app.redraw_all_zoomable()

    def on_release(self, event):
        """Action after drag finishes (optional)."""
        # --- FIX: Ensure dock assets are always on top after a drag ---
        self.app._keep_docks_on_top()

    def select(self, app_instance):
        """Simulate selecting this component in the sidebar and update app state."""
        app_instance.set_selected_component(self.tag) # Update the application's selection state
        
        # Reset borders for all items
        for comp in app_instance.components.values():
            if comp.rect_id:
                 # We only draw the border outline on placeholders (where tk_image is None)
                 if comp.tk_image is None: 
                     self.canvas.itemconfig(comp.rect_id, outline='white', width=2)
        
        # Highlight the current item only if it's a placeholder box
        if self.tk_image is None:
            self.canvas.itemconfig(self.rect_id, outline='yellow', width=3)
        
        print(f"Component selected: {self.tag}")


class ImageEditorApp:
    def __init__(self, master):
        self.master = master
        master.configure(bg="#1f2937") # NEW: Set a dark background for the root window
        master.title("UI Creator")
        master.state('zoomed') # NEW: Maximize the window on startup
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
        
        # --- REFACTORED: Camera-based Zoom and Pan State ---
        self.zoom_scale = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.pan_start_x = 0 # For tracking drag start
        self.pan_start_y = 0 # For tracking drag start
        self.zoom_label_var = tk.StringVar(value="100%") # NEW: For zoom display

        master.bind("<Control-MouseWheel>", self.on_zoom)
        master.bind("<Control-plus>", self.zoom_in)
        master.bind("<Control-equal>", self.zoom_in) # For keyboards where '+' is shift+'='
        master.bind("<Control-minus>", self.zoom_out)
        self.paint_mode_active = False
        self.eraser_mode_active = False # NEW: Eraser state
        self.paint_color = "red"
        self.brush_size = tk.IntVar(value=4)
        self.last_paint_x, self.last_paint_y = None, None
        # --- NEW: Dedicated Paint Layer ---
        self.paint_layer_image = None # The PIL Image for painting.
        self.paint_layer_tk = None    # The PhotoImage for displaying on the canvas
        self.paint_layer_id = None    # The canvas item ID for the paint layer
        
        # --- NEW: Decal Feature State ---
        self.active_decal = None
        self.decal_scale = tk.DoubleVar(value=100) # For the resize slider
        self.transform_job = None # NEW: For debouncing slider updates
        self.decal_rotation = tk.DoubleVar(value=0) # NEW: For the rotation slider

        # --- NEW: Composition Area Bounds ---
        # These define the draggable area for tiles.
        self.COMP_AREA_X1 = 0
        self.COMP_AREA_Y1 = 50
        self.COMP_AREA_X2 = 1407
        self.COMP_AREA_Y2 = 400

        # --- NEW: Asset Dock State ---
        self.dock_assets = []
        self.next_dynamic_id = 0 # FIX: Unified counter for clones and assets

        # --- NEW: Separate dock positions ---
        self.IMAGE_DOCK_Y = 550
        self.BORDER_DOCK_Y = 730 # Positioned below the image dock
        self.next_image_dock_x = 20
        self.next_border_dock_x = 20

        self.DOCK_ASSET_SIZE = (128, 128)
        # Create a main frame to hold everything
        # --- NEW: Define base paths for UI Creator resources ---
        self.base_path = get_base_path() 
        self.ui_creator_contents_path = os.path.join(self.base_path, "Contents", "ui creator")
        self.image_base_dir = os.path.join(self.ui_creator_contents_path, "images")
        self.tools_dir = os.path.join(self.ui_creator_contents_path, "tools")
        self.output_dir = os.path.join(self.ui_creator_contents_path, "output")
        self.layouts_dir = os.path.join(self.ui_creator_contents_path, "layouts")
        self.main_frame = tk.Frame(master, padx=10, pady=10, bg="#1f2937")
        self.main_frame.pack(fill="both", expand=True)

        # --- NEW: Scan for available image sets (subdirectories) ---
        self.image_sets = []
        if os.path.isdir(self.image_base_dir):
            self.image_sets = [d for d in os.listdir(self.image_base_dir) if os.path.isdir(os.path.join(self.image_base_dir, d))]
        self.selected_image_set = tk.StringVar()
        self.selected_image_set.trace_add("write", self.on_image_set_changed)

        # --- 1. Main Canvas (Left/Center) ---
        self.canvas = tk.Canvas(self.main_frame, 
                                 width=CANVAS_WIDTH, 
                                 height=CANVAS_HEIGHT, 
                                 bg="#2d3748", # Darker canvas background
                                 highlightthickness=0)
        # Use grid to place the canvas, leaving space for the toolbar above
        self.canvas.grid(row=0, column=0, padx=(0, 10), sticky="nsew", rowspan=2)
        self.main_frame.grid_columnconfigure(0, weight=1) 
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # Bind painting events directly to the canvas
        self.canvas.bind("<B1-Motion>", self.paint_on_canvas)
        self.canvas.bind("<ButtonRelease-1>", self.reset_paint_line)
        # --- NEW: Pan bindings ---
        self.canvas.bind("<Control-Button-1>", self.on_pan_press)
        self.canvas.bind("<Control-B1-Motion>", self.on_pan_drag)
        self.canvas.bind("<Control-ButtonRelease-1>", self.on_pan_release)
        
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
        
        # --- BACKGROUND TEMPLATE ---
        # This is the main background that other components will be placed on.
        # We create it first so it's at the bottom of the Z-order.
        # Adjusted dimensions to better fit the preview layout.
        # self.background_template = self.canvas.create_rectangle(
        #     0, 50, CANVAS_WIDTH - 140, 450, # Final position adjustment
        #     fill="#1f2937", 
        #     outline="#4b5563", 
        #     width=3,
        #     tags="background" # Tag for easy reference
        # )
        # self.canvas.create_text(CANVAS_WIDTH/2, 25, text="COMPOSITION AREA (Drag components here)", fill="#9ca3af", font=("Inter", 12))

        # Draw a placeholder for the main template background and tag it for zooming
        self.canvas.create_rectangle(self.COMP_AREA_X1, self.COMP_AREA_Y1, self.COMP_AREA_X2, self.COMP_AREA_Y2,
                                     fill="#374151", # Slightly lighter than canvas bg
                                     outline="#4b5563",
                                     width=3,
                                     tags="zoom_target")

        # --- NEW: Create the floating status box in the top-left ---
        status_box_frame = tk.Frame(self.canvas, bg="#1f2937", bd=1, relief="solid", highlightbackground="#4b5563", highlightthickness=1)
        
        self.undo_button = tk.Button(status_box_frame, text="Undo / Ctrl Z", bg='#4b5563', fg='white', relief='flat', font=('Inter', 10, 'bold'),
                                     command=self.undo_last_action, state='disabled', padx=5, pady=2)
        self.undo_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        zoom_label = tk.Label(status_box_frame, textvariable=self.zoom_label_var, bg="#1f2937", fg="#d1d5db", font=('Inter', 10, 'bold'))
        zoom_label.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.reset_view_button = tk.Button(status_box_frame, text="Reset View", bg='#6b7280', fg='white', relief='flat', font=('Inter', 10, 'bold'),
                                           command=self.reset_view, padx=5, pady=2)
        self.reset_view_button.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        # Place the frame on the canvas without it being a canvas item
        self.canvas.create_window(10, 10, window=status_box_frame, anchor="nw")


        # --- NEW: Draw the Image Asset Dock Area ---
        self.canvas.create_text(CANVAS_WIDTH/2, self.IMAGE_DOCK_Y - 20, text="Image Dock (Click image and drag)", fill="#9ca3af", font=("Inter", 12), tags="no_zoom")
        self.canvas.create_rectangle(0, self.IMAGE_DOCK_Y, CANVAS_WIDTH, self.IMAGE_DOCK_Y + self.DOCK_ASSET_SIZE[1] + 20,
                                     fill="#374151", # Match composition area
                                     outline="#4b5563",
                                     width=3,
                                     tags="no_zoom")

        # --- NEW: Draw the Border Asset Dock Area ---
        self.canvas.create_text(CANVAS_WIDTH/2, self.BORDER_DOCK_Y - 20, text="Border Dock (Click border and drag)", fill="#9ca3af", font=("Inter", 12), tags="no_zoom")
        self.canvas.create_rectangle(0, self.BORDER_DOCK_Y, CANVAS_WIDTH, self.BORDER_DOCK_Y + self.DOCK_ASSET_SIZE[1] + 20,
                                     fill="#374151", # Match composition area
                                     outline="#4b5563",
                                     width=3,
                                     tags="no_zoom")


        # --- 2. Initialize Draggable Components (Layers) ---
        self.components = {}
        base_color = "#1e40af" # A more modern, vibrant blue

        # Define tile dimensions for the 4x2 grid (increased size)
        tile_width = 250
        tile_height = 300
        
        # Define starting coordinates for the 4x2 grid with 50px padding/spacing
        # C1_X=50, C2_X=350, C3_X=650, C4_X=950
        # R1_Y=50, R2_Y=400 (50 + 300 + 50)
        
        # TILE 01 (Row 1, Col 1)
        self.components['humanuitile01'] = DraggableComponent(
            self.canvas, self, "humanuitile01", 
            50, 50, 300, 350, # W:250, H:300
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
        
        # --- 3. Sidebar (Right Column) ---
        self.sidebar_frame = tk.Frame(self.main_frame, width=SIDEBAR_WIDTH, bg="#1f2937")
        self.sidebar_frame.grid(row=0, column=1, sticky="nswe", rowspan=2) # Span across toolbar row
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # Define the list of tab/component names 
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
        
        self.create_sidebar_tabs() # Replaced old method with new tabbed one
        # Set a default selected component
        self.set_selected_component('humanuitile01')
        
        # --- 4. Auto-Load Images ---
        # If there are image sets, select the first one by default.
        # Otherwise, fall back to loading from the base images directory.
        if self.image_sets:
            self.selected_image_set.set(self.image_sets[0])
        else:
            self._attempt_auto_load_images(self.image_base_dir)
            
        # --- 5. Apply Initial Layout ---
        self.apply_preview_layout()


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


    def create_sidebar_tabs(self):
        """Creates a tabbed interface in the sidebar for organizing controls."""
        # --- Notebook (Tab) Setup ---
        ttk.Style().theme_use('clam') # FIX: Force a modern theme to ensure custom styles are applied.
        style = ttk.Style(self.master)
        style.configure('TNotebook', background="#1f2937", borderwidth=0)
        style.configure('TNotebook.Tab', font=('Inter', 11, 'bold'), padding=[15, 5], background="#374151", foreground="#d1d5db", borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#4b5563")], foreground=[("selected", "white")])

        notebook = ttk.Notebook(self.sidebar_frame, style='TNotebook')
        notebook.pack(expand=True, fill='both')

        # --- Create Frames for each Tab ---
        layer_tab = tk.Frame(notebook, bg="#374151")
        paint_tab = tk.Frame(notebook, bg="#374151")
        image_tab = tk.Frame(notebook, bg="#374151")
        filters_tab = tk.Frame(notebook, bg="#374151") # NEW
        border_tab = tk.Frame(notebook, bg="#374151") # NEW
        resize_tab = tk.Frame(notebook, bg="#374151") # NEW
        text_tab = tk.Frame(notebook, bg="#374151") # NEW
        export_tab = tk.Frame(notebook, bg="#374151")

        notebook.add(layer_tab, text='Tiles')
        notebook.add(paint_tab, text='Paint')
        notebook.add(border_tab, text='Border')
        notebook.add(image_tab, text='Image')
        notebook.add(resize_tab, text='Resize Tile')
        notebook.add(filters_tab, text='Filters') # NEW
        notebook.add(text_tab, text='Text') # NEW
        notebook.add(export_tab, text='Export')

        # --- Common Styles ---
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')

        # --- Populate the "Layer" Tab ---
        tk.Label(layer_tab, text="TILE SELECT", **label_style).pack(fill='x')
        
        # Layer Selection Buttons
        for i, name in enumerate(self.component_list):
            button_style = {
                'text': name,
                'bg': '#4b5563' if name == "Show All" else '#6b7280',
                'fg': 'white', 'relief': 'flat', 'pady': 8, 'font': ('Inter', 11),
                'command': lambda n=name: self.handle_tab_click(n)
            }
            btn = tk.Button(layer_tab, **button_style)
            btn.pack(fill='x', padx=10, pady=(2 if i > 0 else 5))
        
        # Add a separator before the next section
        tk.Frame(layer_tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)

        # --- Save/Load Layout Buttons ---
        tk.Label(layer_tab, text="TILE LOCATION PRESET", **label_style).pack(fill='x')
        layout_frame = tk.Frame(layer_tab, bg="#374151")
        layout_frame.pack(fill='x', padx=10, pady=5)
        tk.Button(layout_frame, text="Save Layout", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.save_layout).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        tk.Button(layout_frame, text="Load Layout", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.load_layout).pack(side=tk.RIGHT, fill='x', expand=True, padx=(5, 0))
        tk.Button(layer_tab, text="Default Layout", bg='#6b7280', fg='white', relief='flat', font=button_font,
                  command=self.apply_preview_layout).pack(fill='x', padx=10, pady=5)


        # --- Populate the "Image" Tab ---
        tk.Label(image_tab, text="IMAGE SET", **label_style).pack(fill='x')
        # Create the dropdown menu for image sets
        if self.image_sets:
            image_set_menu = ttk.OptionMenu(image_tab, self.selected_image_set, self.image_sets[0], *self.image_sets)
            image_set_menu.pack(fill='x', padx=10, pady=5)
        else:
            tk.Label(image_tab, text="No image sets found in 'images' folder.", bg="#374151", fg="#9ca3af", padx=10).pack(fill='x')


        # --- Populate the "Paint" Tab ---
        tk.Label(paint_tab, text="PAINTING TOOLS", **label_style).pack(fill='x')
        paint_frame = tk.Frame(paint_tab, bg="#374151")
        paint_frame.pack(fill='x', padx=10, pady=5)
        self.paint_toggle_btn = tk.Button(paint_frame, text="Enable Paint Mode", bg='#d97706', fg='white', relief='flat', font=button_font,
                                          command=lambda: self.toggle_paint_mode(tool='paint'))
        self.paint_toggle_btn.pack(fill='x', expand=True)

        # --- NEW: Eraser Button ---
        self.eraser_toggle_btn = tk.Button(paint_frame, text="Enable Eraser", bg='#6b7280', fg='white', relief='flat', font=button_font,
                                           command=lambda: self.toggle_paint_mode(tool='eraser'))
        self.eraser_toggle_btn.pack(fill='x', expand=True, pady=(5,0))

        # Add a separator
        tk.Frame(paint_frame, height=2, bg="#6b7280").pack(fill='x', pady=10)

        color_btn = tk.Button(paint_frame, text="Choose Color", bg='#6b7280', fg='white', relief='flat', font=('Inter', 10),
                              command=self.choose_paint_color, state='disabled')
        color_btn.pack(fill='x', expand=True, pady=(5,0))
        brush_size_frame = tk.Frame(paint_frame, bg="#374151")
        brush_size_frame.pack(fill='x', pady=5)
        tk.Label(brush_size_frame, text="Size:", bg="#374151", fg="white").pack(side=tk.LEFT)
        tk.Scale(brush_size_frame, from_=1, to=50, orient=tk.HORIZONTAL, variable=self.brush_size, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0).pack(side=tk.LEFT, expand=True)
        clear_paint_btn = tk.Button(paint_frame, text="Clear All Paintings", bg='#ef4444', fg='white', relief='flat', font=('Inter', 10),
                                    command=self.clear_paintings)
        clear_paint_btn.pack(fill='x', expand=True, pady=(5,0))

        tk.Label(image_tab, text="ASSET & DECAL CONTROLS", **label_style).pack(fill='x', pady=(10,0))
        tk.Button(image_tab, text="Load Asset to Dock", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.load_asset_to_dock).pack(fill='x', padx=10, pady=(5,10))

        # --- NEW: Decal Transform Controls (Resize & Rotate) ---
        transform_frame = tk.Frame(image_tab, bg="#374151")
        transform_frame.pack(fill='x', padx=10, pady=5)
        
        # Resize Slider
        tk.Label(transform_frame, text="Resize:", bg="#374151", fg="white").grid(row=0, column=0, sticky='w')
        tk.Scale(transform_frame, from_=10, to=200, orient=tk.HORIZONTAL, variable=self.decal_scale,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0, command=lambda e: self._update_active_decal_transform(use_fast_preview=True)).grid(row=0, column=1, sticky='ew')
        tk.Button(transform_frame, text="Reset", bg='#6b7280', fg='white', relief='flat', font=('Inter', 8),
                  command=lambda: self.decal_scale.set(100) or self._update_active_decal_transform()).grid(row=0, column=2, padx=(5,0))

        # Rotation Slider
        tk.Label(transform_frame, text="Rotate:", bg="#374151", fg="white").grid(row=1, column=0, sticky='w')
        tk.Scale(transform_frame, from_=-180, to=180, orient=tk.HORIZONTAL, variable=self.decal_rotation,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0, command=lambda e: self._update_active_decal_transform(use_fast_preview=True)).grid(row=1, column=1, sticky='ew')
        tk.Button(transform_frame, text="Reset", bg='#6b7280', fg='white', relief='flat', font=('Inter', 8),
                  command=lambda: self.decal_rotation.set(0) or self._update_active_decal_transform()).grid(row=1, column=2, padx=(5,0))
        transform_frame.grid_columnconfigure(1, weight=1)

        # --- Apply/Discard buttons for Images ---
        image_action_frame = tk.Frame(image_tab, bg="#374151")
        image_action_frame.pack(fill='x', padx=10, pady=(10, 5))
        tk.Button(image_action_frame, text="Apply Image", bg='#10b981', fg='white', relief='flat', font=button_font,
                  command=self.apply_decal_to_underlying_layer).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        tk.Button(image_action_frame, text="Discard Image", bg='#ef4444', fg='white', relief='flat', font=button_font,
                  command=self.discard_active_image).pack(side=tk.RIGHT, fill='x', expand=True, padx=(5, 0))

        
        # --- Populate the "Resize" Tab ---
        tk.Label(resize_tab, text="RESIZE TILE", **label_style).pack(fill='x')
        resize_frame = tk.Frame(resize_tab, bg="#374151", padx=10, pady=5)
        resize_frame.pack(fill='x')

        tk.Label(resize_frame, text="Width:", bg="#374151", fg="white").grid(row=0, column=0, sticky='w', pady=2)
        tk.Entry(resize_frame, textvariable=self.resize_width, width=10).grid(row=0, column=1, sticky='ew')

        tk.Label(resize_frame, text="Height:", bg="#374151", fg="white").grid(row=1, column=0, sticky='w', pady=2)
        tk.Entry(resize_frame, textvariable=self.resize_height, width=10).grid(row=1, column=1, sticky='ew')
        
        resize_frame.grid_columnconfigure(1, weight=1)

        tk.Checkbutton(resize_tab, text="Maintain Aspect Ratio", variable=self.maintain_aspect,
                        bg="#374151", fg="white", selectcolor="#1f2937", activebackground="#374151", activeforeground="white",
                        command=self.update_resize_entries).pack(pady=5)
        tk.Button(resize_tab, text="Apply Size", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.resize_selected_component).pack(fill='x', padx=10, pady=5)

        # --- Populate the "Border" Tab ---
        tk.Label(border_tab, text="BORDER CONTROLS", **label_style).pack(fill='x')
        tk.Button(border_tab, text="Load Border to Dock", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.load_border_to_dock).pack(fill='x', padx=10, pady=5)

        # --- NEW: Border Transform Controls (Resize & Rotate) ---
        border_transform_frame = tk.Frame(border_tab, bg="#374151")
        border_transform_frame.pack(fill='x', padx=10, pady=5)
        tk.Label(border_transform_frame, text="Resize:", bg="#374151", fg="white").grid(row=0, column=0, sticky='w')
        tk.Scale(border_transform_frame, from_=10, to=200, orient=tk.HORIZONTAL, variable=self.decal_scale,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0, command=lambda e: self._update_active_decal_transform(use_fast_preview=True)).grid(row=0, column=1, sticky='ew')
        tk.Button(border_transform_frame, text="Reset", bg='#6b7280', fg='white', relief='flat', font=('Inter', 8),
                  command=lambda: self.decal_scale.set(100) or self._update_active_decal_transform()).grid(row=0, column=2, padx=(5,0))
        tk.Label(border_transform_frame, text="Rotate:", bg="#374151", fg="white").grid(row=1, column=0, sticky='w')
        tk.Scale(border_transform_frame, from_=-180, to=180, orient=tk.HORIZONTAL, variable=self.decal_rotation,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0, command=lambda e: self._update_active_decal_transform(use_fast_preview=True)).grid(row=1, column=1, sticky='ew')
        tk.Button(border_transform_frame, text="Reset", bg='#6b7280', fg='white', relief='flat', font=('Inter', 8),
                  command=lambda: self.decal_rotation.set(0) or self._update_active_decal_transform()).grid(row=1, column=2, padx=(5,0))
        border_transform_frame.grid_columnconfigure(1, weight=1)

        # --- Apply/Discard buttons for Borders ---
        border_action_frame = tk.Frame(border_tab, bg="#374151")
        border_action_frame.pack(fill='x', padx=10, pady=5)
        tk.Button(border_action_frame, text="Apply Border", bg='#10b981', fg='white', relief='flat', font=button_font,
                  command=self.apply_border_to_selection).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        tk.Button(border_action_frame, text="Discard Border", bg='#ef4444', fg='white', relief='flat', font=button_font,
                  command=self.discard_active_image).pack(side=tk.RIGHT, fill='x', expand=True, padx=(5, 0))


        # --- Populate the "Filters" Tab (Placeholder) ---
        tk.Label(filters_tab, text="IMAGE FILTERS", **label_style).pack(fill='x')
        tk.Label(filters_tab, text="Controls for brightness, contrast, etc.\nwill go here.", bg="#374151", fg="#9ca3af", justify=tk.LEFT, padx=10).pack(fill='x', pady=10)

        # --- Populate the "Text" Tab (Placeholder) ---
        tk.Label(text_tab, text="TEXT TOOLS", **label_style).pack(fill='x')
        tk.Label(text_tab, text="Controls for adding and styling text\nwill go here.", bg="#374151", fg="#9ca3af", justify=tk.LEFT, padx=10).pack(fill='x', pady=10)


        # --- Populate the "Export" Tab ---
        tk.Label(export_tab, text="EXPORT CONTROLS", **label_style).pack(fill='x')
        tk.Button(export_tab, text="Save Modified PNGs", bg='#10b981', fg='white', relief='flat', font=button_font,
                  command=lambda: self._export_modified_images('png')).pack(fill='x', padx=10, pady=5)
        
        # --- NEW: DDS Export Button ---
        tk.Button(export_tab, text="Save Modified as DDS", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=lambda: self._export_modified_images('dds')).pack(fill='x', padx=10, pady=(5, 10))
        tk.Label(export_tab, text="Note: DDS export requires the image\ndimensions to be a power of two\n(e.g., 256x256, 512x512) and may not\nsupport all internal DDS formats.",
                 bg="#374151", fg="#9ca3af", justify=tk.LEFT, padx=10).pack(fill='x')
        
        # Keep a reference to the color button to enable/disable it
        self.paint_color_button = color_btn


    def toggle_paint_mode(self, tool: str):
        """Toggles the painting or erasing mode on or off."""
        # Determine which tool is being activated and which is being deactivated
        is_activating_paint = tool == 'paint' and not self.paint_mode_active
        is_activating_eraser = tool == 'eraser' and not self.eraser_mode_active

        # Deactivate all tools first
        self.paint_mode_active = False
        self.eraser_mode_active = False
        self.paint_toggle_btn.config(text="Enable Paint Mode", bg='#d97706', relief='flat')
        self.eraser_toggle_btn.config(text="Enable Eraser", bg='#6b7280', relief='flat')
        self.paint_color_button.config(state='disabled')

        # Activate the selected tool if it wasn't already active
        if is_activating_paint:
            self.paint_mode_active = True
            self.paint_toggle_btn.config(text="Disable Paint Mode", bg='#ef4444', relief='sunken')
            self.paint_color_button.config(state='normal')
            print("Paint mode ENABLED.")
        elif is_activating_eraser:
            self.eraser_mode_active = True
            self.eraser_toggle_btn.config(text="Disable Eraser", bg='#ef4444', relief='sunken')
            print("Eraser mode ENABLED.")
        else:
            print("Paint and Eraser modes DISABLED.")

        # Common logic for when any tool is active vs. when all are inactive
        is_any_tool_active = self.paint_mode_active or self.eraser_mode_active
        if is_any_tool_active:
            # --- NEW: Create the transparent paint layer ---
            if not self.paint_layer_image:
                canvas_w = self.canvas.winfo_width()
                canvas_h = self.canvas.winfo_height()
                self.paint_layer_image = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                self.paint_layer_tk = ImageTk.PhotoImage(self.paint_layer_image)
                self.paint_layer_id = self.canvas.create_image(0, 0, image=self.paint_layer_tk, anchor=tk.NW, tags=("paint_layer", "zoom_target"), state='normal') # Save initial blank state for undo
                self._save_undo_state(self.paint_layer_image.copy())

            # Disable dragging for all components
            for comp in self.components.values():
                comp.is_draggable = False

            # Ensure the paint layer is on top of components but below the UI docks
            self.canvas.tag_raise(self.paint_layer_id)
            self._keep_docks_on_top()
        else:
            # Re-enable dragging for all components
            for comp in self.components.values():
                comp.is_draggable = True
            print("Paint mode DISABLED. Component dragging is enabled.")

    def choose_paint_color(self):
        """Opens a color chooser and sets the paint color."""
        from tkinter import colorchooser
        color_code = colorchooser.askcolor(title="Choose paint color")
        if color_code and color_code[1]:
            self.paint_color = color_code[1]
            print(f"Paint color set to: {self.paint_color}")

    def clear_paintings(self):
        """Removes all lines drawn on the canvas."""
        if self.paint_layer_image:
            # Save current paint state before clearing
            self._save_undo_state(self.paint_layer_image.copy())

            # Create a new, blank transparent image
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            self.paint_layer_image = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            # Update the canvas to show the cleared image
            self._update_paint_layer_display()
            print("All paintings have been cleared.")

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
            self.paint_layer_image = last_state
            self._update_paint_layer_display()
        elif isinstance(last_state, dict): # It's a component image state
            for tag, image in last_state.items():
                if tag in self.components:
                    self.components[tag]._set_pil_image(image)
                    print(f"Reverted image for component '{tag}'.")

        print("Undo successful.")
        # Disable button if stack is now empty
        if not self.undo_stack:
            self.undo_button.config(state='disabled')

    # --- NEW: Camera Transformation Functions ---
    def world_to_screen(self, world_x, world_y):
        """Converts world coordinates to screen coordinates."""
        screen_x = (world_x * self.zoom_scale) + self.pan_offset_x
        screen_y = (world_y * self.zoom_scale) + self.pan_offset_y
        return screen_x, screen_y

    def screen_to_world(self, screen_x, screen_y):
        """Converts screen coordinates to world coordinates."""
        world_x = (screen_x - self.pan_offset_x) / self.zoom_scale
        world_y = (screen_y - self.pan_offset_y) / self.zoom_scale
        return world_x, world_y

    def redraw_all_zoomable(self):
        """Redraws all zoomable items based on the current camera view."""
        # Redraw all components that are meant to be zoomed/panned
        for comp in self.components.values():
            if "zoom_target" in self.canvas.gettags(comp.rect_id):
                # For components with an image, we need to resize the image itself
                # and then place it at the new screen coordinates.
                if comp.pil_image:
                    # Calculate the new screen dimensions based on world size and zoom
                    screen_w = (comp.world_x2 - comp.world_x1) * self.zoom_scale
                    screen_h = (comp.world_y2 - comp.world_y1) * self.zoom_scale

                    # --- PERFORMANCE FIX: Only regenerate image if size has changed ---
                    if screen_w > 0 and screen_h > 0 and (int(screen_w) != comp._cached_screen_w or int(screen_h) != comp._cached_screen_h):
                        comp._cached_screen_w = int(screen_w)
                        comp._cached_screen_h = int(screen_h)

                        # --- CRITICAL BUG FIX: Always resize from the CURRENT pil_image ---
                        # The pil_image holds the modified state (decals, etc.). The original_pil_image is only for resets.
                        source_img = comp.pil_image
                        if not source_img: continue # Should not happen if pil_image exists, but safe

                        resized_img = source_img.resize((comp._cached_screen_w, comp._cached_screen_h), Image.Resampling.LANCZOS)
                        comp.tk_image = ImageTk.PhotoImage(resized_img)
                        self.canvas.itemconfig(comp.rect_id, image=comp.tk_image)

                    # Always update coordinates, even if the image wasn't regenerated
                    sx1, sy1 = self.world_to_screen(comp.world_x1, comp.world_y1)
                    self.canvas.coords(comp.rect_id, sx1, sy1)

                # For placeholder components (rectangles with text)
                elif comp.text_id:
                    sx1, sy1 = self.world_to_screen(comp.world_x1, comp.world_y1)
                    sx2, sy2 = self.world_to_screen(comp.world_x2, comp.world_y2)
                    self.canvas.coords(comp.rect_id, sx1, sy1, sx2, sy2)
                    self.canvas.coords(comp.text_id, (sx1 + sx2) / 2, (sy1 + sy2) / 2)
        
        # Also redraw the paint layer if it exists
        if self.paint_layer_id:
            orig_w, orig_h = self.paint_layer_image.size
            new_w, new_h = int(orig_w * self.zoom_scale), int(orig_h * self.zoom_scale)
            if new_w > 0 and new_h > 0:
                resized_paint_img = self.paint_layer_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
                self.paint_layer_tk = ImageTk.PhotoImage(resized_paint_img)
                self.canvas.itemconfig(self.paint_layer_id, image=self.paint_layer_tk)
                self.canvas.coords(self.paint_layer_id, self.pan_offset_x, self.pan_offset_y)

    def on_zoom(self, event):
        """Handles zooming the canvas with Ctrl+MouseWheel."""
        if self.paint_mode_active or self.eraser_mode_active:
            self.toggle_paint_mode(tool='off')

        # --- REWRITTEN for Camera System ---
        mouse_world_x_before, mouse_world_y_before = self.screen_to_world(event.x, event.y)

        old_scale = self.zoom_scale
        factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_scale *= factor
        
        # Adjust pan offset to keep the point under the mouse stationary
        self.pan_offset_x = event.x - (mouse_world_x_before * self.zoom_scale)
        self.pan_offset_y = event.y - (mouse_world_y_before * self.zoom_scale)

        self._update_zoom_display()
        self._clamp_camera_pan() # Clamp the view after zooming
        self.redraw_all_zoomable()

    def zoom_in(self, event=None):
        """Zooms in on the center of the canvas."""
        x = self.canvas.winfo_width() / 2
        y = self.canvas.winfo_height() / 2
        center_world_x, center_world_y = self.screen_to_world(x, y)

        old_scale = self.zoom_scale
        factor = 1.1
        self.zoom_scale *= factor

        self.pan_offset_x = x - (center_world_x * self.zoom_scale)
        self.pan_offset_y = y - (center_world_y * self.zoom_scale)

        self._update_zoom_display()
        self._clamp_camera_pan() # Clamp the view after zooming
        self.redraw_all_zoomable()
        return "break" # Prevents the event from propagating

    def zoom_out(self, event=None):
        """Zooms out from the center of the canvas."""
        x = self.canvas.winfo_width() / 2
        y = self.canvas.winfo_height() / 2
        center_world_x, center_world_y = self.screen_to_world(x, y)

        old_scale = self.zoom_scale
        factor = 0.9
        self.zoom_scale *= factor

        self.pan_offset_x = x - (center_world_x * self.zoom_scale)
        self.pan_offset_y = y - (center_world_y * self.zoom_scale)

        self._update_zoom_display()
        self._clamp_camera_pan() # Clamp the view after zooming
        self.redraw_all_zoomable()
        return "break" # Prevents the event from propagating

    def _update_zoom_display(self):
        """Updates the zoom percentage label."""
        # Format the zoom scale as a percentage string
        zoom_percentage = f"{self.zoom_scale * 100:.0f}%"
        self.zoom_label_var.set(zoom_percentage)
        print(f"Zoom: {self.zoom_scale:.2f}x")

    def reset_view(self, event=None):
        """Resets the zoom to 100% and centers the pan."""
        self.zoom_scale = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self._update_zoom_display()
        self.redraw_all_zoomable()
        print("View has been reset.")

    def _clamp_camera_pan(self):
        """
        DEFINITIVE REWRITE V3: Prevents the user from panning the composition area off-screen.
        It ensures the edges of the composition area cannot go past the edges of the canvas.
        """
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        # Calculate the size of the composition area in screen pixels
        comp_screen_w = (self.COMP_AREA_X2 - self.COMP_AREA_X1) * self.zoom_scale
        comp_screen_h = (self.COMP_AREA_Y2 - self.COMP_AREA_Y1) * self.zoom_scale

        # Get the current screen coordinates of the top-left of the composition area
        comp_sx1, comp_sy1 = self.world_to_screen(self.COMP_AREA_X1, self.COMP_AREA_Y1)

        # Determine the valid range for the top-left corner's screen position.
        # The view's left edge cannot go past the canvas's left edge.
        # The view's right edge cannot go past the canvas's right edge.
        min_sx = min(0, canvas_w - comp_screen_w)
        max_sx = max(0, canvas_w - comp_screen_w)
        min_sy = min(0, canvas_h - comp_screen_h)
        max_sy = max(0, canvas_h - comp_screen_h)

        # Calculate the correction needed and apply it to the pan offset.
        self.pan_offset_x += max(min_sx, min(comp_sx1, max_sx)) - comp_sx1
        self.pan_offset_y += max(min_sy, min(comp_sy1, max_sy)) - comp_sy1

    def on_pan_press(self, event):
        """Records the starting position for panning."""
        # Stop painting if active
        if self.paint_mode_active or self.eraser_mode_active:
            self.toggle_paint_mode(tool='off')

        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self.canvas.config(cursor="fleur")

    def on_pan_drag(self, event):
        """Moves all items on the canvas to pan the view."""
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.pan_offset_x += dx
        self.pan_offset_y += dy
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self._clamp_camera_pan() # Clamp the view after panning
        self.redraw_all_zoomable()

    def on_pan_release(self, event):
        """Resets the cursor when panning is finished."""
        self.canvas.config(cursor="")

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
                if self.paint_layer_id:
                    self.canvas.itemconfig("paint_layer", state='normal')

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
        # This function now behaves identically to applying a regular decal.
        # It finds the topmost active image (of any type) and stamps it onto what's below.
        self.apply_decal_to_underlying_layer()


    def remove_border_from_selection(self):
        """Removes the border from the currently selected component."""
        # This function is no longer needed with the new workflow, but we keep the stub.
        messagebox.showinfo("Info", "To remove a border, simply re-apply the original image from the 'Image' tab or reset the layer.")


    def _keep_docks_on_top(self):
        """Iterates through all components and raises any dock assets to the top of the Z-order."""
        for comp in self.components.values():
            if comp.is_dock_asset:
                self.canvas.tag_raise(comp.tag)


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
        
        # Finally, ensure the dock assets are not obscured
        self._keep_docks_on_top()
    
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

        # Get all painted lines from the canvas
        paint_lines = self.canvas.find_withtag("paint_line")
        paint_layer = None
        if paint_lines:
            print(f"Found {len(paint_lines)} paint strokes to process.")
            paint_layer = Image.new("RGBA", (self.canvas.winfo_width(), self.canvas.winfo_height()), (0, 0, 0, 0))
            draw = ImageDraw.Draw(paint_layer)
            for line_id in paint_lines:
                coords = self.canvas.coords(line_id)
                options = self.canvas.itemcget(line_id, "fill")
                width = int(float(self.canvas.itemcget(line_id, "width")))
                for i in range(0, len(coords) - 2, 2):
                    draw.line(coords[i:i+4], fill=options, width=width, joint='curve')

        exported_count = 0
        for tag, comp in self.components.items():
            # --- FIX: Skip dock assets and their clones during export ---
            if not comp.pil_image or comp.is_dock_asset or tag.startswith("clone_"):
                continue


            # Start with the component's current image (which may have decals)
            final_image = comp.pil_image.copy()
            has_paint = False

            if paint_layer:
                bbox = self.canvas.bbox(comp.rect_id)
                if bbox:
                    cropped_paint = paint_layer.crop(bbox)
                    resized_paint = cropped_paint.resize(final_image.size, Image.Resampling.LANCZOS)
                    # Composite paint only if there's something to composite
                    if resized_paint.getbbox():
                        final_image = Image.alpha_composite(final_image, resized_paint)
                        has_paint = True

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

    def paint_on_canvas(self, event):
        """Draws on the dedicated paint layer image."""
        is_painting = self.paint_mode_active or self.eraser_mode_active
        if not is_painting or not self.paint_layer_image:
            return
    
        # Convert screen event coordinates to world coordinates for drawing
        world_x, world_y = self.screen_to_world(event.x, event.y)

        # --- NEW: Save state before drawing the first point of a new line ---
        if self.last_paint_x is None and self.last_paint_y is None:
            self._save_undo_state(self.paint_layer_image.copy())

        if self.last_paint_x and self.last_paint_y:
            last_world_x, last_world_y = self.screen_to_world(self.last_paint_x, self.last_paint_y)
            # --- NEW: Determine color based on tool ---
            paint_color = (0, 0, 0, 0) if self.eraser_mode_active else self.paint_color

            # Get the ImageDraw object for our paint layer
            draw = ImageDraw.Draw(self.paint_layer_image)
            draw.line(
                (last_world_x, last_world_y, world_x, world_y),
                fill=paint_color,
                width=self.brush_size.get(),
                joint='curve' # Creates smoother connections between line segments
            )
            # --- IMPORTANT: Update the canvas to show the change ---
            self._update_paint_layer_display()
    
        # Store the raw screen coordinates for the next event
        self.last_paint_x, self.last_paint_y = event.x, event.y

    def reset_paint_line(self, event):
        """Resets the start of the line when the mouse is released."""
        self.last_paint_x, self.last_paint_y = None, None

    def _update_paint_layer_display(self):
        """Updates the PhotoImage on the canvas to reflect changes to the PIL image."""
        # This is now part of the main redraw loop to handle scaling correctly.
        # We just need to trigger a redraw.
        self.redraw_all_zoomable()

    def _create_and_place_clone(self, asset_comp, event, clone_tag):
        """Helper to create, configure, and place a clone component."""
        w, h = asset_comp.original_pil_image.size
        world_x, world_y = self.screen_to_world(event.x, event.y)
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
        world_x, world_y = self.screen_to_world(event.x, event.y)
        w, h = asset_comp.original_pil_image.size
        clone_comp = DraggableComponent(self.canvas, self, clone_tag, world_x - w/2, world_y - h/2, world_x + w/2, world_y + h/2, "green", clone_tag)
        
        # --- FIX: Carry over the border flag to the clone ---
        clone_comp.is_border_asset = asset_comp.is_border_asset

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

        # --- Crucially, initiate a "drag" on the new clone immediately ---
        clone_comp.on_press(event) # This sets up the drag state for the clone
        clone_comp.on_drag(event)  # This starts the drag immediately

        # --- FIX: Ensure the dock itself remains on top after creating a clone ---
        self._keep_docks_on_top()

        print(f"Created clone '{clone_tag}' from asset '{asset_comp.tag}'.")

    def load_border_to_dock(self):
        """Loads a border image to the asset dock, marking it specifically as a border."""
        self._load_asset_to_dock_generic(is_border=True)

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

            # --- MODIFIED: Define position in the correct dock ---
            if is_border:
                x = self.next_border_dock_x
                y = self.BORDER_DOCK_Y + 20
                self.next_border_dock_x += self.DOCK_ASSET_SIZE[0] + 20
            else:
                x = self.next_image_dock_x
                y = self.IMAGE_DOCK_Y + 20
                self.next_image_dock_x += self.DOCK_ASSET_SIZE[0] + 20

            # Create a new DraggableComponent for the asset
            asset_comp = DraggableComponent(self.canvas, self, asset_tag, x, y, x + self.DOCK_ASSET_SIZE[0], y + self.DOCK_ASSET_SIZE[1], "blue", "ASSET")
            asset_comp.is_dock_asset = True # Mark it as a dock asset
            asset_comp.is_border_asset = is_border # NEW: Mark if it's a border

            # Store both the original and a preview version
            asset_comp.original_pil_image = full_res_image
            asset_comp.preview_pil_image = full_res_image.copy()
            asset_comp.preview_pil_image.thumbnail(self.DOCK_ASSET_SIZE, Image.Resampling.LANCZOS)
            
            # Set the image, which will use the preview because `is_dock_asset` is true
            asset_comp._set_pil_image(asset_comp.preview_pil_image, resize_to_fit=True)

            # Add to our list of assets and update the next position
            self.components[asset_tag] = asset_comp # Add to main components list
            self.dock_assets.append(asset_comp) # Also add to the specific dock asset list
            
            # Ensure the new dock asset is on top
            self._keep_docks_on_top()

            print(f"{asset_type} '{os.path.basename(image_path)}' loaded into dock.")

        except Exception as e:
            messagebox.showerror(f"{asset_type} Load Error", f"Could not load {asset_type.lower()} image: {e}")


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

                # --- CRITICAL FIX: Resize the cropped stamp to match the target's image scale ---
                final_stamp_w = int(cropped_stamp.width * scale_x)
                final_stamp_h = int(cropped_stamp.height * scale_y)
                if final_stamp_w > 0 and final_stamp_h > 0:
                    cropped_stamp = cropped_stamp.resize((final_stamp_w, final_stamp_h), Image.Resampling.LANCZOS)

                # 7. Composite the images.
                # Start with a copy of the target's current image.
                final_image = target_comp.pil_image.copy()
                
                # --- BUG FIX: Use the correct size for the decal layer ---
                decal_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
                # Paste the cropped stamp onto this layer at the correct position.
                decal_layer.paste(cropped_stamp, (paste_x, paste_y), cropped_stamp)

                # Conditionally respect transparency of the underlying tile
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

    def schedule_transform_update(self, event=None):
        """Schedules a decal transformation update, debouncing slider events."""
        # Cancel any previously scheduled update
        if self.transform_job:
            self.master.after_cancel(self.transform_job)
        
        # Schedule the actual update to run after 150ms of inactivity
        self.transform_job = self.master.after(150, self._update_active_decal_transform)

    def _update_active_decal_transform(self, event=None, use_fast_preview=False):
        """Applies both resize and rotation transformations to the active decal."""
        # Debounce the high-quality update
        if self.transform_job:
            self.master.after_cancel(self.transform_job)
        if use_fast_preview:
            # If we're just dragging, schedule a high-quality render for when we stop.
            self.transform_job = self.master.after(250, self._update_active_decal_transform)

        decal = self._find_topmost_stamp_source(show_warning=False, clone_type='any')
        if not decal or not decal.original_pil_image:
            return

        scale_factor = self.decal_scale.get() / 100.0
        rotation_angle = self.decal_rotation.get()

        # 1. Scale the original image
        original_w, original_h = decal.original_pil_image.size
        new_w = int(original_w * scale_factor)
        new_h = int(original_h * scale_factor)

        if new_w > 0 and new_h > 0:
            # Use a faster algorithm for live preview, and a high-quality one for the final render.
            resample_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.LANCZOS
            rotate_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.BICUBIC

            resized_image = decal.original_pil_image.resize((new_w, new_h), resample_quality)

            # 2. Rotate the scaled image
            # Use expand=True to prevent corners from being clipped.
            # The background is transparent, so this is safe.
            rotated_image = resized_image.rotate(rotation_angle, expand=True, resample=rotate_quality)

            # 3. Create the semi-transparent version for display
            alpha = rotated_image.getchannel('A')
            semi_transparent_alpha = Image.eval(alpha, lambda a: a // 2)
            display_image = rotated_image.copy()
            display_image.putalpha(semi_transparent_alpha)

            # 4. Update the component on the canvas
            decal._set_pil_image(display_image, resize_to_fit=False)

    def discard_active_image(self):
        """Finds and removes the top-most draggable image (decal or clone) without applying it."""
        image_to_discard = self._find_topmost_stamp_source(clone_type='any')
        if not image_to_discard:
            # The helper function already shows a warning if nothing is found.
            return

        self._remove_stamp_source_component(image_to_discard)
        print(f"Discarded image '{image_to_discard.tag}'.")

    def _find_topmost_stamp_source(self, show_warning=True, clone_type: str = 'clone'):
        """
        Finds the top-most draggable image (decal or clone) that can be used for stamping.
        clone_type can be 'clone', 'border', or 'any'.
        """
        prefix = f"{clone_type}_"
        all_items = self.canvas.find_all()
        # Iterate from the top of the stack downwards
        for item_id in reversed(all_items):
            tags = self.canvas.gettags(item_id)
            if not tags:
                continue
            
            tag = tags[0]
            if tag in self.components:
                comp = self.components[tag]
                # Check if it's a draggable image but NOT a dock asset
                if comp.is_draggable and comp.pil_image and not comp.is_dock_asset:
                    if clone_type == 'any' and (tag.startswith('clone_') or tag.startswith('border_')):
                        return comp
                    if tag.startswith(prefix):
                        return comp
        
        # If the loop finishes without finding anything
        if show_warning:
            messagebox.showwarning("No Image Found", f"Could not find an active '{clone_type}' image to apply or discard.")
        return None
    
    def _remove_stamp_source_component(self, comp_to_remove):
        """Helper function to cleanly remove a stamp source (decal/clone) from the canvas and component list."""
        if not comp_to_remove:
            return
        
        self.canvas.delete(comp_to_remove.tag)
        if comp_to_remove.tag in self.components:
            del self.components[comp_to_remove.tag]
        
        if comp_to_remove == self.active_decal:
            self.active_decal = None


# --- EXECUTION ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageEditorApp(root)
    try:
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Application Error", f"An error occurred: {e}")