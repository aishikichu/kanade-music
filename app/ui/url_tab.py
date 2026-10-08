import re
import customtkinter as ctk
from app.downloader import downloader

class UrlTab(ctk.CTkFrame):
    def __init__(self, master, on_queue_updated=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_queue_updated = on_queue_updated
        self._build_ui()

    def _build_ui(self):
        # Header Box
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1f242d", "#161b22"))
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Direct URL & Batch Stream Downloader",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#38bdf8", "#38bdf8")
        )
        title_lbl.pack(anchor="w", padx=15, pady=(12, 4))

        subtitle_lbl = ctk.CTkLabel(
            header_frame,
            text="Paste links from YouTube, YouTube Music, SoundCloud, Bandcamp, web streams, or direct audio URLs. The app will extract lossless audio and automatically tag with official studio album art.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        subtitle_lbl.pack(anchor="w", padx=15, pady=(0, 10))

        # Input Area Frame
        input_container = ctk.CTkFrame(self, corner_radius=10, fg_color=("#161b22", "#0d1117"))
        input_container.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        entry_lbl = ctk.CTkLabel(
            input_container,
            text="Enter URL(s) - One link per line for batch downloading:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#e2e8f0"
        )
        entry_lbl.pack(anchor="w", padx=15, pady=(12, 6))

        self.url_textbox = ctk.CTkTextbox(
            input_container,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none"
        )
        self.url_textbox.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self.url_textbox.insert("1.0", "# Paste music URLs here, for example:\n# https://www.youtube.com/watch?v=...\n# https://soundcloud.com/...\n# https://artist.bandcamp.com/track/...\n")

        # Controls Row
        controls_frame = ctk.CTkFrame(input_container, fg_color="transparent")
        controls_frame.pack(fill="x", padx=15, pady=(0, 12))

        self.auto_enrich_var = ctk.BooleanVar(value=True)
        self.enrich_chk = ctk.CTkCheckBox(
            controls_frame,
            text="Auto-match studio metadata & HD album art",
            variable=self.auto_enrich_var,
            font=ctk.CTkFont(size=12)
        )
        self.enrich_chk.pack(side="left", padx=(0, 15))

        self.clear_btn = ctk.CTkButton(
            controls_frame,
            text="Clear",
            width=80,
            height=36,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self.clear_input
        )
        self.clear_btn.pack(side="right", padx=(10, 0))

        self.queue_btn = ctk.CTkButton(
            controls_frame,
            text="⬇ Add to Download Queue",
            width=220,
            height=36,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self.process_urls
        )
        self.queue_btn.pack(side="right")

        # Status Label
        self.status_lbl = ctk.CTkLabel(
            self,
            text="Ready. Paste one or more links above and click 'Add to Download Queue'.",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_lbl.pack(anchor="w", padx=20, pady=(0, 10))

    def clear_input(self):
        self.url_textbox.delete("1.0", "end")

    def process_urls(self):
        content = self.url_textbox.get("1.0", "end").strip()
        lines = content.splitlines()
        valid_urls = []

        url_regex = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Match URLs
            if url_regex.match(line):
                valid_urls.append(line)
            else:
                # Check if there is an embedded url in the line
                found = re.findall(r"https?://[^\s]+", line)
                for u in found:
                    valid_urls.append(u)

        if not valid_urls:
            self.status_lbl.configure(text="No valid URLs found in the text box. Please paste valid web links starting with http:// or https://", text_color="#f87171")
            return

        added_count = 0
        for url in valid_urls:
            downloader.add_url_to_queue(url)
            added_count += 1

        self.status_lbl.configure(text=f"✓ Added {added_count} audio stream(s) to the FLAC download queue!", text_color="#34d399")
        self.clear_input()

        if self.on_queue_updated:
            self.on_queue_updated()
