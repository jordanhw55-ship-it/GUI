from PySide6.QtCore import QThread, QTimer, Qt
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtGui import QColor

from workers import LobbyFetcher, LobbyHeartbeatChecker

class AlignedTableWidgetItem(QTableWidgetItem):
    """A QTableWidgetItem that defaults to center alignment."""
    def __init__(self, text, alignment=Qt.AlignmentFlag.AlignCenter):
        super().__init__(text)
        self.setTextAlignment(alignment)

class LobbyManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.lobbies_tab = main_window.lobbies_tab

        # State variables moved from SimpleWindow
        self.all_lobbies = []
        self.is_fetching_lobbies = False
        self.last_lobby_id = 0
        self.previous_watched_lobbies = set()
        self.watchlist = main_window.settings_manager.get("watchlist", ["hellfire", "rpg"])
        self.play_sound_on_found = main_window.settings_manager.get("play_sound_on_found", False)
        self.selected_sound = main_window.settings_manager.get("selected_sound", "ping1.mp3")
        self.volume = main_window.settings_manager.get("volume", 100)

        self.thread = None
        self.worker = None

        # Connect signals
        self.lobbies_tab.lobby_search_bar.textChanged.connect(self.filter_lobbies)
        self.lobbies_tab.refresh_button.clicked.connect(self.refresh_lobbies)
        self.lobbies_tab.toggle_watchlist_btn.clicked.connect(self.toggle_watchlist_visibility)
        self.lobbies_tab.add_watchlist_button.clicked.connect(self.add_to_watchlist)
        self.lobbies_tab.remove_watchlist_button.clicked.connect(self.remove_from_watchlist)

        for sound, btn in self.lobbies_tab.ping_buttons.items():
            btn.clicked.connect(lambda checked=False, s=sound: self.select_ping_sound(s))
        self.lobbies_tab.test_sound_button.clicked.connect(self.main_window.play_notification_sound)
        self.lobbies_tab.volume_slider.valueChanged.connect(self.set_volume)

        # Populate initial UI state
        self.lobbies_tab.watchlist_widget.addItems(self.watchlist)
        self.lobbies_tab.lobby_placeholder_checkbox.setChecked(self.play_sound_on_found)
        self.lobbies_tab.volume_slider.setValue(self.volume)

        # Start the refresh timer
        self.refresh_timer = QTimer(main_window)
        self.refresh_timer.setInterval(15000)
        self.refresh_timer.timeout.connect(self.check_for_lobby_updates)
        self.refresh_timer.start()

    def check_for_lobby_updates(self):
        if self.is_fetching_lobbies: return
        self.thread = QThread()
        self.worker = LobbyHeartbeatChecker(self.last_lobby_id)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.update_required.connect(self.refresh_lobbies)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def refresh_lobbies(self):
        if self.is_fetching_lobbies: return
        self.is_fetching_lobbies = True
        lobbies_table = self.lobbies_tab.lobbies_table
        lobbies_table.setRowCount(0); lobbies_table.setRowCount(1)
        loading_item = QTableWidgetItem("Fetching lobby data...")
        loading_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        lobbies_table.setItem(0, 0, loading_item); lobbies_table.setSpan(0, 0, 1, 3)
        self.thread = QThread(); self.worker = LobbyFetcher(); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_lobbies_fetched)
        self.worker.error.connect(self.on_lobbies_fetch_error)
        self.worker.finished.connect(self.thread.quit); self.worker.error.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater); self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_lobbies_fetched(self, lobbies: list):
        current_watched_lobbies = set()
        if lobbies: self.last_lobby_id = lobbies[0].get("id", self.last_lobby_id)
        self.is_fetching_lobbies = False
        for lobby in lobbies:
            lobby_name = lobby.get('name', '').lower()
            lobby_map = lobby.get('map', '').lower()
            for keyword in self.watchlist:
                if keyword in lobby_name or keyword in lobby_map:
                    current_watched_lobbies.add(lobby.get('name')); break
        newly_found = current_watched_lobbies - self.previous_watched_lobbies
        if newly_found and self.lobbies_tab.lobby_placeholder_checkbox.isChecked():
            self.main_window.play_notification_sound()
        self.previous_watched_lobbies = current_watched_lobbies
        self.all_lobbies = lobbies
        self.filter_lobbies(self.lobbies_tab.lobby_search_bar.text())

    def on_lobbies_fetch_error(self, error_message: str):
        self.is_fetching_lobbies = False
        lobbies_table = self.lobbies_tab.lobbies_table
        lobbies_table.setRowCount(1)
        lobbies_table.setSpan(0, 0, 1, lobbies_table.columnCount())

        # Create a more user-friendly error message for common network issues
        display_message = f"Error: {error_message}"
        if "network error" in error_message.lower():
            display_message = "Could not connect to the lobby server. It may be temporarily down."

        error_item = QTableWidgetItem(display_message)
        error_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        lobbies_table.setItem(0, 0, error_item)

    def filter_lobbies(self, query: str):
        lobbies_table = self.lobbies_tab.lobbies_table
        lobbies_table.setRowCount(0); lobbies_table.setSortingEnabled(False)
        query = query.lower()
        filtered_lobbies = [l for l in self.all_lobbies if query in l.get('name', '').lower() or query in l.get('map', '').lower()]
        def is_watched(lobby):
            name = lobby.get('name', '').lower(); map_name = lobby.get('map', '').lower()
            return any(k in name or k in map_name for k in self.watchlist)
        sorted_lobbies = sorted(filtered_lobbies, key=is_watched, reverse=True)
        lobbies_table.setRowCount(len(sorted_lobbies))
        for row, lobby in enumerate(sorted_lobbies):
            watched = any(k in lobby.get('name', '').lower() or k in lobby.get('map', '').lower() for k in self.watchlist)
            lobbies_table.setItem(row, 0, QTableWidgetItem(lobby.get('name', 'N/A')))
            lobbies_table.setItem(row, 1, QTableWidgetItem(lobby.get('map', 'N/A')))
            players = f"{lobby.get('slotsTaken', '?')}/{lobby.get('slotsTotal', '?')}"
            lobbies_table.setItem(row, 2, AlignedTableWidgetItem(players))
            host = lobby.get('host', lobby.get('server', 'N/A'))
            lobbies_table.setItem(row, 3, AlignedTableWidgetItem(host))
            if watched:
                for col in range(lobbies_table.columnCount()):
                    lobbies_table.item(row, col).setBackground(QColor("#3A5F0B"))
        lobbies_table.setSortingEnabled(True)

    def toggle_watchlist_visibility(self):
        is_visible = self.lobbies_tab.watchlist_group.isVisible()
        self.lobbies_tab.watchlist_group.setVisible(not is_visible)

    def add_to_watchlist(self):
        keyword = self.lobbies_tab.watchlist_input.text().strip().lower()
        if keyword and keyword not in self.watchlist:
            self.watchlist.append(keyword)
            self.lobbies_tab.watchlist_widget.addItem(keyword)
            self.lobbies_tab.watchlist_input.clear()
            self.filter_lobbies(self.lobbies_tab.lobby_search_bar.text())

    def remove_from_watchlist(self):
        selected_items = self.lobbies_tab.watchlist_widget.selectedItems()
        if not selected_items: return
        for item in selected_items:
            self.watchlist.remove(item.text())
            self.lobbies_tab.watchlist_widget.takeItem(self.lobbies_tab.watchlist_widget.row(item))
        self.filter_lobbies(self.lobbies_tab.lobby_search_bar.text())

    def set_volume(self, value: int):
        self.volume = value
        self.main_window.set_volume(value)

    def select_ping_sound(self, sound_file: str):
        self.selected_sound = sound_file
        self.main_window.play_specific_sound(sound_file)
        self.main_window.update_ping_button_styles()