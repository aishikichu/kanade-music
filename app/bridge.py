import os
import json
import subprocess
import threading
from app.config import config
from app.metadata import search_music_all
from app.downloader import downloader, DownloadTask
from app.player import player

class AppBridge:
    def __init__(self):
        self.window = None

    def set_window(self, window):
        self.window = window

    # ---------------- Search & Discovery (Async Non-Blocking) ----------------
    def search_music(self, query: str):
        """Asynchronously triggers search in a background thread and pushes results via window.onSearchResults"""
        if not query or not query.strip():
            return {"status": "empty"}

        def _do_search():
            try:
                res_res = config.get("artwork_resolution", "1400x1400")
                results = search_music_all(query.strip(), limit_per_source=15, resolution=res_res)
                if self.window:
                    self.window.evaluate_js(f"window.onSearchResults && window.onSearchResults({json.dumps(results)});")
            except Exception as e:
                print(f"[Bridge Search Error] {e}")
                if self.window:
                    self.window.evaluate_js(f"window.onSearchError && window.onSearchError({json.dumps(str(e))});")

        threading.Thread(target=_do_search, daemon=True).start()
        return {"status": "searching"}

    # ---------------- Downloads ----------------
    def download_track(self, item: dict):
        def _prog(task_id, status_str, pct, spd, eta):
            if self.window:
                try:
                    js = f"window.onTaskProgress && window.onTaskProgress({json.dumps(task_id)}, {pct}, {json.dumps(spd)}, {json.dumps(eta)}, {json.dumps(status_str)});"
                    self.window.evaluate_js(js)
                except Exception:
                    pass

        def _comp(task: DownloadTask):
            if self.window:
                try:
                    js = f"window.onTaskComplete && window.onTaskComplete({json.dumps(task.task_id)}, {json.dumps(task.output_file)});"
                    self.window.evaluate_js(js)
                except Exception:
                    pass

        def _err(task: DownloadTask, err: str):
            if self.window:
                try:
                    js = f"window.onTaskError && window.onTaskError({json.dumps(task.task_id)}, {json.dumps(err)});"
                    self.window.evaluate_js(js)
                except Exception:
                    pass

        task = downloader.add_search_item_to_queue(item, on_progress=_prog, on_complete=_comp, on_error=_err)
        return {"success": True, "task_id": task.task_id}

    def download_url(self, url: str):
        if not url or not url.strip():
            return {"success": False, "error": "Empty URL"}

        def _prog(task_id, status_str, pct, spd, eta):
            if self.window:
                try:
                    js = f"window.onTaskProgress && window.onTaskProgress({json.dumps(task_id)}, {pct}, {json.dumps(spd)}, {json.dumps(eta)}, {json.dumps(status_str)});"
                    self.window.evaluate_js(js)
                except Exception:
                    pass

        def _comp(task: DownloadTask):
            if self.window:
                try:
                    js = f"window.onTaskComplete && window.onTaskComplete({json.dumps(task.task_id)}, {json.dumps(task.output_file)});"
                    self.window.evaluate_js(js)
                except Exception:
                    pass

        def _err(task: DownloadTask, err: str):
            if self.window:
                try:
                    js = f"window.onTaskError && window.onTaskError({json.dumps(task.task_id)}, {json.dumps(err)});"
                    self.window.evaluate_js(js)
                except Exception:
                    pass

        task = downloader.add_url_to_queue(url.strip(), on_progress=_prog, on_complete=_comp, on_error=_err)
        return {"success": True, "task_id": task.task_id}

    def download_batch_urls(self, urls: list):
        added = []
        for u in urls:
            res = self.download_url(u)
            if res.get("success"):
                added.append(res.get("task_id"))
        return {"success": True, "count": len(added), "task_ids": added}

    def resolve_playlist(self, url: str):
        from app.playlist import playlist_resolver
        try:
            pl = playlist_resolver.resolve(url)
            return {"success": True, "playlist": pl.to_dict()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def queue_playlist(self, url: str):
        from app.playlist import playlist_resolver
        try:
            res = playlist_resolver.queue_playlist(url)
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}

    def download_all_tracks(self, tracks: list):
        added = []
        for t in tracks:
            res = self.download_track(t)
            if res.get("success"):
                added.append(res.get("task_id"))
        return {"success": True, "count": len(added)}

    def get_queue(self):
        with downloader.queue_lock:
            tasks = []
            for t in downloader.tasks:
                tasks.append({
                    "task_id": t.task_id,
                    "title": t.metadata.get("title", "Audio Stream"),
                    "artist": t.metadata.get("artist", "Online"),
                    "album": t.metadata.get("album", ""),
                    "artwork_url": t.metadata.get("artwork_url", "") or t.metadata.get("thumbnail_url", ""),
                    "status": t.status,
                    "percent": t.percent,
                    "speed": t.speed,
                    "eta": t.eta,
                    "output_file": t.output_file,
                    "error_msg": t.error_msg,
                })
            return tasks

    def clear_finished_queue(self):
        with downloader.queue_lock:
            downloader.tasks = [t for t in downloader.tasks if t.status not in ("completed", "failed")]
        return {"success": True}

    # ---------------- Drive & Settings ----------------
    def get_settings(self):
        return {
            "config": config.config,
            "drive_info": config.get_drive_info(),
            "available_drives": config.get_available_drives(),
        }

    def save_settings(self, new_cfg: dict):
        for k, v in new_cfg.items():
            config.set(k, v)
        return self.get_settings()

    def select_drive_folder(self):
        cur_dir = config.get("download_dir", "")
        chosen = None
        if self.window:
            import webview
            res = self.window.create_file_dialog(webview.FOLDER_DIALOG, directory=cur_dir)
            if res and len(res) > 0:
                chosen = res[0]
        if not chosen:
            # Fallback to tkinter dialog
            try:
                from tkinter import filedialog
                chosen = filedialog.askdirectory(initialdir=cur_dir, title="Select Storage Drive or Folder")
            except Exception:
                pass

        if chosen:
            chosen_norm = os.path.normpath(chosen)
            config.set("download_dir", chosen_norm)
            os.makedirs(chosen_norm, exist_ok=True)
            return {"success": True, "path": chosen_norm, "settings": self.get_settings()}
        return {"success": False}

    def set_quick_drive(self, drive_letter: str):
        target = f"{drive_letter}\\HiRes Music"
        try:
            os.makedirs(target, exist_ok=True)
            config.set("download_dir", target)
            return {"success": True, "path": target, "settings": self.get_settings()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------------- Library ----------------
    def get_library_async(self):
        """Scans destination drive in a background thread and pushes tracks via window.onLibraryLoaded"""
        def _scan():
            tracks = self.get_library()
            if self.window:
                self.window.evaluate_js(f"window.onLibraryLoaded && window.onLibraryLoaded({json.dumps(tracks)});")

        threading.Thread(target=_scan, daemon=True).start()
        return {"status": "scanning"}

    def get_library(self):
        base_dir = config.get("download_dir")
        tracks = []
        if os.path.exists(base_dir):
            from mutagen.flac import FLAC
            for root, _, files in os.walk(base_dir):
                for f in files:
                    if f.lower().endswith(".flac"):
                        full_path = os.path.join(root, f)
                        try:
                            size_mb = os.path.getsize(full_path) / (1024 * 1024)
                            audio = FLAC(full_path)
                            title = audio.get("TITLE", [os.path.splitext(f)[0]])[0]
                            artist = audio.get("ARTIST", ["Unknown Artist"])[0]
                            album = audio.get("ALBUM", ["Unknown Album"])[0]
                            year = audio.get("DATE", audio.get("YEAR", [""]))[0]
                            sr = audio.info.sample_rate
                            bits = audio.info.bits_per_sample
                            dur = int(audio.info.length)
                            tracks.append({
                                "path": full_path,
                                "filename": f,
                                "title": title,
                                "artist": artist,
                                "album": album,
                                "year": year,
                                "sample_rate": sr,
                                "bits": bits,
                                "duration_sec": dur,
                                "size_mb": round(size_mb, 1),
                            })
                        except Exception:
                            tracks.append({
                                "path": full_path,
                                "filename": f,
                                "title": os.path.splitext(f)[0],
                                "artist": "Local Audio",
                                "album": "",
                                "year": "",
                                "sample_rate": 44100,
                                "bits": 16,
                                "duration_sec": 0,
                                "size_mb": round(os.path.getsize(full_path) / (1024 * 1024), 1),
                            })
        return tracks

    def reveal_file(self, file_path: str):
        if file_path and os.path.exists(file_path):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(file_path)}"')
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False, "error": "File does not exist"}

    def open_music_folder(self):
        target = config.get("download_dir")
        if os.path.exists(target):
            try:
                os.startfile(target)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": False}

    # ---------------- Audio Player ----------------
    def play_track(self, track_data: dict):
        preview_url = track_data.get("preview_url")
        local_path = track_data.get("path")
        if preview_url:
            player.play_url(preview_url, track_data)
            return {"success": True, "playing": True}
        elif local_path and os.path.exists(local_path):
            player.play_local_file(local_path, track_data)
            return {"success": True, "playing": True}
        return {"success": False, "error": "No playable stream or file"}

    def toggle_playback(self):
        is_playing = player.toggle_play_pause()
        return {"playing": is_playing}

    def stop_playback(self):
        player.stop()
        return {"playing": False}

    def set_volume(self, vol: float):
        player.set_volume(vol)
        return {"volume": vol}

bridge = AppBridge()
