import os
import customtkinter as ctk
from app.config import config
from app.player import player
from app.downloader import downloader
from app.ui.search_tab import SearchTab
from app.ui.url_tab import UrlTab
from app.ui.queue_tab import QueueTab
from app.ui.library_tab import LibraryTab
from app.ui.settings_tab import SettingsTab

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Kanade 奏 — Hi-Res Lossless Downloader")
        self.geometry("1180x760")
        self.minsize(1000, 680)

        # Main Layout: Sidebar (Left) + Content (Center/Right) + Player Dock (Bottom)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Player dock
        self.grid_columnconfigure(0, weight=0)  # Sidebar
        self.grid_columnconfigure(1, weight=1)  # Tab Content

        self._build_sidebar()
        self._build_content_area()
        self._build_player_dock()

        # Select initial tab
        self.select_tab("search")

        # Periodically refresh player state and queue counter
        self._poll_status()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=("#12161f", "#0d1117"))
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(6, weight=1)  # Spacer push drive widget to bottom

        # Branding Header
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, padx=15, pady=(20, 20), sticky="ew")

        brand_title = ctk.CTkLabel(
            brand_frame,
            text="🌸 Kanade 奏",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#38bdf8"
        )
        brand_title.pack(anchor="w")

        brand_sub = ctk.CTkLabel(
            brand_frame,
            text="Hi-Res Lossless & Studio Tagger",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        brand_sub.pack(anchor="w")

        # Nav Buttons
        self.nav_buttons = {}
        tabs_config = [
            ("search", "🔍  Search & Discover"),
            ("url", "🔗  Direct URLs / Web"),
            ("queue", "⏳  Download Queue"),
            ("library", "📂  FLAC Library"),
            ("settings", "⚙️  Storage & Settings"),
        ]

        for idx, (key, label) in enumerate(tabs_config, start=1):
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                height=42,
                corner_radius=8,
                fg_color="transparent",
                hover_color=("#1f2937", "#161b22"),
                anchor="w",
                font=ctk.CTkFont(size=13, weight="normal"),
                command=lambda k=key: self.select_tab(k)
            )
            btn.grid(row=idx, column=0, padx=12, pady=4, sticky="ew")
            self.nav_buttons[key] = btn

        # Spacer row 6
        spacer = ctk.CTkFrame(sidebar, fg_color="transparent")
        spacer.grid(row=6, column=0, sticky="nsew")

        # Drive Info Widget at bottom of sidebar
        self.drive_widget = ctk.CTkFrame(sidebar, corner_radius=8, fg_color=("#1a1f28", "#161b22"))
        self.drive_widget.grid(row=7, column=0, padx=12, pady=15, sticky="ew")

        self.drive_title_lbl = ctk.CTkLabel(
            self.drive_widget,
            text="Storage Drive",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#cbd5e1"
        )
        self.drive_title_lbl.pack(anchor="w", padx=10, pady=(8, 2))

        self.drive_free_lbl = ctk.CTkLabel(
            self.drive_widget,
            text="Checking drive...",
            font=ctk.CTkFont(size=11),
            text_color="#38bdf8"
        )
        self.drive_free_lbl.pack(anchor="w", padx=10, pady=(0, 8))

        self._update_sidebar_drive_info()

    def _update_sidebar_drive_info(self):
        info = config.get_drive_info()
        drive = info.get("drive", "C:")
        free_gb = info.get("free_gb", 0)
        self.drive_free_lbl.configure(text=f"Drive [{drive}]  •  {free_gb:.1f} GB Free")

    def _build_content_area(self):
        self.content_container = ctk.CTkFrame(self, corner_radius=0, fg_color=("#0f1218", "#080b0f"))
        self.content_container.grid(row=0, column=1, sticky="nsew")
        self.content_container.grid_rowconfigure(0, weight=1)
        self.content_container.grid_columnconfigure(0, weight=1)

        # Initialize all tab views
        self.tabs = {}
        self.tabs["search"] = SearchTab(self.content_container, on_queue_updated=self._on_queue_updated)
        self.tabs["url"] = UrlTab(self.content_container, on_queue_updated=self._on_queue_updated)
        self.tabs["queue"] = QueueTab(self.content_container)
        self.tabs["library"] = LibraryTab(self.content_container)
        self.tabs["settings"] = SettingsTab(self.content_container, on_settings_changed=self._on_settings_changed)

        for tab in self.tabs.values():
            tab.grid(row=0, column=0, sticky="nsew")

    def _build_player_dock(self):
        player_frame = ctk.CTkFrame(self, height=68, corner_radius=0, fg_color=("#161b22", "#0d1117"))
        player_frame.grid(row=1, column=0, columnspan=2, sticky="ew")

        player_inner = ctk.CTkFrame(player_frame, fg_color="transparent")
        player_inner.pack(fill="both", expand=True, padx=20, pady=8)

        # Track Info (Left)
        track_info_col = ctk.CTkFrame(player_inner, fg_color="transparent")
        track_info_col.pack(side="left", fill="both", expand=True)

        self.player_title = ctk.CTkLabel(
            track_info_col,
            text="Ready to Audition",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f1f5f9",
            anchor="w"
        )
        self.player_title.pack(anchor="w")

        self.player_artist = ctk.CTkLabel(
            track_info_col,
            text="Click '▶ Preview' on any track or '▶ Play' in your FLAC Library",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w"
        )
        self.player_artist.pack(anchor="w")

        # Playback Controls (Center)
        controls_col = ctk.CTkFrame(player_inner, fg_color="transparent")
        controls_col.pack(side="left", padx=20)

        self.play_pause_btn = ctk.CTkButton(
            controls_col,
            text="⏸ Pause",
            width=80,
            height=34,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._toggle_playback
        )
        self.play_pause_btn.pack(side="left", padx=5)

        stop_btn = ctk.CTkButton(
            controls_col,
            text="⏹ Stop",
            width=70,
            height=34,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._stop_playback
        )
        stop_btn.pack(side="left", padx=5)

        # Volume Controls (Right)
        vol_col = ctk.CTkFrame(player_inner, fg_color="transparent")
        vol_col.pack(side="right")

        vol_lbl = ctk.CTkLabel(vol_col, text="🔊", font=ctk.CTkFont(size=14))
        vol_lbl.pack(side="left", padx=(0, 6))

        self.vol_slider = ctk.CTkSlider(
            vol_col,
            from_=0,
            to=1,
            width=110,
            command=lambda v: player.set_volume(v)
        )
        self.vol_slider.set(0.85)
        self.vol_slider.pack(side="left")

    def _toggle_playback(self):
        is_playing = player.toggle_play_pause()
        self.play_pause_btn.configure(text="⏸ Pause" if is_playing else "▶ Play")

    def _stop_playback(self):
        player.stop()
        self.player_title.configure(text="Playback Stopped")
        self.player_artist.configure(text="Select another track to audition")
        self.play_pause_btn.configure(text="▶ Play")

    def select_tab(self, key):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=("#2563eb", "#1d4ed8"), font=ctk.CTkFont(size=13, weight="bold"))
                self.tabs[k].tkraise()
            else:
                btn.configure(fg_color="transparent", font=ctk.CTkFont(size=13, weight="normal"))

        if key == "library":
            self.tabs["library"].refresh_library()
        elif key == "settings":
            self.tabs["settings"].refresh_drive_info()

    def _on_queue_updated(self):
        self._update_queue_badge()

    def _on_settings_changed(self):
        self._update_sidebar_drive_info()

    def _update_queue_badge(self):
        with downloader.queue_lock:
            active = sum(1 for t in downloader.tasks if t.status in ("queued", "downloading", "converting", "inspecting"))
        btn = self.nav_buttons.get("queue")
        if btn:
            if active > 0:
                btn.configure(text=f"⏳  Queue ({active})")
            else:
                btn.configure(text="⏳  Download Queue")

    def _poll_status(self):
        # Update player labels if current track changed
        cur = player.current_track
        if cur:
            title = cur.get("title", "Audio Stream")
            artist = cur.get("artist", "")
            album = cur.get("album", "")
            source = cur.get("source", "Audio")
            self.player_title.configure(text=f"{title}")
            self.player_artist.configure(text=f"{artist} • {album} [{source}]")
            self.play_pause_btn.configure(text="▶ Play" if player.is_paused else "⏸ Pause")

        self._update_queue_badge()
        self.after(800, self._poll_status)

def launch_app():
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    launch_app()
