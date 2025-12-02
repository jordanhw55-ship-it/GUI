import re
from PySide6.QtWidgets import QListWidgetItem, QTableWidgetItem, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

class ItemsManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.items_tab = main_window.items_tab
        self.item_database = main_window.item_database

        # Connect signals from the UI to this manager's methods
        self.items_tab.search_box.textChanged.connect(self.on_item_search_changed)
        for i, btn in self.items_tab.item_tab_buttons.items():
            btn.clicked.connect(lambda checked, idx=i: self.switch_items_sub_tab(idx))

        self.items_tab.add_recipe_btn.clicked.connect(self.add_recipe_to_progress)
        self.items_tab.remove_recipe_btn.clicked.connect(self.remove_recipe_from_progress)
        self.items_tab.reset_recipes_btn.clicked.connect(self.reset_recipes)
        self.items_tab.in_progress_recipes_list.itemChanged.connect(self.on_recipe_check_changed)
        self.items_tab.materials_table.itemChanged.connect(self.on_material_checked)

    def on_item_search_changed(self):
        """Decides which view to filter based on the active sub-tab."""
        if self.items_tab.main_stack.currentIndex() == 1:
            self.filter_recipes_list()
        else:
            self.filter_current_item_view()

    def filter_current_item_view(self):
        query = self.items_tab.search_box.text().lower()
        current_index = self.items_tab.item_tables_stack.currentIndex()
        data_source, table_widget = [], None
        if current_index == 0: data_source, table_widget = self.item_database.all_items_data, self.items_tab.all_items_table
        elif current_index == 1: data_source, table_widget = self.item_database.drops_data, self.items_tab.drops_table
        elif current_index == 2: data_source, table_widget = self.item_database.raid_data, self.items_tab.raid_items_table
        elif current_index == 3: data_source, table_widget = self.item_database.vendor_data, self.items_tab.vendor_table
        if not table_widget: return
        table_widget.setSortingEnabled(False); table_widget.setRowCount(0)
        filtered_data = [item for item in data_source if query in item.get("Item", "").lower() or
                         query in item.get("Unit", "").lower() or query in item.get("Location", "").lower()]
        headers = [table_widget.horizontalHeaderItem(i).text() for i in range(table_widget.columnCount())]
        for row, item_data in enumerate(filtered_data):
            table_widget.insertRow(row)
            for col, header in enumerate(headers):
                table_widget.setItem(row, col, QTableWidgetItem(item_data.get(header, "")))
        table_widget.setSortingEnabled(True)

    def switch_items_sub_tab(self, index: int):
        for i, btn in self.items_tab.item_tab_buttons.items():
            btn.setChecked(i == index)

        is_recipe_tab = (index == len(self.items_tab.item_tab_buttons) - 1)

        if is_recipe_tab:
            self.items_tab.main_stack.setCurrentIndex(1)
            self.items_tab.search_box.setPlaceholderText("Search...")
            # DEFERRED LOADING: Load recipes only when this tab is first opened.
            if not self.item_database.recipes_data:
                print("[INFO] Loading recipes for the first time...")
                self.item_database.load_recipes()
            self.filter_recipes_list()
            self.rebuild_materials_table()
        else:
            self.items_tab.main_stack.setCurrentIndex(0)
            self.items_tab.item_tables_stack.setCurrentIndex(index)
            self.items_tab.search_box.show()

            if index == 0 and not self.item_database.all_items_data: self.item_database.all_items_data = self.item_database._load_item_data_from_folder("All Items")
            elif index == 1 and not self.item_database.drops_data: self.item_database.drops_data = self.item_database._load_item_data_from_folder("Drops")
            elif index == 2 and not self.item_database.raid_data: self.item_database.raid_data = self.item_database._load_item_data_from_folder("Raid Items")
            elif index == 3 and not self.item_database.vendor_data: self.item_database.vendor_data = self.item_database._load_item_data_from_folder("Vendor Items")
            self.filter_current_item_view()

    def filter_recipes_list(self):
        query = self.items_tab.search_box.text().lower()
        self.items_tab.available_recipes_list.clear()
        for recipe in self.item_database.recipes_data:
            if query in recipe["name"].lower():
                item = QListWidgetItem(recipe["name"])
                item.setData(Qt.ItemDataRole.UserRole, recipe)
                self.items_tab.available_recipes_list.addItem(item)

    def add_recipe_to_progress(self):
        selected_item = self.items_tab.available_recipes_list.currentItem()
        if not selected_item: return False
        if self._add_recipe_by_name(selected_item.text()):
            self.rebuild_materials_table()
            return True
        return False

    def _add_recipe_by_name(self, recipe_name: str):
        """Helper to add a recipe to the in-progress list by its name."""
        if recipe_name in self.main_window.in_progress_recipes:
            return False

        # Find the full recipe object from the database
        recipe = next((r for r in self.item_database.recipes_data if r["name"] == recipe_name), None)
        if not recipe:
            return False # Recipe not found in database

        self.main_window.in_progress_recipes[recipe_name] = recipe
        item = QListWidgetItem(recipe_name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Unchecked)
        self.items_tab.in_progress_recipes_list.addItem(item)
        return True

    def remove_recipe_from_progress(self):
        selected_item = self.items_tab.in_progress_recipes_list.currentItem()
        if not selected_item: return
        recipe_name = selected_item.text()
        recipe = self.main_window.in_progress_recipes.pop(recipe_name, None)
        if recipe:
            list_widget = self.items_tab.in_progress_recipes_list
            list_widget.takeItem(list_widget.row(selected_item))
            self.rebuild_materials_table()

    def reset_recipes(self):
        confirm = QMessageBox.question(self.main_window, "Confirm Reset", "Are you sure you want to clear all in-progress recipes?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.main_window.in_progress_recipes.clear()
            self.items_tab.in_progress_recipes_list.clear()
            self.rebuild_materials_table()

    def rebuild_materials_table(self):
        materials_table = self.items_tab.materials_table
        materials_table.setSortingEnabled(False)
        try:
            materials_table.itemChanged.disconnect(self.on_material_checked)
        except RuntimeError: pass # Already disconnected
        materials_table.setRowCount(0)
        
        checked_recipe_names = []
        in_progress_list = self.items_tab.in_progress_recipes_list
        for i in range(in_progress_list.count()):
            item = in_progress_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked_recipe_names.append(item.text())
        
        target_recipe_names = checked_recipe_names if checked_recipe_names else [in_progress_list.item(i).text() for i in range(in_progress_list.count())]
        
        materials_to_display = {}
        for recipe_name in target_recipe_names:
            recipe = self.main_window.in_progress_recipes.get(recipe_name)
            if not recipe: continue
            
            for component_str in recipe["components"]:
                match = re.match(r"^(.*?)\s+x(\d+)$", component_str, re.IGNORECASE)
                name, quantity = (match.group(1).strip(), int(match.group(2))) if match else (component_str.strip(), 1)
                
                if name in materials_to_display:
                    materials_to_display[name]["#"] += quantity
                else:
                    drop_info = next((item for item in self.item_database.all_items_data if item["Item"].lower() == name.lower()), None)
                    materials_to_display[name] = {"Material": name, "#": quantity, "Unit": drop_info["Unit"] if drop_info else "?", "Location": drop_info["Location"] if drop_info else "?"}
        
        for row, item_data in enumerate(materials_to_display.values()):
            materials_table.insertRow(row)
            material_item = QTableWidgetItem(item_data["Material"])
            material_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            material_item.setCheckState(Qt.CheckState.Unchecked)
            materials_table.setItem(row, 0, material_item)

            for col, key in enumerate(["#", "Unit", "Location"], 1):
                text = str(item_data.get(key, ""))
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                materials_table.setItem(row, col, item)

            sort_item = QTableWidgetItem("0")
            sort_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            materials_table.setItem(row, 4, sort_item)
        
        materials_table.itemChanged.connect(self.on_material_checked)
        materials_table.setSortingEnabled(True)

    def on_recipe_check_changed(self, item: QListWidgetItem):
        self.rebuild_materials_table()

    def on_material_checked(self, item: QTableWidgetItem):
        if item.column() != 0: return
        materials_table = self.items_tab.materials_table
        is_checked = item.checkState() == Qt.CheckState.Checked
        color = QColor("gray") if is_checked else self.main_window.palette().color(self.main_window.foregroundRole())
        
        try:
            materials_table.itemChanged.disconnect(self.on_material_checked)
        except RuntimeError: pass

        for col in range(materials_table.columnCount()):
            table_item = materials_table.item(item.row(), col)
            if table_item: table_item.setForeground(color)
        
        sort_item = materials_table.item(item.row(), 4)
        if sort_item: sort_item.setText("1" if is_checked else "0")
        
        materials_table.setSortingEnabled(True)
        materials_table.sortItems(4, Qt.SortOrder.AscendingOrder)
        materials_table.itemChanged.connect(self.on_material_checked)