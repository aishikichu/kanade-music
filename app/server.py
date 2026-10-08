import os
import sys
import json
import socket
import subprocess
import threading
from bottle import Bottle, request, response, static_file, run

from app.config import config
from app.metadata import search_music_all
from app.downloader import downloader, DownloadTask
from app.player import player
from app.playlist import playlist_resolver

def find_available_port(default_port=8765):
    """Finds an available TCP port on localhost."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", default_port))
        sock.close()
        return default_port
    except OSError:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

def get_web_dir():
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target = os.path.join(base, "app", "web")
    if not os.path.exists(target):
        target = os.path.join(base, "web")
    return target

def create_app():
    app = Bottle()
    web_dir = get_web_dir()

    # CORS Headers for complete security and seamless fetch() calls
    @app.hook("after_request")
    def enable_cors():
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"

    # Static file serving
    @app.route("/")
    def index():
        return static_file("index.html", root=web_dir)

    @app.route("/<filename:path>")
    def static_assets(filename):
        return static_file(filename, root=web_dir)

    # ---------------- API: Settings & Storage ----------------
    @app.route("/api/settings", method=["GET", "OPTIONS"])
    def get_settings():
        response.content_type = "application/json"
        return json.dumps({
            "config": config.config,
            "drive_info": config.get_drive_info(),
            "available_drives": config.get_available_drives(),
        })

    @app.route("/api/settings", method=["POST"])
    def save_settings():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            for k, v in data.items():
                config.set(k, v)
            return json.dumps({
                "success": True,
                "config": config.config,
                "drive_info": config.get_drive_info(),
                "available_drives": config.get_available_drives(),
            })
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/browse-folder", method=["POST"])
    def browse_folder():
        response.content_type = "application/json"
        cur = config.get("download_dir", "")
        chosen = None
        try:
            from tkinter import filedialog, Tk
            root = Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            chosen = filedialog.askdirectory(initialdir=cur if os.path.exists(cur) else None, title="Select Storage Drive or Folder for Hi-Res FLAC")
            root.destroy()
        except Exception as e:
            print(f"[Folder Dialog Error] {e}")

        if chosen:
            norm = os.path.normpath(chosen)
            config.set("download_dir", norm)
            os.makedirs(norm, exist_ok=True)
            return json.dumps({
                "success": True,
                "path": norm,
                "drive_info": config.get_drive_info(),
                "available_drives": config.get_available_drives(),
            })
        return json.dumps({"success": False})

    @app.route("/api/set-quick-drive", method=["POST"])
    def set_quick_drive():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            letter = data.get("letter", "E:")
            target = f"{letter}\\HiRes Music"
            os.makedirs(target, exist_ok=True)
            config.set("download_dir", target)
            return json.dumps({
                "success": True,
                "path": target,
                "drive_info": config.get_drive_info(),
                "available_drives": config.get_available_drives(),
            })
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/open-folder", method=["POST"])
    def open_folder():
        response.content_type = "application/json"
        target = config.get("download_dir")
        if os.path.exists(target):
            try:
                os.startfile(target)
                return json.dumps({"success": True})
            except Exception as e:
                return json.dumps({"success": False, "error": str(e)})
        return json.dumps({"success": False, "error": "Folder does not exist"})

    # ---------------- API: Music Search ----------------
    @app.route("/api/search", method=["GET"])
    def search_music():
        response.content_type = "application/json"
        query = request.query.get("q", "").strip()
        if not query:
            return json.dumps([])

        res_res = config.get("artwork_resolution", "1400x1400")
        filter_unwanted = request.query.get("filter_unwanted", "0") in ("1", "true", "True")
        try:
            results = search_music_all(query, limit_per_source=15, resolution=res_res, filter_unwanted=filter_unwanted)
            return json.dumps(results)
        except Exception as e:
            print(f"[Search API Error] {e}")
            return json.dumps([])

    @app.route("/api/score", method=["POST"])
    def score_tracks_api():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            query = data.get("query", "")
            tracks = data.get("tracks", [])
            filter_unwanted = bool(data.get("filter_unwanted", False))
            from app.scoring import rank_tracks
            ranked = rank_tracks(query, tracks, filter_unwanted=filter_unwanted)
            return json.dumps(ranked)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ---------------- API: Downloads ----------------
    @app.route("/api/download-track", method=["POST"])
    def download_track():
        response.content_type = "application/json"
        try:
            track = request.json or {}
            task = downloader.add_search_item_to_queue(track)
            return json.dumps({"success": True, "task_id": task.task_id})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # ---------------- API: Playlist Import ----------------
    @app.route("/api/playlist/resolve", method=["POST"])
    def resolve_playlist_api():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            url = data.get("url", "").strip()
            limit = int(data.get("limit", 200))
            if not url:
                return json.dumps({"success": False, "error": "URL is required"})
            pl = playlist_resolver.resolve(url, limit=limit)
            return json.dumps({"success": True, "playlist": pl.to_dict()})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/playlist/queue", method=["POST"])
    def queue_playlist_api():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            url = data.get("url", "").strip()
            tracks = data.get("tracks", [])
            if tracks:
                added = []
                for trk in tracks:
                    t = downloader.add_search_item_to_queue(trk)
                    added.append(t.task_id)
                return json.dumps({"success": True, "count": len(added), "task_ids": added})
            elif url:
                limit = int(data.get("limit", 200))
                res = playlist_resolver.queue_playlist(url, limit=limit)
                return json.dumps({"success": True, "count": res["total_tracks"], "task_ids": res["task_ids"], "playlist": res["playlist"]})
            else:
                return json.dumps({"success": False, "error": "URL or tracks required"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/download-url", method=["POST"])
    def download_url():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            url = data.get("url", "").strip()
            if not url:
                return json.dumps({"success": False, "error": "Empty URL"})

            # Check if this is a supported streaming playlist (Spotify, Apple Music, Deezer)
            plat, _ = playlist_resolver.identify(url)
            if plat:
                res = playlist_resolver.queue_playlist(url)
                return json.dumps({
                    "success": True,
                    "is_playlist": True,
                    "count": res["total_tracks"],
                    "playlist_title": res["playlist_title"],
                    "task_ids": res["task_ids"],
                })

            task = downloader.add_url_to_queue(url)
            return json.dumps({"success": True, "task_id": task.task_id})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/download-batch", method=["POST"])
    def download_batch():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            urls = data.get("urls", [])
            added = []
            for u in urls:
                if u and u.strip():
                    u_clean = u.strip()
                    plat, _ = playlist_resolver.identify(u_clean)
                    if plat:
                        try:
                            res = playlist_resolver.queue_playlist(u_clean)
                            added.extend(res["task_ids"])
                        except Exception as e:
                            print(f"[Playlist Batch Error] {e}")
                    else:
                        t = downloader.add_url_to_queue(u_clean)
                        added.append(t.task_id)
            return json.dumps({"success": True, "count": len(added), "task_ids": added})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/download-all", method=["POST"])
    def download_all():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            tracks = data.get("tracks", [])
            added = []
            for trk in tracks:
                t = downloader.add_search_item_to_queue(trk)
                added.append(t.task_id)
            return json.dumps({"success": True, "count": len(added)})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/queue", method=["GET"])
    def get_queue():
        response.content_type = "application/json"
        with downloader.queue_lock:
            tasks = []
            for t in downloader.tasks:
                output_ext = os.path.splitext(t.output_file)[1].lower() if t.output_file else ""
                is_flac = output_ext == ".flac" or (not output_ext and config.get("audio_quality_preset", "flac_24bit") != "native_clean")
                preset = config.get("audio_quality_preset", "flac_24bit")
                if is_flac:
                    quality_label = "24-bit Hi-Res FLAC" if preset == "flac_24bit" else "16-bit Lossless FLAC"
                elif output_ext in (".m4a", ".mp4"):
                    quality_label = "Native Clean AAC"
                else:
                    quality_label = output_ext.replace(".", "").upper() if output_ext else ""
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
                    "format": output_ext.replace(".", "").upper() if output_ext else "",
                    "is_flac": is_flac,
                    "quality_label": quality_label,
                    "error_msg": t.error_msg,
                })
            return json.dumps(tasks)

    @app.route("/api/clear-queue", method=["POST"])
    def clear_queue():
        response.content_type = "application/json"
        with downloader.queue_lock:
            downloader.tasks = [t for t in downloader.tasks if t.status not in ("completed", "failed")]
        return json.dumps({"success": True})

    # ---------------- API: Library ----------------
    @app.route("/api/library", method=["GET"])
    def get_library():
        response.content_type = "application/json"
        base_dir = config.get("download_dir")
        tracks = []
        if os.path.exists(base_dir):
            from mutagen.flac import FLAC
            from mutagen.mp4 import MP4
            from mutagen.mp3 import MP3
            for root, _, files in os.walk(base_dir):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in (".flac", ".m4a", ".mp3"):
                        full_path = os.path.join(root, f)
                        try:
                            size_mb = os.path.getsize(full_path) / (1024 * 1024)
                            if ext == ".flac":
                                audio = FLAC(full_path)
                                title = audio.get("TITLE", [os.path.splitext(f)[0]])[0]
                                artist = audio.get("ARTIST", ["Unknown Artist"])[0]
                                album = audio.get("ALBUM", ["Unknown Album"])[0]
                                year = audio.get("DATE", audio.get("YEAR", [""]))[0]
                                sr = getattr(audio.info, "sample_rate", 44100)
                                bits = getattr(audio.info, "bits_per_sample", 16)
                                dur = int(getattr(audio.info, "length", 0))
                                fmt = "FLAC"
                                is_hires = bits > 16 or sr > 44100
                                tier_badge = "HI-RES" if is_hires else "LOSSLESS"
                                tier_label = f"{bits}-bit / {round(sr/1000, 1)} kHz Hi-Res" if is_hires else f"{bits}-bit / {round(sr/1000, 1)} kHz Lossless"
                                quality_badge = f"{bits}-bit / {round(sr/1000, 1)} kHz"
                            elif ext == ".m4a":
                                audio = MP4(full_path)
                                title = (audio.get("\xa9nam") or [os.path.splitext(f)[0]])[0]
                                artist = (audio.get("\xa9ART") or ["Unknown Artist"])[0]
                                album = (audio.get("\xa9alb") or ["Unknown Album"])[0]
                                year = (audio.get("\xa9day") or [""])[0]
                                sr = getattr(audio.info, "sample_rate", 44100)
                                dur = int(getattr(audio.info, "length", 0))
                                bitrate = getattr(audio.info, "bitrate", 0)
                                bitrate_kbps = round(bitrate / 1000) if (bitrate and bitrate >= 64000) else 256
                                fmt = "M4A"
                                is_hires = False
                                tier_badge = "NATIVE"
                                tier_label = f"{bitrate_kbps} kbps AAC Clean Stream"
                                quality_badge = f"{bitrate_kbps} kbps AAC"
                                bits = 16
                            elif ext == ".mp3":
                                audio = MP3(full_path)
                                title = str(audio.get("TIT2", os.path.splitext(f)[0]))
                                artist = str(audio.get("TPE1", "Unknown Artist"))
                                album = str(audio.get("TALB", "Unknown Album"))
                                year = str(audio.get("TDRC", ""))
                                sr = getattr(audio.info, "sample_rate", 44100)
                                dur = int(getattr(audio.info, "length", 0))
                                bitrate = getattr(audio.info, "bitrate", 0)
                                bitrate_kbps = round(bitrate / 1000) if bitrate else 320
                                fmt = "MP3"
                                is_hires = False
                                tier_badge = "MP3"
                                tier_label = f"{bitrate_kbps} kbps MP3"
                                quality_badge = f"{bitrate_kbps} kbps MP3"
                                bits = 16
                            else:
                                continue

                            tracks.append({
                                "path": full_path,
                                "filename": f,
                                "title": title,
                                "artist": artist,
                                "album": album,
                                "year": year,
                                "format": fmt,
                                "is_hires": is_hires,
                                "tier_badge": tier_badge,
                                "tier_label": tier_label,
                                "quality_badge": quality_badge,
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
                                "format": ext.strip(".").upper(),
                                "quality_badge": "Audio",
                                "sample_rate": 44100,
                                "bits": 16,
                                "duration_sec": 0,
                                "size_mb": round(os.path.getsize(full_path) / (1024 * 1024), 1),
                            })
        return json.dumps(tracks)

    @app.route("/api/reveal", method=["POST"])
    def reveal_file():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            file_path = data.get("path", "")
            if file_path and os.path.exists(file_path):
                subprocess.Popen(f'explorer /select,"{os.path.abspath(file_path)}"')
                return json.dumps({"success": True})
            return json.dumps({"success": False, "error": "File not found"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/spectrogram", method=["GET"])
    def get_spectrogram():
        file_path = request.query.get("path", "")
        if not file_path or not os.path.exists(file_path):
            response.status = 404
            return "File not found"
        try:
            import hashlib, tempfile
            ffmpeg = downloader.ffmpeg_path
            file_hash = hashlib.md5(f"{file_path}_{os.path.getmtime(file_path)}".encode("utf-8")).hexdigest()
            cache_png = os.path.join(tempfile.gettempdir(), f"spectrogram_{file_hash}.png")
            if not os.path.exists(cache_png):
                subprocess.run([
                    ffmpeg, "-y", "-i", file_path,
                    "-lavfi", "showspectrumpic=s=1024x512:mode=combined:color=rainbow:legend=1",
                    cache_png
                ], capture_output=True, timeout=20)
            if os.path.exists(cache_png):
                dir_name, file_name = os.path.split(cache_png)
                return static_file(file_name, root=dir_name, mimetype="image/png")
            response.status = 500
            return "Failed to generate spectrogram"
        except Exception as e:
            response.status = 500
            return str(e)

    # ---------------- API: Audio Player & Streams ----------------
    @app.route("/api/stream", method=["GET"])
    def stream_audio():
        file_path = request.query.get("path", "")
        if not file_path or not os.path.exists(file_path):
            response.status = 404
            return "File not found"
        dir_name, file_name = os.path.split(file_path)
        ext = os.path.splitext(file_name)[1].lower()
        mime_map = {
            ".flac": "audio/flac",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".aac": "audio/aac",
            ".ogg": "audio/ogg",
            ".wav": "audio/wav",
        }
        mime = mime_map.get(ext, "application/octet-stream")
        return static_file(file_name, root=dir_name, mimetype=mime)

    @app.route("/api/preview-lookup", method=["GET", "POST"])
    def preview_lookup():
        response.content_type = "application/json"
        try:
            if request.method == "POST":
                data = request.json or {}
                artist = data.get("artist", "").strip()
                title = data.get("title", "").strip()
            else:
                artist = request.query.get("artist", "").strip()
                title = request.query.get("title", "").strip()

            query = f"{artist} {title}".strip() if artist else title
            if not query:
                return json.dumps({"success": False, "error": "Query required"})

            from app.metadata import search_itunes, search_deezer
            itunes_res = search_itunes(query, limit=3)
            for item in itunes_res:
                if item.get("preview_url"):
                    return json.dumps({
                        "success": True,
                        "preview_url": item["preview_url"],
                        "source": "iTunes Preview",
                        "title": item.get("title", title),
                        "artist": item.get("artist", artist),
                    })

            deezer_res = search_deezer(query, limit=3)
            for item in deezer_res:
                if item.get("preview_url"):
                    return json.dumps({
                        "success": True,
                        "preview_url": item["preview_url"],
                        "source": "Deezer Preview",
                        "title": item.get("title", title),
                        "artist": item.get("artist", artist),
                    })

            return json.dumps({"success": False, "error": "No preview found"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/play", method=["POST"])
    def play_track():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            preview_url = data.get("preview_url")
            local_path = data.get("path")
            if preview_url:
                player.play_url(preview_url, data)
                return json.dumps({"success": True, "playing": True})
            elif local_path and os.path.exists(local_path):
                player.play_local_file(local_path, data)
                return json.dumps({"success": True, "playing": True})
            return json.dumps({"success": False, "error": "No playable stream or file"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @app.route("/api/toggle-play", method=["POST"])
    def toggle_play():
        response.content_type = "application/json"
        is_playing = player.toggle_play_pause()
        return json.dumps({"playing": is_playing})

    @app.route("/api/stop", method=["POST"])
    def stop_play():
        response.content_type = "application/json"
        player.stop()
        return json.dumps({"playing": False})

    @app.route("/api/volume", method=["POST"])
    def set_volume():
        response.content_type = "application/json"
        try:
            data = request.json or {}
            vol = float(data.get("volume", 0.85))
            player.set_volume(vol)
            return json.dumps({"success": True, "volume": vol})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    return app

from bottle import ServerAdapter

class ThreadedServer(ServerAdapter):
    def run(self, handler):
        from wsgiref.simple_server import make_server, WSGIServer
        from socketserver import ThreadingMixIn

        class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
            daemon_threads = True

        server = make_server(self.host, self.port, handler, server_class=ThreadedWSGIServer)
        server.serve_forever()

def start_server_background(port=None):
    chosen_port = port or find_available_port(8765)
    app = create_app()
    server_thread = threading.Thread(
        target=lambda: run(app, host="127.0.0.1", port=chosen_port, server=ThreadedServer, quiet=True),
        daemon=True
    )
    server_thread.start()
    return chosen_port
