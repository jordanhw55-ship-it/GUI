import tkinter as tk
from tkinter import ttk

class UIManager:
    """Manages the creation and layout of the Tkinter UI widgets."""
    def __init__(self, app):
        self.app = app
        self.master = app.master
        self.sidebar_frame = None
        self.image_dock_canvas = None
        self.border_dock_canvas = None
        self.paint_color_button = None
        self.border_preview_canvas = None # NEW: For smart border preview
        self.paint_toggle_btn = None
        self.eraser_toggle_btn = None
        self.border_tab = None # NEW: To hold a reference to the border tab widget
        self.smart_border_btn = None # NEW: For the smart border tool
        self.notebook = None # NEW: To hold a reference to the main notebook

    def create_canvas(self):
        """Creates the main canvas and returns it."""
        self.app.main_frame = tk.Frame(self.master, padx=10, pady=10, bg="#1f2937")
        self.app.main_frame.pack(fill="both", expand=True)

        self.app.canvas = tk.Canvas(self.app.main_frame, 
                                 width=self.app.CANVAS_WIDTH, 
                                 height=self.app.CANVAS_HEIGHT, 
                                 bg="#2d3748",
                                 highlightthickness=0)
        self.app.canvas.grid(row=0, column=0, padx=(0, 10), sticky="nsew", rowspan=2)
        self.app.main_frame.grid_columnconfigure(0, weight=1) 
        self.app.main_frame.grid_rowconfigure(0, weight=1)

        self.app.canvas.bind("<Configure>", self.app.on_canvas_resize)
        return self.app.canvas

    def bind_canvas_events(self):
        """Binds events that depend on other managers being initialized."""
        self.app.canvas.bind("<B1-Motion>", self.app.paint_manager.paint_on_canvas)
        self.app.canvas.bind("<ButtonRelease-1>", self.app.paint_manager.reset_paint_line)

    def create_ui(self):
        """Creates the rest of the UI that might depend on other components."""
        self.create_status_box()
        self.create_coordinate_display() # NEW: Add the coordinate display
        self.create_sidebar_tabs()

    def create_status_box(self):
        """Creates the floating status box in the top-left of the canvas."""
        status_box_frame = tk.Frame(self.app.canvas, bg="#1f2937", bd=1, relief="solid", highlightbackground="#4b5563", highlightthickness=1)
        
        self.app.undo_button = tk.Button(status_box_frame, text="Undo / Ctrl Z", bg='#4b5563', fg='white', relief='flat', font=('Inter', 10, 'bold'),
                                     command=self.app.undo_last_action, state='disabled', padx=5, pady=2)
        self.app.undo_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        zoom_label = tk.Label(status_box_frame, textvariable=self.app.camera.zoom_label_var, bg="#1f2937", fg="#d1d5db", font=('Inter', 10, 'bold'))
        zoom_label.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.app.reset_view_button = tk.Button(status_box_frame, text="Reset View", bg='#6b7280', fg='white', relief='flat', font=('Inter', 10, 'bold'),
                                           command=self.app.camera.reset_view, padx=5, pady=2)
        self.app.reset_view_button.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.app.canvas.create_window(10, 10, window=status_box_frame, anchor="nw")

    def create_coordinate_display(self):
        """Creates a floating box in the bottom-left to show mouse world coordinates."""
        coord_box_frame = tk.Frame(self.app.canvas, bg="#1f2937", bd=1, relief="solid", highlightbackground="#4b5563", highlightthickness=1)
        
        coord_label = tk.Label(coord_box_frame, textvariable=self.app.mouse_coords_var, bg="#1f2937", fg="#d1d5db", font=('Inter', 10, 'bold'))
        coord_label.pack(padx=5, pady=5)

        self.app.canvas.create_window(10, self.app.CANVAS_HEIGHT - 10, window=coord_box_frame, anchor="sw")

    def create_sidebar_tabs(self):
        """Creates a tabbed interface in the sidebar for organizing controls."""
        self.sidebar_frame = tk.Frame(self.app.main_frame, width=self.app.SIDEBAR_WIDTH, bg="#1f2937")
        self.sidebar_frame.grid(row=0, column=1, sticky="nswe", rowspan=2)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        ttk.Style().theme_use('clam')
        style = ttk.Style(self.master)
        style.configure('TNotebook', background="#1f2937", borderwidth=0)
        style.configure('TNotebook.Tab', font=('Inter', 11, 'bold'), padding=[15, 5], background="#374151", foreground="#d1d5db", borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#4b5563")], foreground=[("selected", "white")])

        self.notebook = ttk.Notebook(self.sidebar_frame, style='TNotebook')
        self.notebook.pack(expand=True, fill='both')
        # --- NEW: Bind an event to clear the border preview when changing main tabs ---
        # This ensures the preview disappears when you navigate away from the Border tab.
        self.notebook.bind("<<NotebookTabChanged>>", self.app.on_tab_changed)


        layer_tab = tk.Frame(self.notebook, bg="#374151")
        paint_tab = tk.Frame(self.notebook, bg="#374151")
        image_tab = tk.Frame(self.notebook, bg="#374151")
        filters_tab = tk.Frame(self.notebook, bg="#374151")
        self.border_tab = tk.Frame(self.notebook, bg="#374151") # Use the new instance variable
        tile_control_tab = tk.Frame(self.notebook, bg="#374151")
        text_tab = tk.Frame(self.notebook, bg="#374151")
        export_tab = tk.Frame(self.notebook, bg="#374151")

        self.notebook.add(layer_tab, text='Tiles')
        self.notebook.add(paint_tab, text='Paint')
        self.notebook.add(self.border_tab, text='Border')
        self.notebook.add(image_tab, text='Image')
        self.notebook.add(tile_control_tab, text='Tile Control')
        self.notebook.add(filters_tab, text='Filters')
        self.notebook.add(text_tab, text='Text')
        self.notebook.add(export_tab, text='Export')

        self._populate_layer_tab(layer_tab)
        self._populate_paint_tab(paint_tab)
        self._populate_image_tab(image_tab)
        self._populate_tile_control_tab(tile_control_tab)
        self._populate_border_tab(self.border_tab)
        self._populate_filters_tab(filters_tab)
        self._populate_text_tab(text_tab)
        self._populate_export_tab(export_tab)

    def _populate_layer_tab(self, tab):
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')
        tk.Label(tab, text="TILE SELECT", **label_style).pack(fill='x')
        
        for i, name in enumerate(self.app.component_list):
            btn = tk.Button(tab, text=name, bg='#4b5563' if name == "Show All" else '#6b7280', fg='white', relief='flat', pady=8, font=('Inter', 11),
                            command=lambda n=name: self.app.handle_tab_click(n))
            btn.pack(fill='x', padx=10, pady=(2 if i > 0 else 5))
        
        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)

        tk.Label(tab, text="TILE LOCATION PRESET", **label_style).pack(fill='x')
        layout_frame = tk.Frame(tab, bg="#374151")
        layout_frame.pack(fill='x', padx=10, pady=5)
        tk.Button(layout_frame, text="Save Layout", bg='#3b82f6', fg='white', relief='flat', font=button_font, command=self.app.save_layout).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        tk.Button(layout_frame, text="Load Layout", bg='#3b82f6', fg='white', relief='flat', font=button_font, command=self.app.load_layout).pack(side=tk.RIGHT, fill='x', expand=True, padx=(5, 0))
        tk.Button(tab, text="Default Layout", bg='#6b7280', fg='white', relief='flat', font=button_font, command=self.app.apply_preview_layout).pack(fill='x', padx=10, pady=5)
        
        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)
        
        tk.Label(tab, text="IMAGE SET", **label_style).pack(fill='x')
        if self.app.image_sets:
            image_set_menu = ttk.OptionMenu(tab, self.app.selected_image_set, self.app.image_sets[0], *self.app.image_sets)
            image_set_menu.pack(fill='x', padx=10, pady=5)
        else:
            tk.Label(tab, text="No image sets found in 'images' folder.", bg="#374151", fg="#9ca3af", padx=10).pack(fill='x')

    def _populate_paint_tab(self, tab):
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')
        tk.Label(tab, text="PAINTING TOOLS", **label_style).pack(fill='x')
        paint_frame = tk.Frame(tab, bg="#374151")
        paint_frame.pack(fill='x', padx=10, pady=5)
        self.paint_toggle_btn = tk.Button(paint_frame, text="Paint Brush", bg='#d97706', fg='white', relief='flat', font=button_font,
                                           command=lambda: self.app.paint_manager.toggle_paint_mode(tool='paint'))
        self.paint_toggle_btn.pack(fill='x', expand=True)

        self.eraser_toggle_btn = tk.Button(paint_frame, text="Transparency Brush", bg='#0e7490', fg='white', relief='flat', font=button_font,
                                            command=lambda: self.app.paint_manager.toggle_paint_mode(tool='eraser'))
        self.eraser_toggle_btn.pack(fill='x', expand=True, pady=(5,0))

        self.tile_eraser_btn = tk.Button(paint_frame, text="Tile Eraser", bg='#991b1b', fg='white', relief='flat', font=button_font,
                                           command=lambda: self.app.toggle_tile_eraser_mode())
        self.tile_eraser_btn.pack(fill='x', expand=True, pady=(5,0))

        self.universal_eraser_btn = tk.Button(paint_frame, text="Universal Eraser", bg='#be123c', fg='white', relief='flat', font=button_font,
                                           command=lambda: self.app.paint_manager.toggle_paint_mode(tool='universal_eraser'))
        self.universal_eraser_btn.pack(fill='x', expand=True, pady=(5,0))

        tk.Frame(paint_frame, height=2, bg="#6b7280").pack(fill='x', pady=10)

        self.paint_color_button = tk.Button(paint_frame, text="Choose Color", bg='#6b7280', fg='white', relief='flat', font=('Inter', 10),
                               command=self.app.paint_manager.choose_paint_color, state='disabled')
        self.paint_color_button.pack(fill='x', expand=True, pady=(5,0))
        brush_size_frame = tk.Frame(paint_frame, bg="#374151")
        brush_size_frame.pack(fill='x', pady=5)
        tk.Label(brush_size_frame, text="Size:", bg="#374151", fg="white").pack(side=tk.LEFT)
        tk.Scale(brush_size_frame, from_=1, to=50, orient=tk.HORIZONTAL, variable=self.app.paint_manager.brush_size, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0).pack(side=tk.LEFT, expand=True)
        clear_paint_btn = tk.Button(paint_frame, text="Clear All Paintings", bg='#ef4444', fg='white', relief='flat', font=('Inter', 10),
                                     command=self.app.paint_manager.clear_paintings)
        clear_paint_btn.pack(fill='x', expand=True, pady=(5,0))

    def _populate_image_tab(self, tab):
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')
        tk.Label(tab, text="ASSET & DECAL CONTROLS", **label_style).pack(fill='x', pady=(10,0))
        tk.Button(tab, text="Load Asset to Dock", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.app.image_manager.load_asset_to_dock).pack(fill='x', padx=10, pady=(5,10))

        image_dock_frame = tk.Frame(tab, bg="#2d3748", bd=2, relief="sunken")
        image_dock_frame.pack(fill='both', expand=True, padx=10, pady=5)
        image_dock_frame.grid_rowconfigure(0, weight=1)
        image_dock_frame.grid_columnconfigure(0, weight=1)
        self.image_dock_canvas = tk.Canvas(image_dock_frame, bg="#2d3748", highlightthickness=0)
        self.image_dock_canvas.grid(row=0, column=0, sticky='nsew')
        image_scrollbar = ttk.Scrollbar(image_dock_frame, orient="vertical", command=self.image_dock_canvas.yview)
        image_scrollbar.grid(row=0, column=1, sticky='ns')
        self.image_dock_canvas.configure(yscrollcommand=image_scrollbar.set)

        self._create_transform_controls(tab)

        image_action_frame = tk.Frame(tab, bg="#374151")
        image_action_frame.pack(fill='x', padx=10, pady=(10, 5))
        tk.Button(image_action_frame, text="Apply Image", bg='#10b981', fg='white', relief='flat', font=button_font,
                  command=self.app.image_manager.apply_decal_to_underlying_layer).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        tk.Button(image_action_frame, text="Discard Image", bg='#ef4444', fg='white', relief='flat', font=button_font,
                  command=self.app.image_manager.discard_active_image).pack(side=tk.RIGHT, fill='x', expand=True, padx=(5, 0))

        # --- NEW: Frame for stamping options ---
        stamp_options_frame = tk.Frame(tab, bg="#374151")
        stamp_options_frame.pack(pady=5)

        tk.Checkbutton(stamp_options_frame, text="Ignore Borders", variable=self.app.image_manager.ignore_borders_on_stamp,
                        bg="#374151", fg="white", selectcolor="#1f2937", activebackground="#374151", activeforeground="white"
                        ).pack(side=tk.LEFT, padx=5)
        
        tk.Checkbutton(stamp_options_frame, text="Only Affect Borders", variable=self.app.image_manager.only_affect_borders_on_stamp,
                        bg="#374151", fg="white", selectcolor="#1f2937", activebackground="#374151", activeforeground="white"
                        ).pack(side=tk.LEFT, padx=5)

    def _populate_tile_control_tab(self, tab):
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')
        tk.Label(tab, text="RESIZE TILE", **label_style).pack(fill='x')
        resize_frame = tk.Frame(tab, bg="#374151", padx=10, pady=5)
        resize_frame.pack(fill='x')

        tk.Label(resize_frame, text="Width:", bg="#374151", fg="white").grid(row=0, column=0, sticky='w', pady=2)
        tk.Entry(resize_frame, textvariable=self.app.resize_width, width=10).grid(row=0, column=1, sticky='ew')

        tk.Label(resize_frame, text="Height:", bg="#374151", fg="white").grid(row=1, column=0, sticky='w', pady=2)
        tk.Entry(resize_frame, textvariable=self.app.resize_height, width=10).grid(row=1, column=1, sticky='ew')
        
        resize_frame.grid_columnconfigure(1, weight=1)

        tk.Checkbutton(tab, text="Maintain Aspect Ratio", variable=self.app.maintain_aspect,
                        bg="#374151", fg="white", selectcolor="#1f2937", activebackground="#374151", activeforeground="white",
                        command=self.app.update_resize_entries).pack(pady=5)
        tk.Button(tab, text="Apply Size", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=self.app.resize_selected_component).pack(fill='x', padx=10, pady=5)

        # --- NEW: Add controls for moving the tile ---
        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)
        tk.Label(tab, text="MOVE TILE (PIXELS)", **label_style).pack(fill='x')
        
        move_frame = tk.Frame(tab, bg="#374151", padx=10, pady=5)
        move_frame.pack(fill='x')

        tk.Label(move_frame, text="Amount:", bg="#374151", fg="white").pack(side=tk.LEFT, padx=(0, 5))
        tk.Entry(move_frame, textvariable=self.app.move_amount, width=5).pack(side=tk.LEFT)

        btn_frame = tk.Frame(tab, bg="#374151", padx=10)
        btn_frame.pack(fill='x')
        
        # Grid for directional buttons
        tk.Button(btn_frame, text="Up", bg='#6b7280', fg='white', relief='flat', command=lambda: self.app.move_selected_component('up')).grid(row=0, column=1, pady=2)
        tk.Button(btn_frame, text="Left", bg='#6b7280', fg='white', relief='flat', command=lambda: self.app.move_selected_component('left')).grid(row=1, column=0, padx=2)
        tk.Button(btn_frame, text="Right", bg='#6b7280', fg='white', relief='flat', command=lambda: self.app.move_selected_component('right')).grid(row=1, column=2, padx=2)
        tk.Button(btn_frame, text="Down", bg='#6b7280', fg='white', relief='flat', command=lambda: self.app.move_selected_component('down')).grid(row=2, column=1, pady=2)
        btn_frame.grid_columnconfigure(0, weight=1); btn_frame.grid_columnconfigure(1, weight=1); btn_frame.grid_columnconfigure(2, weight=1)


        # --- NEW: Add a tile selector directly in the resize tab ---
        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)
        tk.Label(tab, text="SELECT TILE TO RESIZE", **label_style).pack(fill='x')

        selector_frame = tk.Frame(tab, bg="#374151", padx=10, pady=5)
        selector_frame.pack(fill='x')

        # Create a grid of buttons for tile selection
        self.app.resize_selector_buttons = {}
        row, col = 0, 0
        for name in self.app.component_list:
            if name == "Show All": continue
            btn = tk.Button(selector_frame, text=name, bg='#6b7280', fg='white', relief='flat', font=('Inter', 9),
                            command=lambda n=name: self.app.handle_resize_selector_click(n))
            btn.grid(row=row, column=col, padx=2, pady=2, sticky='ew')
            self.app.resize_selector_buttons[name] = btn
            col += 1
            if col >= 2: # 2 buttons per row
                col = 0; row += 1

    def _populate_border_tab(self, tab):
        # --- FIX: Clear existing widgets before repopulating to prevent duplicates ---
        for widget in tab.winfo_children():
            widget.destroy()

        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')
        manager = self.app.border_manager

        # --- NEW: Style for Radio Buttons ---
        style = ttk.Style(self.master)
        style.configure('Dark.TRadiobutton', background="#374151", foreground="white", indicatorcolor="#6b7280")
        style.map('Dark.TRadiobutton',
            background=[('active', '#4b5563'), ('selected', '#374151')],
            foreground=[('active', 'white')],
            indicatorcolor=[('selected', '#3b82f6')]
        )

        # --- Preset Selection ---
        tk.Label(tab, text="BORDER PRESETS", **label_style).pack(fill='x')
        
        controls_frame = tk.Frame(tab, bg="#374151", padx=10, pady=5)
        controls_frame.pack(fill='x')
        controls_frame.grid_columnconfigure(1, weight=1)

        # Preset Dropdown
        tk.Label(controls_frame, text="Preset:", bg="#374151", fg="white").grid(row=0, column=0, sticky='w', pady=2)
        # --- FIX: Add "None" to the list of presets and set it as the default ---
        preset_names = ["None"] + list(manager.border_presets.keys())
        if preset_names:
            preset_menu = ttk.OptionMenu(controls_frame, manager.selected_preset, "None", *preset_names)
            preset_menu.grid(row=0, column=1, sticky='ew', padx=5)
            # --- NEW: Bind an event to show the preview when a preset is selected ---
            preset_menu.bind("<<OptionMenuChanged>>", manager.show_preset_preview)

        # Style Dropdown
        tk.Label(controls_frame, text="Style:", bg="#374151", fg="white").grid(row=1, column=0, sticky='w', pady=2)
        style_names = list(manager.border_textures.keys())
        if style_names:
            style_menu = ttk.OptionMenu(controls_frame, manager.selected_style, style_names[0], *style_names)
            style_menu.grid(row=1, column=1, sticky='ew', padx=5)

        # Thickness Slider
        tk.Label(controls_frame, text="Thickness:", bg="#374151", fg="white").grid(row=2, column=0, sticky='w', pady=2)
        thickness_slider = tk.Scale(controls_frame, from_=1, to=50, orient=tk.HORIZONTAL, variable=manager.border_thickness, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0)
        thickness_slider.grid(row=2, column=1, sticky='ew', padx=5)
        thickness_slider.config(command=manager.show_preset_preview)

        # NEW: Border Width Slider
        tk.Label(controls_frame, text="Width (%):", bg="#374151", fg="white").grid(row=3, column=0, sticky='w', pady=2)
        width_slider = tk.Scale(controls_frame, from_=1, to=200, orient=tk.HORIZONTAL, variable=manager.border_width, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0)
        width_slider.grid(row=3, column=1, sticky='ew', padx=5)
        # --- NEW: Update the preview when the width slider is moved ---
        width_slider.config(command=manager.show_preset_preview) # type: ignore

        # --- NEW: Feather Slider ---
        tk.Label(controls_frame, text="Feather:", bg="#374151", fg="white").grid(row=4, column=0, sticky='w', pady=2)
        feather_slider = tk.Scale(controls_frame, from_=0, to=20, orient=tk.HORIZONTAL, variable=manager.border_feather, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0)
        feather_slider.grid(row=4, column=1, sticky='ew', padx=5)
        feather_slider.config(command=manager.show_preset_preview) # type: ignore

        # --- NEW: Growth Direction Toggle ---
        tk.Label(controls_frame, text="Growth:", bg="#374151", fg="white").grid(row=5, column=0, sticky='w', pady=2)
        growth_radio_frame = tk.Frame(controls_frame, bg="#374151")
        growth_radio_frame.grid(row=5, column=1, sticky='w')
        radio_in = ttk.Radiobutton(growth_radio_frame, text="Inward", variable=manager.border_growth_direction, value="in", command=manager.show_preset_preview, style='Dark.TRadiobutton')
        radio_out = ttk.Radiobutton(growth_radio_frame, text="Outward", variable=manager.border_growth_direction, value="out", command=manager.show_preset_preview, style='Dark.TRadiobutton')
        radio_in.pack(side=tk.LEFT, padx=(0, 10))
        radio_out.pack(side=tk.LEFT)

        # Apply Button
        tk.Button(tab, text="Apply Preset Border", bg='#3b82f6', fg='white', relief='flat', font=button_font, command=manager.apply_preset_border).pack(fill='x', padx=10, pady=10)

        # --- NEW: Border Preview Canvas ---
        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)
        tk.Label(tab, text="BORDER PREVIEW", **label_style).pack(fill='x')
        
        preview_frame = tk.Frame(tab, bg="#374151", padx=10, pady=5)
        preview_frame.pack(fill='x')
        
        self.border_preview_canvas = tk.Canvas(preview_frame, bg="#2d3748", height=150, highlightthickness=0)
        self.border_preview_canvas.pack(fill='x', expand=True, pady=(0, 5))
        self.border_preview_canvas.bind("<Button-1>", manager.on_preview_down)
        self.border_preview_canvas.bind("<B1-Motion>", manager.on_preview_drag)
        self.border_preview_canvas.bind("<ButtonRelease-1>", manager.on_preview_up)
        self.border_preview_canvas.bind("<Leave>", manager.on_preview_leave)
        self.border_preview_canvas.bind("<Motion>", manager.on_preview_move)

        # --- NEW: Button to trigger preview area selection ---
        tk.Button(preview_frame, text="Select Area to Preview", bg='#3b82f6', fg='white', relief='flat', font=('Inter', 10, 'bold'),
                  command=manager.toggle_preview_selection_mode).pack(fill='x', expand=True, pady=(5,0))

        tk.Scale(preview_frame, from_=0.5, to=5.0, resolution=0.1, orient=tk.HORIZONTAL, variable=manager.preview_scale_var, command=manager.update_preview_canvas, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0).pack(fill='x', expand=True)

        # --- NEW: Smart Border Tool Section ---
        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)
        tk.Label(tab, text="SMART BORDER TOOL", **label_style).pack(fill='x')

        self.smart_border_btn = tk.Button(tab, text="Smart Border Tool", bg='#0e7490', fg='white', relief='flat', font=button_font, command=manager.toggle_smart_border_mode)
        self.smart_border_btn.pack(fill='x', padx=10, pady=5)

        smart_controls_frame = tk.Frame(tab, bg="#374151", padx=10, pady=5)
        smart_controls_frame.pack(fill='x')
        smart_controls_frame.grid_columnconfigure(1, weight=1)

        # Draw/Erase Toggle
        # --- DEFINITIVE FIX: Add a command to update the UI when the checkbox is toggled ---
        tk.Checkbutton(smart_controls_frame, text="Erase Points", variable=manager.is_erasing_points,
                        bg="#374151", fg="white", selectcolor="#1f2937", activebackground="#374151", activeforeground="white",
                        command=manager.on_erase_mode_toggle
                        ).grid(row=0, column=0, columnspan=2, sticky='w', pady=2)

        # Brush Size
        tk.Label(smart_controls_frame, text="Brush Size:", bg="#374151", fg="white").grid(row=1, column=0, sticky='w', pady=2)
        # --- FIX for AttributeError: Point to the new canvas cursor resize function ---
        tk.Scale(smart_controls_frame, from_=5, to=50, orient=tk.HORIZONTAL, variable=manager.smart_brush_radius,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0,
                 command=manager._update_canvas_brush_size).grid(row=1, column=1, sticky='ew', padx=5)

        # Sensitivity
        tk.Label(smart_controls_frame, text="Sensitivity:", bg="#374151", fg="white").grid(row=2, column=0, sticky='w', pady=2)
        tk.Scale(smart_controls_frame, from_=10, to=100, orient=tk.HORIZONTAL, variable=manager.smart_diff_threshold, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0).grid(row=2, column=1, sticky='ew', padx=5)

        # Draw Skip
        tk.Label(smart_controls_frame, text="Draw Skip:", bg="#374151", fg="white").grid(row=3, column=0, sticky='w', pady=2)
        tk.Scale(smart_controls_frame, from_=1, to=15, orient=tk.HORIZONTAL, variable=manager.smart_draw_skip, bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0).grid(row=3, column=1, sticky='ew', padx=5)

        smart_action_frame = tk.Frame(tab, bg="#374151", padx=10, pady=5)
        smart_action_frame.pack(fill='x')
        tk.Button(smart_action_frame, text="Finalize Border", bg='#10b981', fg='white', relief='flat', font=button_font, command=manager.finalize_border).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        tk.Button(smart_action_frame, text="Clear Points", bg='#ef4444', fg='white', relief='flat', font=button_font, command=manager.clear_detected_points).pack(side=tk.RIGHT, fill='x', expand=True, padx=(5, 0))

    def _populate_filters_tab(self, tab):
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')

        # --- NEW: Debugging Tools ---
        tk.Label(tab, text="COORDINATE DEBUGGING", **label_style).pack(fill='x')

        tk.Button(tab, text="Dot on Tile 01 (430, 455)", bg='#d97706', fg='white', relief='flat', font=button_font,
                  command=lambda: self.app.image_manager.draw_debug_dot('humanuitile01', 430, 455)).pack(fill='x', padx=10, pady=5)

        tk.Button(tab, text="Dot on Tile 02 (49, 455)", bg='#d97706', fg='white', relief='flat', font=button_font,
                  command=lambda: self.app.image_manager.draw_debug_dot('humanuitile02', 49, 455)).pack(fill='x', padx=10, pady=5)

        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=15)

        tk.Label(tab, text="IMAGE FILTERS", **label_style).pack(fill='x')
        tk.Label(tab, text="Controls for brightness, contrast, etc.\nwill go here.", bg="#374151", fg="#9ca3af", justify=tk.LEFT, padx=10).pack(fill='x', pady=10)

    def _populate_text_tab(self, tab):
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        tk.Label(tab, text="TEXT TOOLS", **label_style).pack(fill='x')
        tk.Label(tab, text="Controls for adding and styling text\nwill go here.", bg="#374151", fg="#9ca3af", justify=tk.LEFT, padx=10).pack(fill='x', pady=10)

    def _populate_export_tab(self, tab):
        label_style = {"bg": "#374151", "fg": "white", "font": ("Inter", 12, "bold"), "pady": 10}
        button_font = ('Inter', 11, 'bold')
        tk.Label(tab, text="EXPORT CONTROLS", **label_style).pack(fill='x')
        tk.Button(tab, text="Save Modified PNGs", bg='#10b981', fg='white', relief='flat', font=button_font,
                  command=lambda: self.app._export_modified_images('png')).pack(fill='x', padx=10, pady=5)
        
        tk.Button(tab, text="Save Modified as DDS", bg='#3b82f6', fg='white', relief='flat', font=button_font,
                  command=lambda: self.app._export_modified_images('dds')).pack(fill='x', padx=10, pady=(5, 10))

        # --- NEW: Checkbox to control export behavior ---
        tk.Checkbutton(tab, text="Export all tiles (not just modified)", variable=self.app.export_all_tiles,
                        bg="#374151", fg="white", selectcolor="#1f2937", activebackground="#374151", activeforeground="white"
                        ).pack(pady=5)

        tk.Frame(tab, height=2, bg="#6b7280").pack(fill='x', padx=10, pady=10)
        tk.Label(tab, text="OPEN EXPORT FOLDER", **label_style).pack(fill='x')
        open_folder_frame = tk.Frame(tab, bg="#374151")
        open_folder_frame.pack(fill='x', padx=10, pady=5)
        tk.Button(open_folder_frame, text="Open PNG Folder", bg='#6b7280', fg='white', relief='flat', font=button_font, command=lambda: self.app.open_export_folder('png')).pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        tk.Button(open_folder_frame, text="Open DDS Folder", bg='#6b7280', fg='white', relief='flat', font=button_font, command=lambda: self.app.open_export_folder('dds')).pack(side=tk.RIGHT, fill='x', expand=True, padx=(5, 0))

        tk.Label(tab, text="Note: DDS export requires the image\ndimensions to be a power of two\n(e.g., 256x256, 512x512) and may not\nsupport all internal DDS formats.",
                 bg="#374151", fg="#9ca3af", justify=tk.LEFT, padx=10).pack(fill='x')

    def _create_transform_controls(self, parent_tab):
        """Helper to create the resize and rotate sliders."""
        transform_frame = tk.Frame(parent_tab, bg="#374151")
        transform_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(transform_frame, text="Resize:", bg="#374151", fg="white").grid(row=0, column=0, sticky='w')
        tk.Scale(transform_frame, from_=10, to=200, orient=tk.HORIZONTAL, variable=self.app.image_manager.decal_scale,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0, command=lambda e: self.app.image_manager._update_active_decal_transform(use_fast_preview=True)).grid(row=0, column=1, sticky='ew')
        tk.Button(transform_frame, text="Reset", bg='#6b7280', fg='white', relief='flat', font=('Inter', 8),
                  command=lambda: self.app.image_manager.decal_scale.set(100) or self.app.image_manager._update_active_decal_transform()).grid(row=0, column=2, padx=(5,0))

        tk.Label(transform_frame, text="Rotate:", bg="#374151", fg="white").grid(row=1, column=0, sticky='w')
        tk.Scale(transform_frame, from_=-180, to=180, orient=tk.HORIZONTAL, variable=self.app.image_manager.decal_rotation,
                 bg="#374151", fg="white", troughcolor="#4b5563", highlightthickness=0, command=lambda e: self.app.image_manager._update_active_decal_transform(use_fast_preview=True)).grid(row=1, column=1, sticky='ew')
        tk.Button(transform_frame, text="Reset", bg='#6b7280', fg='white', relief='flat', font=('Inter', 8),
                  command=lambda: self.app.image_manager.decal_rotation.set(0) or self.app.image_manager._update_active_decal_transform()).grid(row=1, column=2, padx=(5,0))
        transform_frame.grid_columnconfigure(1, weight=1)