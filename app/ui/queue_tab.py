import os
import subprocess
import customtkinter as ctk
from app.downloader import downloader

class QueueTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.task_widgets = {}
        self._build_ui()
        self._start_poll()

    def _build_ui(self):
        # Header Box
        header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1f242d", "#161b22"))
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Active Download & Encoding Queue",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=("#38bdf8", "#38bdf8")
        )
        title_lbl.pack(anchor="w", padx=15, pady=(12, 4))

        subtitle_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        subtitle_row.pack(fill="x", padx=15, pady=(0, 10))

        self.summary_lbl = ctk.CTkLabel(
            subtitle_row,
            text="0 active downloads | 0 queued | 0 completed",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.summary_lbl.pack(side="left")

        self.clear_btn = ctk.CTkButton(
            subtitle_row,
            text="Clear Finished",
            width=120,
            height=30,
            fg_color="#374151",
            hover_color="#4b5563",
            font=ctk.CTkFont(size=12),
            command=self.clear_finished
        )
        self.clear_btn.pack(side="right")

        # Scrollable Task List
        self.queue_scroll = ctk.CTkScrollableFrame(self, corner_radius=10, fg_color=("#161b22", "#0d1117"))
        self.queue_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def _start_poll(self):
        self.update_queue_ui()
        self.after(600, self._start_poll)

    def update_queue_ui(self):
        with downloader.queue_lock:
            tasks = list(downloader.tasks)

        active = sum(1 for t in tasks if t.status in ("downloading", "inspecting", "converting"))
        queued = sum(1 for t in tasks if t.status == "queued")
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")

        self.summary_lbl.configure(
            text=f"{active} active • {queued} queued • {completed} saved • {failed} failed"
        )

        existing_ids = set(self.task_widgets.keys())
        current_ids = set(t.task_id for t in tasks)

        # Remove deleted widgets
        for tid in existing_ids - current_ids:
            widgets = self.task_widgets.pop(tid, None)
            if widgets and widgets.get("frame"):
                widgets["frame"].destroy()

        # Update or create task rows
        for t in tasks:
            if t.task_id not in self.task_widgets:
                self._create_task_widget(t)
            else:
                self._update_task_widget(t)

    def _create_task_widget(self, task):
        row = ctk.CTkFrame(self.queue_scroll, corner_radius=8, fg_color=("#21262d", "#161b22"))
        row.pack(fill="x", padx=6, pady=5)

        top_line = ctk.CTkFrame(row, fg_color="transparent")
        top_line.pack(fill="x", padx=10, pady=(8, 2))

        title = task.metadata.get("title") or "Streaming Audio"
        artist = task.metadata.get("artist") or "Online Source"
        title_lbl = ctk.CTkLabel(
            top_line,
            text=f"{title} - {artist}",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        title_lbl.pack(side="left", fill="x", expand=True)

        status_badge = ctk.CTkLabel(
            top_line,
            text="Queued",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8"
        )
        status_badge.pack(side="right")

        # Progress bar
        pbar = ctk.CTkProgressBar(row, height=8, corner_radius=4)
        pbar.set(0)
        pbar.pack(fill="x", padx=10, pady=(2, 4))

        # Bottom detail row
        bottom_line = ctk.CTkFrame(row, fg_color="transparent")
        bottom_line.pack(fill="x", padx=10, pady=(0, 6))

        info_lbl = ctk.CTkLabel(
            bottom_line,
            text="Waiting in queue...",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w"
        )
        info_lbl.pack(side="left")

        open_btn = ctk.CTkButton(
            bottom_line,
            text="📂 Open File",
            width=90,
            height=24,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=11),
            command=lambda p=task: self._reveal_file(p.output_file)
        )
        # Hidden until complete
        open_btn.pack_forget()

        self.task_widgets[task.task_id] = {
            "frame": row,
            "title_lbl": title_lbl,
            "status_badge": status_badge,
            "pbar": pbar,
            "info_lbl": info_lbl,
            "open_btn": open_btn,
        }

    def _update_task_widget(self, task):
        w = self.task_widgets.get(task.task_id)
        if not w:
            return

        title = task.metadata.get("title", "Audio Stream")
        artist = task.metadata.get("artist", "Online")
        w["title_lbl"].configure(text=f"{title} - {artist}")

        st = task.status
        pct = task.percent / 100.0

        if st == "queued":
            w["status_badge"].configure(text="Queued", text_color="#94a3b8")
            w["pbar"].set(0)
            w["info_lbl"].configure(text="Waiting for available download worker...")
        elif st == "inspecting":
            w["status_badge"].configure(text="Analyzing...", text_color="#38bdf8")
            w["pbar"].set(0.08)
            w["info_lbl"].configure(text="Inspecting stream and matching studio tags...")
        elif st == "downloading":
            w["status_badge"].configure(text=f"Downloading {task.percent:.0f}%", text_color="#38bdf8")
            w["pbar"].set(min(0.9, pct))
            detail = f"{task.speed}  •  ETA: {task.eta}" if task.speed else "Downloading audio data..."
            w["info_lbl"].configure(text=detail)
        elif st == "converting":
            w["status_badge"].configure(text="Encoding FLAC & Tags...", text_color="#a855f7")
            w["pbar"].set(0.95)
            w["info_lbl"].configure(text="FFmpeg encoding to lossless FLAC and embedding HD cover art...")
        elif st == "completed":
            w["status_badge"].configure(text="✓ Saved FLAC", text_color="#34d399")
            w["pbar"].set(1.0)
            w["pbar"].configure(progress_color="#10b981")
            saved_name = os.path.basename(task.output_file) if task.output_file else "Finished"
            w["info_lbl"].configure(text=f"Saved to: {saved_name}")
            if task.output_file and os.path.exists(task.output_file):
                w["open_btn"].pack(side="right")
        elif st == "failed":
            w["status_badge"].configure(text="Failed", text_color="#f87171")
            w["pbar"].set(0.0)
            w["info_lbl"].configure(text=f"Error: {task.error_msg}")

    def _reveal_file(self, file_path):
        if file_path and os.path.exists(file_path):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(file_path)}"')
            except Exception as e:
                print(f"Error opening explorer: {e}")

    def clear_finished(self):
        with downloader.queue_lock:
            downloader.tasks = [t for t in downloader.tasks if t.status not in ("completed", "failed")]
        self.update_queue_ui()
