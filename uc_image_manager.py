import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageChops
import os

from uc_component import DraggableComponent

class ImageManager:
    """Manages loading, cloning, transforming, and applying image assets (decals)."""
    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas

        # Decal/Asset State
        self.decal_scale = tk.DoubleVar(value=100)
        self.decal_rotation = tk.DoubleVar(value=0)
        self.transform_job = None
        self.dock_assets = []
        self.next_clone_id = 0
        self.next_asset_id = 0

    def load_asset_to_dock(self):
        """Loads a regular image to the asset dock."""
        self._load_asset_to_dock_generic(is_border=False)

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
            asset_tag = f"dock_{'border' if is_border else 'asset'}_{self.next_asset_id}"
            self.next_asset_id += 1

            if is_border:
                target_canvas = self.app.ui_manager.border_dock_canvas
                item_index = sum(1 for asset in self.dock_assets if asset.is_border_asset)
            else:
                target_canvas = self.app.ui_manager.image_dock_canvas
                item_index = sum(1 for asset in self.dock_assets if not asset.is_border_asset)

            items_per_row = 4
            padding = 10
            asset_width = 128
            asset_height = 128

            col = item_index % items_per_row
            row = item_index // items_per_row
            # --- FIX: Use relative coordinates for the dock canvas, not absolute ---
            x, y = padding + col * (asset_width + padding), padding + row * (asset_height + padding)

            # Create the component on the target dock canvas
            asset_comp = DraggableComponent(target_canvas, self.app, asset_tag, x, y, x + asset_width, y + asset_height, "blue", "ASSET", is_dock_asset=True)
            asset_comp.is_border_asset = is_border

            target_canvas.tag_bind(asset_tag, '<Button-1>', 
                lambda event, comp=asset_comp: self.handle_dock_asset_press(event, comp))

            asset_comp.original_pil_image = full_res_image
            asset_comp.preview_pil_image = full_res_image.copy()
            asset_comp.preview_pil_image.thumbnail((asset_width, asset_height), Image.Resampling.LANCZOS)
            
            asset_comp._set_pil_image(asset_comp.preview_pil_image, resize_to_fit=True)

            self.app.components[asset_tag] = asset_comp
            self.dock_assets.append(asset_comp)
            
            target_canvas.config(scrollregion=target_canvas.bbox("all"))
            print(f"{asset_type} '{os.path.basename(image_path)}' loaded into dock.")

        except Exception as e:
            messagebox.showerror(f"{asset_type} Load Error", f"Could not load {asset_type.lower()} image: {e}")

    def handle_dock_asset_press(self, event, asset_comp):
        """Translates a click on a dock asset to the main canvas to create a clone."""
        dock_canvas = event.widget
        abs_x = dock_canvas.winfo_rootx() + event.x
        abs_y = dock_canvas.winfo_rooty() + event.y
        main_canvas_x = abs_x - self.canvas.winfo_rootx()
        main_canvas_y = abs_y - self.canvas.winfo_rooty()

        corrected_event = tk.Event()
        corrected_event.x, corrected_event.y = main_canvas_x, main_canvas_y
        self.create_clone_from_asset(asset_comp, corrected_event)

    def create_clone_from_asset(self, asset_comp, event):
        """Creates a new draggable component (decal/clone) from a dock asset."""
        if not asset_comp.original_pil_image:
            return

        clone_prefix = "border_" if asset_comp.is_border_asset else "clone_"
        existing_active_image = self._find_topmost_stamp_source(show_warning=False, clone_type='any')
        if existing_active_image:
            self._remove_stamp_source_component(existing_active_image)

        clone_tag = f"{clone_prefix}{self.next_clone_id}"
        self.next_clone_id += 1
        
        world_x, world_y = self.app.camera.screen_to_world(event.x, event.y)
        w, h = asset_comp.original_pil_image.size
        clone_comp = DraggableComponent(self.canvas, self.app, clone_tag, world_x - w/2, world_y - h/2, world_x + w/2, world_y + h/2, "green", clone_tag)
        
        clone_comp.is_border_asset = asset_comp.is_border_asset
        clone_comp.is_decal = True

        # --- CRITICAL FIX: Give the clone its own copy of the image ---
        # This prevents the clone's image from being a direct reference to the dock asset's image.
        clone_comp.original_pil_image = asset_comp.original_pil_image.copy()
        # --- FIX: Use the clone's own copied image for display, not the asset's, to prevent
        # the component from accidentally re-linking its original_pil_image to the asset.
        clone_comp._set_pil_image(clone_comp.original_pil_image, resize_to_fit=False)
        
        self.app.components[clone_tag] = clone_comp
        self._update_active_decal_transform()
        self.app._keep_docks_on_top()
        print(f"Created clone '{clone_tag}' from asset '{asset_comp.tag}'.")

    def apply_decal_to_underlying_layer(self):
        """Finds the active decal and stamps it onto any underlying components."""
        stamp_source_comp = self._find_topmost_stamp_source(clone_type='any')
        if not stamp_source_comp:
            return

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

        for target_comp in self.app.components.values():
            if target_comp.tag == stamp_source_comp.tag or target_comp.is_dock_asset or not target_comp.pil_image:
                continue

            final_image, applied = self._composite_decal_onto_image(target_comp, decal_stamp_image, stamp_world_x1, stamp_world_y1, stamp_world_x2, stamp_world_y2, stamp_source_comp.is_border_asset)
            
            if applied:
                if target_comp.tag not in undo_data:
                    undo_data[target_comp.tag] = target_comp.pil_image.copy()
                target_comp._set_pil_image(final_image)
                applied_count += 1
                print(f"Stamped decal onto layer '{target_comp.tag}'.")


        if applied_count == 0:
            messagebox.showwarning("No Target", "Decal must be positioned over a valid layer to be applied.")
            return

        if undo_data:
            self.app._save_undo_state(undo_data)

        self._remove_stamp_source_component(stamp_source_comp)
        self.app.redraw_all_zoomable()
        self.app._keep_docks_on_top()

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

            # Determine which part of the stamp image to use
            crop_x1 = int(intersect_x1 - stamp_world_x1)
            crop_y1 = int(intersect_y1 - stamp_world_y1)
            crop_x2 = int(intersect_x2 - stamp_world_x1)
            crop_y2 = int(intersect_y2 - stamp_world_y1)
            
            cropped_stamp = decal_stamp_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))

            # Resize the cropped stamp to match the target's image scale
            final_stamp_w = int(cropped_stamp.width * scale_x)
            final_stamp_h = int(cropped_stamp.height * scale_y)
            if final_stamp_w > 0 and final_stamp_h > 0:
                cropped_stamp = cropped_stamp.resize((final_stamp_w, final_stamp_h), Image.Resampling.LANCZOS)

            # Composite the images
            final_image = target_comp.pil_image.copy()
            decal_layer = Image.new("RGBA", final_image.size, (0, 0, 0, 0))
            decal_layer.paste(cropped_stamp, (paste_x, paste_y), cropped_stamp)

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

            # --- CRITICAL FIX: Update the component's world coordinates ---
            # This ensures the bounding box used for stamping matches the visual size.
            final_w, final_h = rotated_image.size
            cx = (decal.world_x1 + decal.world_x2) / 2
            cy = (decal.world_y1 + decal.world_y2) / 2
            decal.world_x1 = cx - final_w / 2
            decal.world_y1 = cy - final_h / 2
            decal.world_x2 = cx + final_w / 2
            decal.world_y2 = cy + final_h / 2
            decal._set_pil_image(display_image, resize_to_fit=False)

    def discard_active_image(self):
        """Finds and removes the active decal without applying it."""
        image_to_discard = self._find_topmost_stamp_source(clone_type='any')
        if not image_to_discard:
            return
        self._remove_stamp_source_component(image_to_discard)
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