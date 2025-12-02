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
        self.original_pil_image = None # NEW: For storing the pristine decal image
        self.rect_id = None
        self.text_id = None
        self.is_draggable = True # Control whether the component can be dragged
        self.is_decal = False # NEW: To identify temporary decals
        
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
                                                     width=2,
                                                     tags=(self.tag, "draggable"))
        
        self.text_id = self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, 
                                              text=text, 
                                              fill="white", 
                                              font=("Inter", 16, "bold"), # Increased font size
                                              tags=(self.tag, "draggable"))
        
        # Update bounding box of the component
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2

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

        # Get the current size and position of the component for resizing
        current_bbox = self.canvas.bbox(self.rect_id)
        if not current_bbox: # Fallback if bbox is not available
            x_start, y_start, w, h = self.x1, self.y1, self.x2 - self.x1, self.y2 - self.y1
        else:
            x_start, y_start, _, _ = current_bbox

        if resize_to_fit:
            # Resize the PIL image to fit the current component size
            # For dock assets, use the specific preview image
            image_to_render = self.preview_pil_image if self.is_dock_asset else self.pil_image
            w, h = int(self.x2 - self.x1), int(self.y2 - self.y1)
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

        # Must store a reference to avoid garbage collection
        self.tk_image = new_tk_image


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
                alpha = self.preview_pil_image.getpixel((rel_x, rel_y))[3]
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

        dx = event.x - self.last_x
        dy = event.y - self.last_y
        
        # Move the item by the calculated distance
        self.canvas.move(self.rect_id, dx, dy)
        if self.text_id:
            self.canvas.move(self.text_id, dx, dy)
        
        # Update the last mouse position for the next movement calculation
        self.last_x = event.x
        self.last_y = event.y

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
        master.title("Interactive Layer Compositor (Expanded)")
        self.selected_component_tag = None
        
        # --- NEW: Painting Feature State ---
        self.resize_width = tk.StringVar()
        self.resize_height = tk.StringVar()
        self.maintain_aspect = tk.BooleanVar(value=True)
        self.resize_width.trace_add("write", self.on_resize_entry_change)
        self.resize_height.trace_add("write", self.on_resize_entry_change)

        self.paint_mode_active = False
        self.paint_color = "red"
        self.brush_size = tk.IntVar(value=4)
        self.last_paint_x, self.last_paint_y = None, None
        
        # --- NEW: Decal Feature State ---
        self.active_decal = None
        self.decal_scale = tk.DoubleVar(value=100) # For the resize slider

        # --- NEW: Asset Dock State ---
        self.dock_assets = []
        self.next_dynamic_id = 0 # FIX: Unified counter for clones and assets
        self.next_dock_x = 20
        self.DOCK_Y_POSITION = 650
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
        # Use grid to place the canvas in the first column
        self.canvas.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1) 
        self.main_frame.grid_rowconfigure(0, weight=1)
        
        # Bind painting events directly to the canvas
        self.canvas.bind("<B1-Motion>", self.paint_on_canvas)
        self.canvas.bind("<ButtonRelease-1>", self.reset_paint_line)
        
        # --- PREVIEW LAYOUT COORDINATES ---
        self.preview_layout = {
            "humanuitile01": {"coords": [259, 57, 511, 359]},
            "humanuitile02": {"coords": [511, 57, 763, 359]},
            "humanuitile03": {"coords": [763, 57, 1015, 359]},
            "humanuitile04": {"coords": [887, 57, 1139, 359]},
            "humanuitile05": {"coords": [7, 57, 259, 359]},
            "humanuitile06": {"coords": [1139, 57, 1391, 359]},
            "humanuitile-inventorycover": {"coords": [728, 57, 850, 359]},
            "humanuitile-timeindicatorframe": {"coords": [585, 57, 722, 134]}
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

        # Draw a placeholder for the main template background
        self.canvas.create_rectangle(0, 50, 1407, 400, # Final position adjustment
                                     fill="#374151", # Slightly lighter than canvas bg
                                     outline="#4b5563",
                                     width=3)

        # --- NEW: Draw the Asset Dock Area ---
        self.canvas.create_text(CANVAS_WIDTH/2, self.DOCK_Y_POSITION - 20, text="ASSET DOCK (Load images here and drag them into the composition)", fill="#9ca3af", font=("Inter", 12))
        self.canvas.create_rectangle(0, self.DOCK_Y_POSITION, CANVAS_WIDTH, CANVAS_HEIGHT,
                                     fill="#374151", # Match composition area
                                     outline="#4b5563",
                                     width=3)

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
            950, 50, 1200, 350, 
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
        self.sidebar_frame.grid(row=0, column=1, sticky="nswe")
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
        resize_tab = tk.Frame(notebook, bg="#374151") # NEW
        text_tab = tk.Frame(notebook, bg="#374151") # NEW
        export_tab = tk.Frame(notebook, bg="#374151")

        notebook.add(layer_tab, text='Tiles')
        notebook.add(paint_tab, text='Paint')
        notebook.add(image_tab, text='Image')
        notebook.add(resize_tab, text='Resize') # NEW
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
                                          command=self.toggle_paint_mode)
        self.paint_toggle_btn.pack(fill='x', expand=True)
        color_btn = tk.Button(paint_frame, text="Choose Color", bg='#6b7280', fg='white', relief='flat', font=('Inter', 10),
                              command=self.choose_paint_color)
        color_btn.pack(fill='x', expand=True, pady=(5,0))
        brush_size_frame = tk.Frame(paint_frame, bg="#374151")
        brush_size_frame.pack(fill='x', pady=5)
        tk.Label(brush_size_frame, text="Size:", bg="#374151", fg="white").pack(side=tk.LEFT)
        tk.Scale(brush_size_frame, from_=1, to=50, orient=tk.HORIZONTAL, variable=self.brush_size, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0).pack(side=tk.LEFT, expand=True)
        clear_paint_btn = tk.Button(paint_frame, text="Clear All Paintings", bg='#ef4444', fg='white', relief='flat', font=('Inter', 10),
                                    command=self.clear_paintings)
        clear_paint_btn.pack(fill='x', expand=True, pady=(5,0))

        tk.Label(image_tab, text="ASSET CONTROLS", **label_style).pack(fill='x', pady=(10,0))
        tk.Button(image_tab, text="Load Asset to Dock", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.load_asset_to_dock).pack(fill='x', padx=10, pady=(5,10))
        # --- NEW: Decal Resizing Controls ---
        resize_frame = tk.Frame(image_tab, bg="#374151")
        resize_frame.pack(fill='x', padx=10, pady=5)
        tk.Label(resize_frame, text="Resize:", bg="#374151", fg="white").pack(side=tk.LEFT)
        tk.Scale(resize_frame, from_=10, to=200, orient=tk.HORIZONTAL, variable=self.decal_scale,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0, command=self.resize_active_decal).pack(side=tk.LEFT, expand=True)
        tk.Button(resize_frame, text="Reset", bg='#6b7280', fg='white', relief='flat', font=('Inter', 8),
                  command=lambda: self.decal_scale.set(100) or self.resize_active_decal()).pack(side=tk.LEFT, padx=(5,0))


        tk.Button(image_tab, text="Apply Image", bg='#10b981', fg='white', relief='flat', font=button_font,
                  command=self.apply_decal_to_underlying_layer).pack(fill='x', padx=10, pady=(10,2))
        
        # --- Populate the "Resize" Tab ---
        tk.Label(resize_tab, text="RESIZE SELECTED TILE", **label_style).pack(fill='x')
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


    def toggle_paint_mode(self):
        """Toggles the painting mode on or off."""
        self.paint_mode_active = not self.paint_mode_active
        if self.paint_mode_active:
            self.paint_toggle_btn.config(text="Disable Paint Mode", bg='#ef4444', relief='sunken')
            # Disable dragging for all components
            for comp in self.components.values():
                comp.is_draggable = False
            print("Paint mode ENABLED. Component dragging is disabled.")
        else:
            self.paint_toggle_btn.config(text="Enable Paint Mode", bg='#d97706', relief='flat')
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
        self.canvas.delete("paint_line")
        print("All paintings have been cleared.")


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
                # Also ensure any drawn paint lines are visible
                self.canvas.itemconfig("paint_line", state='normal')

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
        if bbox:
            width = int(bbox[2] - bbox[0])
            height = int(bbox[3] - bbox[1])
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
        comp.x2 = comp.x1 + new_w
        comp.y2 = comp.y1 + new_h

        # If the component has an image, re-apply it to trigger the resize.
        # Otherwise, redraw the placeholder rectangle.
        if comp.pil_image:
            comp._set_pil_image(comp.pil_image, resize_to_fit=True)
        else:
            comp._draw_placeholder(comp.x1, comp.y1, comp.x2, comp.y2, comp.canvas.itemcget(comp.rect_id, "fill"), comp.canvas.itemcget(comp.text_id, "text"))
        print(f"Resized '{comp.tag}' to {new_w}x{new_h}.")


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

                current_x1, current_y1, _, _ = current_bbox
                
                dx = target_x1 - current_x1
                dy = target_y1 - current_y1
                
                self.canvas.move(comp.rect_id, dx, dy)
                if comp.text_id:
                    self.canvas.move(comp.text_id, dx, dy)
            
            # 3. Reset placeholder borders
            if comp.tk_image is None:
                self.canvas.itemconfig(comp.rect_id, outline='white', width=2)
        
        # Finally, ensure the dock assets are not obscured
        self._keep_docks_on_top()
    
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
        """Draws a line on the canvas if paint mode is active."""
        if not self.paint_mode_active:
            return # Do nothing if we are not in paint mode

        if self.last_paint_x and self.last_paint_y:
            self.canvas.create_line(
                self.last_paint_x, self.last_paint_y, 
                event.x, event.y,
                width=self.brush_size.get(),
                fill=self.paint_color,
                capstyle=tk.ROUND, 
                smooth=tk.TRUE,
                tags="paint_line" # Tag for easy clearing
            )
        self.last_paint_x, self.last_paint_y = event.x, event.y

    def reset_paint_line(self, event):
        """Resets the start of the line when the mouse is released."""
        self.last_paint_x, self.last_paint_y = None, None

    def reset_selected_layer(self):
        """Resets the currently selected layer to its original, unmodified image."""
        if not self.selected_component_tag:
            messagebox.showwarning("Selection Required", "Please select a component layer to reset.")
            return

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

        # --- NEW: Ensure only one active image exists at a time ---
        existing_active_image = self._find_topmost_stamp_source(show_warning=False)
        if existing_active_image:
            self._remove_stamp_source_component(existing_active_image)

        # Create a unique tag for the new component
        clone_tag = f"clone_{self.next_dynamic_id}"
        self.next_dynamic_id += 1
        
        # Get the original image size to create the new component's bounds
        w, h = asset_comp.original_pil_image.size
        
        # --- NEW: Position the new clone in the center of the canvas ---
        x = (self.canvas.winfo_width() / 2) - (w / 2)
        y = (self.canvas.winfo_height() / 2) - (h / 2)

        # Create the new component instance
        clone_comp = DraggableComponent(self.canvas, self, clone_tag, x, y, x + w, y + h, "green", clone_tag)
        
        # --- FIX: Apply semi-transparency to the clone for visual feedback ---
        # 1. Set the clone's original image to the full-resolution one for stamping.
        clone_comp.original_pil_image = asset_comp.original_pil_image
        
        # 2. Create a semi-transparent version for display while dragging.
        display_image = asset_comp.original_pil_image.copy()
        display_image.putalpha(Image.eval(display_image.getchannel('A'), lambda a: a // 2))

        # 3. Set the clone's display image.
        clone_comp._set_pil_image(display_image, resize_to_fit=False)
        # Add the new clone to the main components dictionary
        self.components[clone_tag] = clone_comp

        # --- Crucially, initiate a "drag" on the new clone immediately ---
        clone_comp.on_press(event) # This sets up the drag state for the clone
        clone_comp.on_drag(event)  # This starts the drag immediately

        # --- FIX: Ensure the dock itself remains on top after creating a clone ---
        self._keep_docks_on_top()

        print(f"Created clone '{clone_tag}' from asset '{asset_comp.tag}'.")

    def load_asset_to_dock(self):
        """Loads an image, scales it, and places it in the asset dock as a new draggable component."""
        image_path = filedialog.askopenfilename(
            title="Select Asset Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif")],
            initialdir=self.image_base_dir # Start in the new images directory
        )
        if not image_path:
            return

        try:
            # Load the image
            full_res_image = Image.open(image_path).convert("RGBA")

            # Create a unique tag for the new asset
            asset_tag = f"dock_asset_{self.next_dynamic_id}"
            self.next_dynamic_id += 1

            # Define position in the dock
            x = self.next_dock_x
            y = self.DOCK_Y_POSITION + 20
            
            # Create a new DraggableComponent for the asset
            asset_comp = DraggableComponent(self.canvas, self, asset_tag, x, y, x + self.DOCK_ASSET_SIZE[0], y + self.DOCK_ASSET_SIZE[1], "blue", "ASSET")
            asset_comp.is_dock_asset = True # Mark it as a dock asset

            # Store both the original and a preview version
            asset_comp.original_pil_image = full_res_image
            asset_comp.preview_pil_image = full_res_image.copy()
            asset_comp.preview_pil_image.thumbnail(self.DOCK_ASSET_SIZE, Image.Resampling.LANCZOS)
            
            # Set the image, which will use the preview because `is_dock_asset` is true
            asset_comp._set_pil_image(asset_comp.preview_pil_image, resize_to_fit=True)

            # Add to our list of assets and update the next position
            self.components[asset_tag] = asset_comp # Add to main components list
            self.dock_assets.append(asset_comp) # Also add to the specific dock asset list
            self.next_dock_x += self.DOCK_ASSET_SIZE[0] + 20 # Add padding
            
            # Ensure the new dock asset is on top
            self._keep_docks_on_top()

            print(f"Asset '{os.path.basename(image_path)}' loaded into dock.")

        except Exception as e:
            messagebox.showerror("Asset Load Error", f"Could not load asset image: {e}")


    def apply_decal_to_underlying_layer(self):
        """
        Finds the top-most draggable image (decal or clone) and stamps it onto all layers underneath.
        """
        # --- REFACTOR: Use the helper function to find the source image ---
        stamp_source_comp = self._find_topmost_stamp_source()
        
        if not stamp_source_comp:
            # The helper function now shows its own warning.
            # messagebox.showwarning("No Stamp Source", "Could not find a draggable image (decal or cloned asset) at the top of the layer stack to apply.")
            return

        stamp_bbox = self.canvas.bbox(stamp_source_comp.rect_id)
        if not stamp_bbox: return

        # Find all canvas items that overlap with the decal's bounding box
        overlapping_ids = self.canvas.find_overlapping(*stamp_bbox)
        
        # --- FIX: Use the original, full-resolution image for stamping ---
        # Resize it to match the current on-screen size of the stamp source.
        stamp_w = int(stamp_bbox[2] - stamp_bbox[0])
        stamp_h = int(stamp_bbox[3] - stamp_bbox[1])
        decal_stamp_image = stamp_source_comp.original_pil_image.resize((stamp_w, stamp_h), Image.Resampling.LANCZOS)


        applied_count = 0
        for item_id in overlapping_ids:
            tags = self.canvas.gettags(item_id)
            if not tags or tags[0] == stamp_source_comp.tag:
                continue # Skip if no tags or if it's the stamp source itself

            comp_tag = tags[0]
            if comp_tag in self.components:
                target_comp = self.components[comp_tag]
                if not target_comp.original_pil_image: continue

                comp_bbox = self.canvas.bbox(target_comp.rect_id)
                if not comp_bbox: continue

                # 1. Create a new composite image based on the component's current state
                # IMPORTANT: Start with a copy of the CURRENT pil_image, not the original one.
                new_comp_image = target_comp.pil_image.copy()

                # 2. Calculate the intersection area on the canvas
                intersect_x1 = max(stamp_bbox[0], comp_bbox[0])
                intersect_y1 = max(stamp_bbox[1], comp_bbox[1])
                intersect_x2 = min(stamp_bbox[2], comp_bbox[2])
                intersect_y2 = min(stamp_bbox[3], comp_bbox[3])

                # 3. Crop the part of the decal that's in the intersection
                decal_crop_x1 = intersect_x1 - stamp_bbox[0]
                decal_crop_y1 = intersect_y1 - stamp_bbox[1]
                decal_crop_x2 = intersect_x2 - stamp_bbox[0]
                decal_crop_y2 = intersect_y2 - stamp_bbox[1]
                cropped_decal = decal_stamp_image.crop((decal_crop_x1, decal_crop_y1, decal_crop_x2, decal_crop_y2))

                # 4. Correctly calculate where to paste the cropped decal onto the component's image
                # This involves scaling from canvas coordinates to the original image's pixel coordinates.
                comp_canvas_w = comp_bbox[2] - comp_bbox[0]
                comp_canvas_h = comp_bbox[3] - comp_bbox[1]
                
                # Avoid division by zero if a component has no size
                if comp_canvas_w == 0 or comp_canvas_h == 0: continue

                scale_x = new_comp_image.width / comp_canvas_w
                scale_y = new_comp_image.height / comp_canvas_h

                paste_x = int((intersect_x1 - comp_bbox[0]) * scale_x)
                paste_y = int((intersect_y1 - comp_bbox[1]) * scale_y)
                
                final_decal_w, final_decal_h = int(cropped_decal.width * scale_x), int(cropped_decal.height * scale_y)
                resized_cropped_decal = cropped_decal.resize((final_decal_w, final_decal_h), Image.Resampling.LANCZOS)

                # 5. --- MODIFIED: Use alpha_composite for correct layering ---
                # Create a new transparent image the same size as the component image.
                # This will serve as the layer for our decal.
                decal_layer = Image.new("RGBA", new_comp_image.size, (0, 0, 0, 0))
                
                # Paste the resized decal onto this new transparent layer.
                decal_layer.paste(resized_cropped_decal, (paste_x, paste_y), resized_cropped_decal)

                # --- FIX 2.0: Combine alpha channels instead of replacing them ---
                # This prevents black cutouts by ensuring the decal is only visible where BOTH
                # the decal itself has alpha AND the original component has alpha.
                comp_alpha_mask = target_comp.original_pil_image.getchannel('A')
                combined_alpha = ImageChops.multiply(decal_layer.getchannel('A'), comp_alpha_mask)
                decal_layer.putalpha(combined_alpha)

                # 6. Composite the decal layer onto the component's image.
                final_image = Image.alpha_composite(new_comp_image, decal_layer)

                target_comp._set_pil_image(final_image)
                applied_count += 1
                print(f"Stamped decal onto layer '{target_comp.tag}'.")

        if applied_count == 0:
            messagebox.showwarning("No Target", "Decal must be positioned over a valid layer to be applied.")
            return

        self._remove_stamp_source_component(stamp_source_comp)

    def resize_active_decal(self, event=None):
        """Resizes the active image (clone) based on the slider value."""
        # --- FIX: Find the currently active image instead of relying on self.active_decal ---
        decal = self._find_topmost_stamp_source(show_warning=False)

        if not decal or not decal.original_pil_image:
            # Silently return if there's no active image to resize.
            return

        scale_factor = self.decal_scale.get() / 100.0
        original_w, original_h = decal.original_pil_image.size
        new_w = int(original_w * scale_factor)
        new_h = int(original_h * scale_factor)
        
        if new_w > 0 and new_h > 0:
            # Always resize from the original image to maintain quality
            resized_image = decal.original_pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Create the semi-transparent version for display
            alpha = resized_image.getchannel('A')
            semi_transparent_alpha = Image.eval(alpha, lambda a: a // 2)
            display_image = resized_image.copy()
            display_image.putalpha(semi_transparent_alpha)
            
            decal._set_pil_image(display_image, resize_to_fit=False)

    def discard_active_image(self):
        """Finds and removes the top-most draggable image (decal or clone) without applying it."""
        image_to_discard = self._find_topmost_stamp_source()
        if not image_to_discard:
            # The helper function already shows a warning if nothing is found.
            return

        self._remove_stamp_source_component(image_to_discard)
        print(f"Discarded image '{image_to_discard.tag}'.")

    def _find_topmost_stamp_source(self, show_warning=True):
        """
        Finds the top-most draggable image (decal or clone) that can be used for stamping.
        This is a helper function to avoid code duplication.
        """
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
                # --- FIX: Only consider 'clones' as stamp sources ---
                if comp.is_draggable and comp.pil_image and not comp.is_dock_asset and tag.startswith("clone_"):
                    return comp
        
        # If the loop finishes without finding anything
        if show_warning:
            messagebox.showwarning("No Image Found", "Could not find a draggable image (decal or clone) to apply or discard.")
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
    try:
        root = tk.Tk()
        app = ImageEditorApp(root)

        # --- FIX: Move button creation here to ensure `app` exists ---
        # Find the 'Image' tab in the notebook
        image_tab = app.sidebar_frame.winfo_children()[0].tabs()[2]
        image_tab_frame = app.sidebar_frame.winfo_children()[0].nametowidget(image_tab)

        tk.Button(image_tab_frame, text="Discard Image", bg='#ef4444', fg='white', relief='flat', font=('Inter', 11, 'bold'),
                  command=app.discard_active_image).pack(fill='x', padx=10, pady=(2,10))
        tk.Label(image_tab_frame, text="1. Load an asset to the dock.\n2. Click it to create an active image.\n3. Drag, resize, and 'Apply' or 'Discard'.",
                 bg="#374151", fg="#9ca3af", justify=tk.LEFT, padx=10).pack(fill='x', pady=(10,0))

        root.mainloop()
    except Exception as e:
        messagebox.showerror("Application Error", f"An error occurred: {e}")