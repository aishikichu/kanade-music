import os
import customtkinter as ctk
from tkinter import filedialog
from app.config import config

class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, on_settings_changed=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_settings_changed = on_settings_changed
        self._build_ui()
        self.refresh_drive_info()

    def _build_ui(self):
        # Header Box
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1f242d", "#161b22"))
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Storage Drive & Audio Preferences",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#38bdf8", "#38bdf8")
        )
        title_lbl.pack(anchor="w", padx=15, pady=(12, 4))

        subtitle_lbl = ctk.CTkLabel(
            header_frame,
            text="Configure your target storage drive, folder layout, metadata tags, and audiophile compression settings.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        subtitle_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # Main Settings Container (Scrollable)
        scroll = ctk.CTkScrollableFrame(self, corner_radius=10, fg_color=("#161b22", "#0d1117"))
        scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # ---------------- Section 1: Storage & Drive Selection ----------------
        storage_card = ctk.CTkFrame(scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        storage_card.pack(fill="x", padx=10, pady=8)

        sec1_title = ctk.CTkLabel(
            storage_card,
            text="📁 Destination Storage Drive & Directory",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#38bdf8"
        )
        sec1_title.pack(anchor="w", padx=15, pady=(12, 6))

        path_row = ctk.CTkFrame(storage_card, fg_color="transparent")
        path_row.pack(fill="x", padx=15, pady=(0, 10))

        self.path_entry = ctk.CTkEntry(
            path_row,
            height=36,
            font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.path_entry.insert(0, config.get("download_dir", ""))
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        browse_btn = ctk.CTkButton(
            path_row,
            text="📁 Browse Drive...",
            width=140,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.choose_directory
        )
        browse_btn.pack(side="left")

        # Live Drive Usage Widget
        drive_box = ctk.CTkFrame(storage_card, corner_radius=6, fg_color=("#1a1f28", "#11151c"))
        drive_box.pack(fill="x", padx=15, pady=(0, 15))

        self.drive_label = ctk.CTkLabel(
            drive_box,
            text="Analyzing drive storage...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e2e8f0"
        )
        self.drive_label.pack(anchor="w", padx=12, pady=(10, 4))

        self.storage_pbar = ctk.CTkProgressBar(drive_box, height=10, corner_radius=5)
        self.storage_pbar.set(0)
        self.storage_pbar.pack(fill="x", padx=12, pady=(0, 8))

        self.drive_details = ctk.CTkLabel(
            drive_box,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.drive_details.pack(anchor="w", padx=12, pady=(0, 10))

        # ---------------- Section 1.5: Audio Quality & Bit-Depth ----------------
        quality_card = ctk.CTkFrame(scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        quality_card.pack(fill="x", padx=10, pady=8)

        sec15_title = ctk.CTkLabel(
            quality_card,
            text="👑 Audio Format & Bit-Depth Preset",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#38bdf8"
        )
        sec15_title.pack(anchor="w", padx=15, pady=(12, 6))

        quality_options = [
            "👑 24-bit Hi-Res Studio Master FLAC (24-bit / 48 kHz - Pure Studio Master)",
            "🎧 16-bit Lossless CD FLAC (16-bit / 44.1 kHz - Red Book Standard)",
            "🌟 Hi-Fi Lossless First (Queries Lossless Archives, Auto 24/16-bit FLAC)",
            "⚡ Native Clean M4A (Lightweight ~4 MB AAC Stream)",
        ]
        self.quality_key_map = {
            quality_options[0]: "flac_24bit",
            quality_options[1]: "flac_16bit",
            quality_options[2]: "hifi_first",
            quality_options[3]: "native_clean",
        }
        self.key_to_quality_map = {v: k for k, v in self.quality_key_map.items()}

        curr_qual_key = config.get("audio_quality_preset", "flac_24bit")
        curr_qual_display = self.key_to_quality_map.get(curr_qual_key, quality_options[0])

        self.quality_menu = ctk.CTkOptionMenu(
            quality_card,
            values=quality_options,
            height=34,
            font=ctk.CTkFont(size=12)
        )
        self.quality_menu.set(curr_qual_display)
        self.quality_menu.pack(fill="x", padx=15, pady=(0, 15))

        # ---------------- Section 2: Folder Organization Format ----------------
        format_card = ctk.CTkFrame(scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        format_card.pack(fill="x", padx=10, pady=8)

        sec2_title = ctk.CTkLabel(
            format_card,
            text="🗂 Library Folder Structure",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#38bdf8"
        )
        sec2_title.pack(anchor="w", padx=15, pady=(12, 6))

        template_options = [
            "Audiophile: {Artist} / {Album} ({Year}) / {Track:02d} - {Title}.flac",
            "Standard: {Artist} / {Album} / {Track:02d} - {Title}.flac",
            "Artist Folders: {Artist} / {Track:02d} - {Title}.flac",
            "Flat: {Artist} - {Title}.flac",
        ]
        self.template_key_map = {
            template_options[0]: "audiophile",
            template_options[1]: "artist_album",
            template_options[2]: "artist_track",
            template_options[3]: "flat",
        }
        self.key_to_template_map = {v: k for k, v in self.template_key_map.items()}

        current_key = config.get("folder_template", "audiophile")
        current_display = self.key_to_template_map.get(current_key, template_options[0])

        self.template_menu = ctk.CTkOptionMenu(
            format_card,
            values=template_options,
            height=34,
            font=ctk.CTkFont(size=12)
        )
        self.template_menu.set(current_display)
        self.template_menu.pack(fill="x", padx=15, pady=(0, 15))

        # ---------------- Section 3: Metadata & Cover Art ----------------
        meta_card = ctk.CTkFrame(scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        meta_card.pack(fill="x", padx=10, pady=8)

        sec3_title = ctk.CTkLabel(
            meta_card,
            text="🎨 Album Artwork & Audiophile Tags",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#38bdf8"
        )
        sec3_title.pack(anchor="w", padx=15, pady=(12, 10))

        # Embed Art Switch
        self.embed_art_var = ctk.BooleanVar(value=config.get("embed_cover_art", True))
        self.embed_switch = ctk.CTkSwitch(
            meta_card,
            text="Embed HD Album Art directly inside FLAC header (Picture Block)",
            variable=self.embed_art_var,
            font=ctk.CTkFont(size=13)
        )
        self.embed_switch.pack(anchor="w", padx=15, pady=(0, 10))

        # External cover.jpg Switch
        self.external_cover_var = ctk.BooleanVar(value=config.get("save_external_cover", True))
        self.cover_switch = ctk.CTkSwitch(
            meta_card,
            text="Save external 'cover.jpg' in album directory (Recommended for Foobar2000, Plex, Roon, Car Audio)",
            variable=self.external_cover_var,
            font=ctk.CTkFont(size=13)
        )
        self.cover_switch.pack(anchor="w", padx=15, pady=(0, 15))

        # Artwork Resolution
        art_res_row = ctk.CTkFrame(meta_card, fg_color="transparent")
        art_res_row.pack(fill="x", padx=15, pady=(0, 15))

        res_lbl = ctk.CTkLabel(art_res_row, text="Artwork Download Quality:", font=ctk.CTkFont(size=12))
        res_lbl.pack(side="left", padx=(0, 10))

        self.res_menu = ctk.CTkOptionMenu(
            art_res_row,
            values=["1400x1400 (Studio HD)", "3000x3000 (Ultra Hi-Res)", "1000x1000 (Standard HD)"],
            height=30
        )
        curr_res = config.get("artwork_resolution", "1400x1400")
        if curr_res == "3000x3000":
            self.res_menu.set("3000x3000 (Ultra Hi-Res)")
        elif curr_res == "1000x1000":
            self.res_menu.set("1000x1000 (Standard HD)")
        else:
            self.res_menu.set("1400x1400 (Studio HD)")
        self.res_menu.pack(side="left")

        # ---------------- Section 4: Compression Level ----------------
        flac_card = ctk.CTkFrame(scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        flac_card.pack(fill="x", padx=10, pady=8)

        sec4_title = ctk.CTkLabel(
            flac_card,
            text="⚡ FLAC Lossless Encoding Level",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#38bdf8"
        )
        sec4_title.pack(anchor="w", padx=15, pady=(12, 6))

        slider_row = ctk.CTkFrame(flac_card, fg_color="transparent")
        slider_row.pack(fill="x", padx=15, pady=(0, 15))

        self.comp_slider = ctk.CTkSlider(
            slider_row,
            from_=0,
            to=8,
            number_of_steps=8,
            command=self._on_slider_change
        )
        self.comp_slider.set(config.get("flac_compression_level", 8))
        self.comp_slider.pack(side="left", fill="x", expand=True, padx=(0, 15))

        self.comp_label = ctk.CTkLabel(
            slider_row,
            text=f"Level {int(self.comp_slider.get())} (Max Compression)",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=180
        )
        self.comp_label.pack(side="left")

        # ---------------- Section 5: Save Actions ----------------
        save_card = ctk.CTkFrame(scroll, fg_color="transparent")
        save_card.pack(fill="x", padx=10, pady=15)

        self.save_btn = ctk.CTkButton(
            save_card,
            text="💾 Save & Apply Settings",
            height=40,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.save_all_settings
        )
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.save_status = ctk.CTkLabel(
            save_card,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#34d399"
        )
        self.save_status.pack(side="left")

    def _on_slider_change(self, val):
        lvl = int(val)
        desc = "Fastest" if lvl == 0 else "Balanced" if lvl == 5 else "Max Compression" if lvl == 8 else f"Level {lvl}"
        self.comp_label.configure(text=f"Level {lvl} ({desc})")

    def choose_directory(self):
        cur = self.path_entry.get().strip() or config.get("download_dir")
        chosen = filedialog.askdirectory(initialdir=cur if os.path.exists(cur) else None, title="Select Storage Drive or Folder for Hi-Res FLAC")
        if chosen:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, os.path.normpath(chosen))
            self.refresh_drive_info(chosen)

    def refresh_drive_info(self, path=None):
        target = path or self.path_entry.get().strip() or config.get("download_dir")
        info = config.get_drive_info(target)

        drive_letter = info.get("drive", "")
        free_gb = info.get("free_gb", 0)
        total_gb = info.get("total_gb", 0)
        used_gb = info.get("used_gb", 0)
        pct = info.get("percent_used", 0)

        self.drive_label.configure(
            text=f"Drive [{drive_letter}] Status: {free_gb:.1f} GB Free of {total_gb:.1f} GB Total"
        )
        self.storage_pbar.set(pct / 100.0)
        self.storage_pbar.configure(
            progress_color="#ef4444" if pct > 90 else "#f59e0b" if pct > 75 else "#10b981"
        )
        self.drive_details.configure(
            text=f"Selected Path: {info.get('path')}  •  Used: {used_gb:.1f} GB ({pct:.1f}%)"
        )

    def save_all_settings(self):
        new_dir = self.path_entry.get().strip()
        if not new_dir:
            new_dir = config.get("download_dir")

        os.makedirs(new_dir, exist_ok=True)
        config.set("download_dir", new_dir)

        selected_tmpl_text = self.template_menu.get()
        tmpl_key = self.template_key_map.get(selected_tmpl_text, "audiophile")
        config.set("folder_template", tmpl_key)

        selected_qual_text = self.quality_menu.get()
        qual_key = self.quality_key_map.get(selected_qual_text, "flac_24bit")
        config.set("audio_quality_preset", qual_key)

        config.set("embed_cover_art", self.embed_art_var.get())
        config.set("save_external_cover", self.external_cover_var.get())

        res_text = self.res_menu.get()
        res_val = "3000x3000" if "3000x3000" in res_text else "1000x1000" if "1000x1000" in res_text else "1400x1400"
        config.set("artwork_resolution", res_val)

        config.set("flac_compression_level", int(self.comp_slider.get()))

        self.refresh_drive_info(new_dir)
        self.save_status.configure(text="✓ Preferences saved successfully!")
        self.after(3000, lambda: self.save_status.configure(text=""))

        if self.on_settings_changed:
            self.on_settings_changed()
