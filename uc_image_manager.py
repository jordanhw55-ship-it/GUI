import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageChops, ImageEnhance
import os

from uc_component import DraggableComponent

class ImageManager:
    """Manages loading, cloning, transforming, and applying image assets (decals)."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas
        self.next_dynamic_id = 0

        # REFACTOR: Manager now owns the list of dock assets
        self.dock_assets = []


        # Decal/Asset State
        self.decal_scale = tk.DoubleVar(value=100)
        self.decal_rotation = tk.DoubleVar(value=0)
        self.transform_job = None
        self.dock_assets = []
        self.next_clone_id = 0

    def _are_images_identical(self, img1, img2):
        """Helper to check if two PIL images are identical."""
        if img1 is None or img2 is None:
            return img1 == img2
        if img1.size != img2.size or img1.mode != img2.mode:
            return False
        return ImageChops.difference(img1, img2).getbbox() is None

    def _load_asset_to_dock_generic(self, is_border: bool):
        """Loads an image, scales it, and places it in the asset dock as a new draggable component."""
        asset_type = "Border" if is_border else "Asset"
        image_path = filedialog.askopenfilename(
            title=f"Select {asset_type} Image",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif")],
            initialdir=self.app.image_base_dir
        )
        if not image_path:
            return

        try:
            full_res_image = Image.open(image_path).convert("RGBA")
            asset_tag = f"dock_{'border' if is_border else 'asset'}_{self.next_dynamic_id}"
            self.next_dynamic_id += 1

            if is_border:
                target_canvas = self.app.ui_manager.border_dock_canvas
                item_index = sum(1 for asset in self.dock_assets if asset.is_border_asset) # Use manager's list
            else:
                target_canvas = self.app.ui_manager.image_dock_canvas
                item_index = sum(1 for asset in self.dock_assets if not asset.is_border_asset) # Use manager's list

            items_per_row = 2
            padding = 10
            asset_width = (self.app.SIDEBAR_WIDTH - (padding * (items_per_row + 1))) / items_per_row
            asset_height = asset_width

            col = item_index % items_per_row
            row = item_index // items_per_row
            x, y = padding + col * (asset_width + padding), padding + row * (asset_height + padding)

            asset_comp = DraggableComponent(self.app, asset_tag, x, y, x + asset_width, y + asset_height, "blue", "ASSET", is_dock_asset=True)
            asset_comp.is_border_asset = is_border
            asset_comp.image_path = image_path # FIX: Save the file path for persistence

            target_canvas.tag_bind(asset_tag, '<Button-1>', 
                lambda event, comp=asset_comp: self.handle_dock_asset_press(event, comp))

            asset_comp.original_pil_image = full_res_image
            asset_comp.preview_pil_image = full_res_image.copy()
            asset_comp.preview_pil_image.thumbnail((int(asset_width), int(asset_height)), Image.Resampling.LANCZOS)
            
            asset_comp.tk_image = ImageTk.PhotoImage(asset_comp.preview_pil_image)
            asset_comp.rect_id = target_canvas.create_image(x, y, anchor=tk.NW, image=asset_comp.tk_image, tags=(asset_tag,))
            asset_comp.pil_image = asset_comp.preview_pil_image

            self.dock_assets.append(asset_comp)
            
            target_canvas.config(scrollregion=target_canvas.bbox("all"))
            print(f"{asset_type} '{os.path.basename(image_path)}' loaded into dock.")

        except Exception as e:
            messagebox.showerror(f"{asset_type} Load Error", f"Could not load {asset_type.lower()} image: {e}")

    def load_asset_from_path(self, image_path: str, is_border: bool):
        """Loads a dock asset directly from a file path without a dialog."""
        if not image_path or not os.path.exists(image_path):
            print(f"[WARNING] Could not reload asset. File not found: {image_path}")
            return

        try:
            full_res_image = Image.open(image_path).convert("RGBA")
            asset_tag = f"dock_{'border' if is_border else 'asset'}_{self.next_dynamic_id}"
            self.next_dynamic_id += 1

            if is_border:
                target_canvas = self.app.ui_manager.border_dock_canvas
                item_index = sum(1 for asset in self.dock_assets if asset.is_border_asset)
            else:
                target_canvas = self.app.ui_manager.image_dock_canvas
                item_index = sum(1 for asset in self.dock_assets if not asset.is_border_asset)

            items_per_row = 2
            padding = 10
            asset_width = (self.app.SIDEBAR_WIDTH - (padding * (items_per_row + 1))) / items_per_row
            asset_height = asset_width

            col = item_index % items_per_row
            row = item_index // items_per_row
            x, y = padding + col * (asset_width + padding), padding + row * (asset_height + padding)

            asset_comp = DraggableComponent(self.app, asset_tag, x, y, x + asset_width, y + asset_height, "blue", "ASSET", is_dock_asset=True)
            asset_comp.is_border_asset = is_border
            asset_comp.image_path = image_path # Save the path

            target_canvas.tag_bind(asset_tag, '<Button-1>', lambda event, comp=asset_comp: self.handle_dock_asset_press(event, comp))

            asset_comp.original_pil_image = full_res_image
            asset_comp.preview_pil_image = full_res_image.copy()
            asset_comp.preview_pil_image.thumbnail((int(asset_width), int(asset_height)), Image.Resampling.LANCZOS)
            asset_comp.tk_image = ImageTk.PhotoImage(asset_comp.preview_pil_image)
            asset_comp.rect_id = target_canvas.create_image(x, y, anchor=tk.NW, image=asset_comp.tk_image, tags=(asset_tag,))
            self.dock_assets.append(asset_comp)
            target_canvas.config(scrollregion=target_canvas.bbox("all"))
        except Exception as e:
            print(f"[ERROR] Failed to reload asset from path '{image_path}': {e}")
    def apply_decal_to_underlying_layer(self):
        """Finds the active decal and stamps it onto any underlying components."""
        stamp_source_comp = self._find_topmost_stamp_source(show_warning=True, clone_type='any')
        if not stamp_source_comp:
            return
        
        # Recreate the stamp from the original image and current transforms
        scale_factor = self.decal_scale.get() / 100.0
        rotation_angle = self.decal_rotation.get()

        original_w, original_h = stamp_source_comp.original_pil_image.size
        new_w = int(original_w * scale_factor)
        new_h = int(original_h * scale_factor)
        resized_image = stamp_source_comp.original_pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        decal_stamp_image = resized_image.rotate(rotation_angle, expand=True, resample=Image.Resampling.BICUBIC)
        stamp_w, stamp_h = decal_stamp_image.size

        stamp_cx = (stamp_source_comp.world_x1 + stamp_source_comp.world_x2) / 2
        stamp_cy = (stamp_source_comp.world_y1 + stamp_source_comp.world_y2) / 2
        stamp_world_x1 = stamp_cx - stamp_w / 2
        stamp_world_y1 = stamp_cy - stamp_h / 2
        stamp_world_x2 = stamp_world_x1 + stamp_w
        stamp_world_y2 = stamp_world_y1 + stamp_h

        undo_data = {}
        applied_count = 0

        # --- DEFINITIVE FIX: Iterate through all components to find targets ---
        # The previous logic was flawed. We must check every component to see if it's a valid target.
        for target_comp in self.app.components.values():
            # Skip if it's the stamp itself, a dock asset, or has no image to stamp onto.
            if target_comp.tag == stamp_source_comp.tag or target_comp.is_dock_asset or not target_comp.pil_image:
                continue

            # Attempt to composite the decal onto this specific target component.
            final_image, applied = self._composite_decal_onto_image(target_comp, decal_stamp_image, stamp_world_x1, stamp_world_y1, stamp_world_x2, stamp_world_y2, stamp_source_comp.is_border_asset)
            
            if applied:
                # If the composite was successful, save an undo state and apply the new image.
                if target_comp.tag not in undo_data:
                    undo_data[target_comp.tag] = target_comp.pil_image.copy()
                target_comp.set_image(final_image)
                applied_count += 1
                print(f"Stamped decal onto layer '{target_comp.tag}'.")

        if applied_count == 0:
            messagebox.showwarning("No Target", "Decal must be positioned over a valid layer to be applied.")
            return

        if undo_data:
            self.app._save_undo_state(undo_data)

        self._remove_stamp_source_component(stamp_source_comp)
        self.app.redraw_all_zoomable()

    def _composite_decal_onto_image(self, target_comp, decal_stamp_image, stamp_world_x1, stamp_world_y1, stamp_world_x2, stamp_world_y2, is_border):
        """
        Helper function to composite a decal/stamp image onto a target component's image.
        Returns the new composited image and a boolean indicating if a change was made.
        """
        # Calculate the intersection in WORLD coordinates
        intersect_x1 = max(stamp_world_x1, target_comp.world_x1)
        intersect_y1 = max(stamp_world_y1, target_comp.world_y1)
        intersect_x2 = min(stamp_world_x2, target_comp.world_x2)
        intersect_y2 = min(stamp_world_y2, target_comp.world_y2)

        # If they overlap...
        if intersect_x1 < intersect_x2 and intersect_y1 < intersect_y2:
            # Scale paste position relative to the target's PIL image size
            target_world_w = target_comp.world_x2 - target_comp.world_x1
            target_world_h = target_comp.world_y2 - target_comp.world_y1
            if target_world_w == 0 or target_world_h == 0:
                return target_comp.pil_image, False

            scale_x = target_comp.pil_image.width / target_world_w
            scale_y = target_comp.pil_image.height / target_world_h

            paste_x = int((intersect_x1 - target_comp.world_x1) * scale_x)
            paste_y = int((intersect_y1 - target_comp.world_y1) * scale_y)

            # --- DEFINITIVE FIX: Correctly calculate the crop box from the stamp image ---
            # The intersection is in world coordinates. We need to find out what part of the
            # decal_stamp_image corresponds to this intersection.
            stamp_w, stamp_h = decal_stamp_image.size
            stamp_world_w = stamp_world_x2 - stamp_world_x1
            stamp_world_h = stamp_world_y2 - stamp_world_y1

            # Calculate the scale of the stamp image relative to its world dimensions
            stamp_scale_x = stamp_w / stamp_world_w if stamp_world_w > 0 else 1
            stamp_scale_y = stamp_h / stamp_world_h if stamp_world_h > 0 else 1

            crop_x1 = int((intersect_x1 - stamp_world_x1) * stamp_scale_x)
            crop_y1 = int((intersect_y1 - stamp_world_y1) * stamp_scale_y)
            crop_x2 = int((intersect_x2 - stamp_world_x1) * stamp_scale_x)
            crop_y2 = int((intersect_y2 - stamp_world_y1) * stamp_scale_y)
            
            cropped_stamp = decal_stamp_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))

            # --- DEFINITIVE FIX: Resize the cropped stamp to match the target's image scale ---
            # The cropped stamp is in the decal's pixel space. The paste position is in the
            # target's pixel space. We must scale the stamp to match the target's scale.
            final_stamp_w = int(cropped_stamp.width * scale_x)
            final_stamp_h = int(cropped_stamp.height * scale_y)
            if final_stamp_w > 0 and final_stamp_h > 0:
                cropped_stamp = cropped_stamp.resize((final_stamp_w, final_stamp_h), Image.Resampling.LANCZOS)

            final_image = target_comp.pil_image.copy()
            decal_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
            decal_layer.paste(cropped_stamp, (paste_x, paste_y))

            # Conditionally respect transparency of the underlying tile
            if not is_border:
                comp_alpha_mask = final_image.getchannel('A')
                combined_alpha = ImageChops.multiply(decal_layer.getchannel('A'), comp_alpha_mask)
                decal_layer.putalpha(combined_alpha)
                
            final_image = Image.alpha_composite(final_image, decal_layer)

            # Return the new image and True to indicate a change was made
            return final_image, True

        # No overlap, return original image and False
        return target_comp.pil_image, False

    def schedule_transform_update(self, event=None):
        """Schedules a decal transformation update, debouncing slider events."""
        if self.transform_job:
            self.app.master.after_cancel(self.transform_job)
        self.transform_job = self.app.master.after(150, self._update_active_decal_transform)

    def _update_active_decal_transform(self, event=None, use_fast_preview=False):
        """Applies resize and rotation transformations to the active decal."""
        if self.transform_job:
            self.app.master.after_cancel(self.transform_job)
        if use_fast_preview:
            self.transform_job = self.app.master.after(250, self._update_active_decal_transform)

        decal = self._find_topmost_stamp_source(show_warning=False, clone_type='any')
        if not decal or not decal.original_pil_image:
            return

        scale_factor = self.decal_scale.get() / 100.0
        rotation_angle = self.decal_rotation.get()

        original_w, original_h = decal.original_pil_image.size
        new_w, new_h = int(original_w * scale_factor), int(original_h * scale_factor)

        if new_w > 0 and new_h > 0:
            resample_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.LANCZOS
            rotate_quality = Image.Resampling.NEAREST if use_fast_preview else Image.Resampling.BICUBIC

            resized_image = decal.original_pil_image.resize((new_w, new_h), resample_quality)
            rotated_image = resized_image.rotate(rotation_angle, expand=True, resample=rotate_quality)

            alpha = rotated_image.getchannel('A')
            semi_transparent_alpha = Image.eval(alpha, lambda a: a // 2)
            display_image = rotated_image.copy()
            display_image.putalpha(semi_transparent_alpha)

            # Update the component's world coordinates to match the new visual size
            final_w, final_h = rotated_image.size
            cx = (decal.world_x1 + decal.world_x2) / 2
            cy = (decal.world_y1 + decal.world_y2) / 2
            decal.world_x1 = cx - final_w / 2
            decal.world_y1 = cy - final_h / 2
            decal.world_x2 = cx + final_w / 2
            decal.world_y2 = cy + final_h / 2
            
            # --- DEFINITIVE FIX: Set the component's image to the new transparent preview ---
            # Use `display_pil_image` for on-canvas rendering, preserving `pil_image`
            decal.display_pil_image = display_image
            # The manager is responsible for redrawing
            self.app.redraw_all_zoomable()


    def discard_active_image(self):
        """Finds and removes the active decal without applying it."""
        image_to_discard = self._find_topmost_stamp_source(clone_type='any')
        if not image_to_discard:
            return
        self._remove_stamp_source_component(image_to_discard)
        self.app.redraw_all_zoomable()
        print(f"Discarded image '{image_to_discard.tag}'.")

    def _find_topmost_stamp_source(self, show_warning=True, clone_type: str = 'clone'):
        """Finds the top-most draggable image (decal/clone) on the canvas."""
        prefix = f"{clone_type}_"
        for item_id in reversed(self.canvas.find_all()):
            tags = self.canvas.gettags(item_id)
            if not tags: continue
            
            tag = tags[0]
            if tag in self.app.components:
                comp = self.app.components[tag]
                if comp.is_draggable and comp.pil_image and not comp.is_dock_asset:
                    if clone_type == 'any' and (tag.startswith('clone_') or tag.startswith('border_')):
                        return comp
                    if tag.startswith(prefix):
                        return comp
        
        if show_warning:
            messagebox.showwarning("No Image Found", f"Could not find an active '{clone_type}' image to apply or discard.")
        return None
    
    def _remove_stamp_source_component(self, comp_to_remove):
        """Helper to cleanly remove a decal/clone from the canvas and component list."""
        if not comp_to_remove: return
        
        self.canvas.delete(comp_to_remove.tag)
        if comp_to_remove.tag in self.app.components:
            del self.app.components[comp_to_remove.tag]
        self.app.redraw_all_zoomable()

    def load_asset_to_dock(self):
        """Loads a regular image to the asset dock."""
        self._load_asset_to_dock_generic(is_border=False)

    def handle_dock_asset_press(self, event, asset_comp):
        """Translates a click on a dock asset to the main canvas and creates a clone."""
        dock_canvas = event.widget
        abs_x = dock_canvas.winfo_rootx() + event.x
        abs_y = dock_canvas.winfo_rooty() + event.y

        main_canvas_x = abs_x - self.app.canvas.winfo_rootx()
        main_canvas_y = abs_y - self.app.canvas.winfo_rooty()

        corrected_event = tk.Event()
        corrected_event.x, corrected_event.y = main_canvas_x, main_canvas_y
        self.create_clone_from_asset(asset_comp, corrected_event)

    def create_clone_from_asset(self, asset_comp, event):
        """Creates a new draggable component by cloning an asset from the dock."""
        if not asset_comp.original_pil_image:
            return

        clone_prefix = "border_" if asset_comp.is_border_asset else "clone_"
        existing_active_image = self._find_topmost_stamp_source(show_warning=False, clone_type='any')
        if existing_active_image:
            self._remove_stamp_source_component(existing_active_image)

        clone_tag = f"{clone_prefix}{self.next_dynamic_id}"
        self.next_dynamic_id += 1

        # --- MODIFICATION: Place the clone in the center of the canvas, not at the cursor ---
        # 1. Get the center of the canvas in screen coordinates.
        center_x_screen = self.app.CANVAS_WIDTH / 2
        center_y_screen = self.app.CANVAS_HEIGHT / 2
        # 2. Convert the screen center to world coordinates to respect pan/zoom.
        world_x, world_y = self.app.camera.screen_to_world(center_x_screen, center_y_screen)
        w, h = asset_comp.original_pil_image.size
        clone_comp = DraggableComponent(self.app, clone_tag, world_x - w/2, world_y - h/2, world_x + w/2, world_y + h/2, "green", clone_tag)

        # --- DEFINITIVE FIX: Create the transparent preview BEFORE drawing ---
        # 1. Set the clone's core properties.
        clone_comp.is_border_asset = asset_comp.is_border_asset
        clone_comp.is_decal = True
        clone_comp.original_pil_image = asset_comp.original_pil_image.copy()
        clone_comp.pil_image = clone_comp.original_pil_image.copy()

        # 2. Generate the initial semi-transparent display image.
        # This is the same logic from _update_active_decal_transform, but applied immediately.
        alpha = clone_comp.original_pil_image.getchannel('A')
        semi_transparent_alpha = Image.eval(alpha, lambda a: a // 2)
        display_image = clone_comp.original_pil_image.copy()
        display_image.putalpha(semi_transparent_alpha)
        clone_comp.display_pil_image = display_image # Set the transparent image

        # 3. Now, add the fully prepared component to the app and draw it.
        self.app.components[clone_tag] = clone_comp
        self.app._bind_component_events(clone_tag)

        # 4. Final setup and redraw.
        self.app._keep_docks_on_top()
        self.app.redraw_all_zoomable()

        print(f"Created clone '{clone_tag}' from asset '{asset_comp.tag}'.")