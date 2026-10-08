import os
import io
import subprocess
import threading
import customtkinter as ctk
from PIL import Image
from mutagen.flac import FLAC
from app.config import config
from app.player import player

class LibraryTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.library_files = []
        self._build_ui()
        self.refresh_library()

    def _build_ui(self):
        # Header Box
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1f242d", "#161b22"))
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Downloaded Hi-Res FLAC Library",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#38bdf8", "#38bdf8")
        )
        title_lbl.pack(anchor="w", padx=15, pady=(12, 4))

        controls_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        controls_row.pack(fill="x", padx=15, pady=(0, 10))

        self.summary_lbl = ctk.CTkLabel(
            controls_row,
            text="Scanning destination drive for FLAC audio files...",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.summary_lbl.pack(side="left")

        self.refresh_btn = ctk.CTkButton(
            controls_row,
            text="🔄 Refresh Library",
            width=130,
            height=30,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=12),
            command=self.refresh_library
        )
        self.refresh_btn.pack(side="right", padx=(10, 0))

        self.open_folder_btn = ctk.CTkButton(
            controls_row,
            text="📂 Open Music Folder",
            width=150,
            height=30,
            fg_color="#374151",
            hover_color="#4b5563",
            font=ctk.CTkFont(size=12),
            command=self.open_music_directory
        )
        self.open_folder_btn.pack(side="right")

        # Search / Filter Bar
        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", padx=15, pady=(0, 8))

        self.filter_entry = ctk.CTkEntry(
            filter_row,
            placeholder_text="Filter library by title, artist, or album...",
            height=32,
            font=ctk.CTkFont(size=12)
        )
        self.filter_entry.pack(fill="x")
        self.filter_entry.bind("<KeyRelease>", lambda e: self.filter_display())

        # Scrollable track listing
        self.list_scroll = ctk.CTkScrollableFrame(self, corner_radius=10, fg_color=("#161b22", "#0d1117"))
        self.list_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def open_music_directory(self):
        target = config.get("download_dir")
        if os.path.exists(target):
            try:
                os.startfile(target)
            except Exception as e:
                print(f"Error opening folder: {e}")

    def refresh_library(self):
        self.summary_lbl.configure(text="Scanning audio files on disk...", text_color="#38bdf8")
        self.refresh_btn.configure(state="disabled")

        def _scan():
            base_dir = config.get("download_dir")
            flacs = []
            if os.path.exists(base_dir):
                for root, _, files in os.walk(base_dir):
                    for file in files:
                        if file.lower().endswith(".flac"):
                            full_path = os.path.join(root, file)
                            try:
                                size_mb = os.path.getsize(full_path) / (1024 * 1024)
                                audio = FLAC(full_path)
                                title = audio.get("TITLE", [os.path.splitext(file)[0]])[0]
                                artist = audio.get("ARTIST", ["Unknown Artist"])[0]
                                album = audio.get("ALBUM", ["Unknown Album"])[0]
                                year = audio.get("DATE", audio.get("YEAR", [""]))[0]
                                track_no = audio.get("TRACKNUMBER", ["1"])[0]
                                sample_rate = audio.info.sample_rate
                                bits = audio.info.bits_per_sample
                                length = audio.info.length

                                has_art = len(audio.pictures) > 0
                                art_data = audio.pictures[0].data if has_art else None

                                flacs.append({
                                    "path": full_path,
                                    "filename": file,
                                    "title": title,
                                    "artist": artist,
                                    "album": album,
                                    "year": year,
                                    "track_no": track_no,
                                    "sample_rate": sample_rate,
                                    "bits": bits,
                                    "length_sec": int(length),
                                    "size_mb": round(size_mb, 1),
                                    "art_bytes": art_data,
                                })
                            except Exception as e:
                                # Fallback if tag reading fails
                                flacs.append({
                                    "path": full_path,
                                    "filename": file,
                                    "title": os.path.splitext(file)[0],
                                    "artist": "Local Audio",
                                    "album": "",
                                    "year": "",
                                    "track_no": "1",
                                    "sample_rate": 44100,
                                    "bits": 16,
                                    "length_sec": 0,
                                    "size_mb": round(os.path.getsize(full_path)/(1024*1024), 1),
                                    "art_bytes": None,
                                })
            self.after(0, lambda: self._on_scan_done(flacs))

        threading.Thread(target=_scan, daemon=True).start()

    def _on_scan_done(self, flacs):
        self.library_files = flacs
        self.refresh_btn.configure(state="normal")
        total_size = sum(f["size_mb"] for f in flacs)
        self.summary_lbl.configure(
            text=f"{len(flacs)} lossless FLAC track(s) found ({total_size:.1f} MB total storage)",
            text_color="#34d399"
        )
        self.filter_display()

    def filter_display(self):
        query = self.filter_entry.get().strip().lower()
        for w in self.list_scroll.winfo_children():
            w.destroy()

        matched = [
            f for f in self.library_files
            if not query or query in f["title"].lower() or query in f["artist"].lower() or query in f["album"].lower()
        ]

        if not matched:
            empty_lbl = ctk.CTkLabel(
                self.list_scroll,
                text="No FLAC audio tracks found in this directory.\nDownload some music from the Search or URLs tab!",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            empty_lbl.pack(pady=40)
            return

        for item in matched:
            self._render_library_row(item)

    def _render_library_row(self, item):
        row = ctk.CTkFrame(self.list_scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        row.pack(fill="x", padx=6, pady=4)

        # Cover Thumbnail
        art_lbl = ctk.CTkLabel(row, text="[FLAC]", width=50, height=50, corner_radius=6, fg_color=("#30363d", "#21262d"))
        art_lbl.pack(side="left", padx=8, pady=6)

        if item.get("art_bytes"):
            try:
                img = Image.open(io.BytesIO(item["art_bytes"]))
                img.thumbnail((50, 50), Image.Resampling.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(50, 50))
                art_lbl.configure(image=ctk_img, text="")
            except Exception:
                pass

        # Track Info
        info_frame = ctk.CTkFrame(row, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=6, pady=6)

        title = item["title"]
        artist = item["artist"]
        album = item["album"]
        year = f" ({item['year']})" if item["year"] else ""
        bits = item["bits"]
        sr_khz = item["sample_rate"] / 1000.0
        dur_sec = item["length_sec"]
        dur_str = f"{dur_sec // 60}:{dur_sec % 60:02d}" if dur_sec > 0 else ""
        size_str = f"{item['size_mb']} MB"

        title_lbl = ctk.CTkLabel(info_frame, text=title, font=ctk.CTkFont(size=13, weight="bold"), anchor="w")
        title_lbl.pack(anchor="w")

        sub_line = f"{artist} • {album}{year}"
        sub_lbl = ctk.CTkLabel(info_frame, text=sub_line, font=ctk.CTkFont(size=11), text_color="#cbd5e1", anchor="w")
        sub_lbl.pack(anchor="w")

        spec_line = f"FLAC {bits}-bit / {sr_khz:.1f} kHz  |  Duration: {dur_str}  |  File Size: {size_str}"
        spec_lbl = ctk.CTkLabel(info_frame, text=spec_line, font=ctk.CTkFont(size=10), text_color="#38bdf8", anchor="w")
        spec_lbl.pack(anchor="w")

        # Action Buttons
        btn_frame = ctk.CTkFrame(row, fg_color="transparent")
        btn_frame.pack(side="right", padx=8, pady=6)

        play_btn = ctk.CTkButton(
            btn_frame,
            text="▶ Play",
            width=75,
            height=30,
            fg_color="#10b981",
            hover_color="#059669",
            command=lambda it=item: player.play_local_file(it["path"], it)
        )
        play_btn.pack(side="left", padx=4)

        open_btn = ctk.CTkButton(
            btn_frame,
            text="📂 Reveal",
            width=75,
            height=30,
            fg_color="#374151",
            hover_color="#4b5563",
            command=lambda p=item["path"]: self._reveal_file(p)
        )
        open_btn.pack(side="left", padx=4)

    def _reveal_file(self, path):
        if path and os.path.exists(path):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(path)}"')
            except Exception as e:
                print(f"Error revealing file: {e}")
