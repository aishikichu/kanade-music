import os
import threading
import customtkinter as ctk
from PIL import Image
from app.metadata import search_music_all, fetch_pil_image
from app.downloader import downloader
from app.player import player
from app.config import config

class SearchTab(ctk.CTkFrame):
    def __init__(self, master, on_queue_updated=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_queue_updated = on_queue_updated
        self.current_results = []
        self.thumbnail_cache = {}

        self._build_ui()

    def _build_ui(self):
        # Header / Search Control Bar
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1f242d", "#161b22"))
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Universal Music Search & Lossless Grabber",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#38bdf8", "#38bdf8")
        )
        title_lbl.pack(anchor="w", padx=15, pady=(12, 4))

        subtitle_lbl = ctk.CTkLabel(
            header_frame,
            text="Search studio catalog for songs, artists, or albums. Preview tracks and download in pristine FLAC with full metadata & HD cover art.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        subtitle_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # Search Input Row
        search_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        search_row.pack(fill="x", padx=15, pady=(0, 12))

        self.search_entry = ctk.CTkEntry(
            search_row,
            placeholder_text="Enter artist, song title, or album (e.g. Queen Bohemian Rhapsody, Daft Punk, The Weeknd)...",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self.start_search())

        self.search_btn = ctk.CTkButton(
            search_row,
            text="🔍 Search Catalog",
            width=140,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.start_search
        )
        self.search_btn.pack(side="left", padx=(0, 10))

        self.download_all_btn = ctk.CTkButton(
            search_row,
            text="⬇ Download All",
            width=130,
            height=38,
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled",
            command=self.download_all_results
        )
        self.download_all_btn.pack(side="left")

        # Status and Filter Bar
        self.status_bar = ctk.CTkLabel(
            self,
            text="Ready to search millions of tracks worldwide.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_bar.pack(anchor="w", padx=20, pady=(0, 5))

        # Results Scrollable Frame
        self.results_scroll = ctk.CTkScrollableFrame(self, corner_radius=10, fg_color=("#161b22", "#0d1117"))
        self.results_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def start_search(self):
        query = self.search_entry.get().strip()
        if not query:
            return

        self.search_btn.configure(state="disabled", text="Searching...")
        self.status_bar.configure(text=f"Searching studio catalogs for '{query}'...", text_color="#38bdf8")
        self.download_all_btn.configure(state="disabled")

        # Clear existing cards
        for widget in self.results_scroll.winfo_children():
            widget.destroy()

        def _do_search():
            res_res = config.get("artwork_resolution", "1400x1400")
            results = search_music_all(query, limit_per_source=15, resolution=res_res)
            self.after(0, lambda: self._on_search_done(results, query))

        threading.Thread(target=_do_search, daemon=True).start()

    def _on_search_done(self, results, query):
        self.search_btn.configure(state="normal", text="🔍 Search Catalog")
        self.current_results = results

        if not results:
            self.status_bar.configure(text=f"No results found for '{query}'. Try a different song or artist name.", text_color="#f87171")
            no_res_lbl = ctk.CTkLabel(self.results_scroll, text="No tracks matched your search.", font=ctk.CTkFont(size=14))
            no_res_lbl.pack(pady=40)
            return

        self.status_bar.configure(text=f"Found {len(results)} tracks for '{query}'. Click 'Download' or '▶ Preview' to audition.", text_color="#34d399")
        self.download_all_btn.configure(state="normal")

        # Render cards
        for idx, item in enumerate(results):
            self._render_track_card(idx, item)

    def _render_track_card(self, idx, item):
        card = ctk.CTkFrame(self.results_scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        card.pack(fill="x", padx=8, pady=5)

        # Thumbnail Label
        thumb_lbl = ctk.CTkLabel(card, text="[Cover]", width=60, height=60, fg_color=("#30363d", "#21262d"), corner_radius=6)
        thumb_lbl.pack(side="left", padx=10, pady=8)

        # Async load thumbnail
        thumb_url = item.get("thumbnail_url")
        if thumb_url:
            def _load_thumb(label=thumb_lbl, url=thumb_url):
                pil_img = fetch_pil_image(url, size=(60, 60))
                if pil_img:
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(60, 60))
                    self.after(0, lambda: label.configure(image=ctk_img, text=""))
            threading.Thread(target=_load_thumb, daemon=True).start()

        # Track Information Column
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        title_text = item.get("title", "Unknown Track")
        artist_text = item.get("artist", "Unknown Artist")
        album_text = item.get("album", "Unknown Album")
        year_text = f" ({item.get('year')})" if item.get("year") else ""
        genre_text = item.get("genre", "Music")
        dur_sec = item.get("duration_sec", 0)
        dur_str = f"{dur_sec // 60}:{dur_sec % 60:02d}" if dur_sec > 0 else ""

        title_lbl = ctk.CTkLabel(info_frame, text=title_text, font=ctk.CTkFont(size=14, weight="bold"), anchor="w")
        title_lbl.pack(anchor="w")

        meta_line1 = f"{artist_text} • {album_text}{year_text}"
        meta_lbl = ctk.CTkLabel(info_frame, text=meta_line1, font=ctk.CTkFont(size=12), text_color="#cbd5e1", anchor="w")
        meta_lbl.pack(anchor="w")

        meta_line2 = f"Genre: {genre_text} | Duration: {dur_str} | Source: {item.get('source', 'Online Catalog')}"
        sub_lbl = ctk.CTkLabel(info_frame, text=meta_line2, font=ctk.CTkFont(size=11), text_color="gray", anchor="w")
        sub_lbl.pack(anchor="w")

        # Action Buttons Column
        actions_frame = ctk.CTkFrame(card, fg_color="transparent")
        actions_frame.pack(side="right", padx=10, pady=8)

        # Preview button if preview_url is present
        preview_url = item.get("preview_url")
        if preview_url:
            preview_btn = ctk.CTkButton(
                actions_frame,
                text="▶ Preview",
                width=85,
                height=32,
                fg_color="#3b82f6",
                hover_color="#2563eb",
                command=lambda it=item: self._preview_track(it)
            )
            preview_btn.pack(side="left", padx=5)

        # Download button
        download_btn = ctk.CTkButton(
            actions_frame,
            text="⬇ Download",
            width=110,
            height=32,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        download_btn.configure(command=lambda it=item, btn=download_btn: self._download_single(it, btn))
        download_btn.pack(side="left", padx=5)

    def _preview_track(self, item):
        url = item.get("preview_url")
        if url:
            self.status_bar.configure(text=f"Auditioning studio preview: '{item.get('title')}' by {item.get('artist')}...", text_color="#38bdf8")
            player.play_url(url, item)

    def _download_single(self, item, btn):
        btn.configure(state="disabled", text="Queued...", fg_color="#6b7280")
        self.status_bar.configure(text=f"Added '{item.get('title')}' to download queue.", text_color="#34d399")

        def on_prog(task_id, status_str, pct, spd, eta):
            if pct < 100:
                self.after(0, lambda: btn.configure(text=f"{int(pct)}% FLAC"))
            else:
                self.after(0, lambda: btn.configure(text="✓ Saved", fg_color="#059669"))

        def on_comp(task):
            self.after(0, lambda: btn.configure(text="✓ Saved FLAC", fg_color="#059669"))
            if self.on_queue_updated:
                self.after(0, self.on_queue_updated)

        def on_err(task, err):
            self.after(0, lambda: btn.configure(text="Failed", fg_color="#ef4444", state="normal"))

        downloader.add_search_item_to_queue(item, on_progress=on_prog, on_complete=on_comp, on_error=on_err)
        if self.on_queue_updated:
            self.on_queue_updated()

    def download_all_results(self):
        if not self.current_results:
            return
        count = len(self.current_results)
        self.status_bar.configure(text=f"Adding all {count} tracks to FLAC download queue...", text_color="#34d399")
        for item in self.current_results:
            downloader.add_search_item_to_queue(item)
        if self.on_queue_updated:
            self.on_queue_updated()
