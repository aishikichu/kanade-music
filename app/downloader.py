import os
import sys
import re
import shutil
import threading
import tempfile
import time
import requests
import imageio_ffmpeg
import yt_dlp
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, TCON, TRCK, APIC, COMM
from app.config import config
from app.metadata import fetch_image_bytes, search_music_all, clean_song_query
from app.hifi_resolver import hifi_resolver, HEADERS as HIFI_HEADERS

def get_ffmpeg_path() -> str:
    """Finds ffmpeg executable whether running from source or frozen in PyInstaller exe."""
    # 1. Check PyInstaller temp directory (_MEIPASS)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            # Check direct ffmpeg.exe
            candidate = os.path.join(meipass, "ffmpeg.exe")
            if os.path.isfile(candidate):
                return candidate
            # Check imageio_ffmpeg binaries folder inside _MEIPASS
            bin_dir = os.path.join(meipass, "imageio_ffmpeg", "binaries")
            if os.path.isdir(bin_dir):
                for f in os.listdir(bin_dir):
                    if f.startswith("ffmpeg") and f.endswith(".exe"):
                        return os.path.join(bin_dir, f)

    # 2. Check next to running .exe or script
    app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_candidate = os.path.join(app_dir, "ffmpeg.exe")
    if os.path.isfile(local_candidate):
        return local_candidate

    # 3. Use imageio_ffmpeg auto-detection
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        print(f"[FFmpeg] imageio_ffmpeg fallback: {e}")

    # 4. System PATH fallback
    return "ffmpeg"

def sanitize_filename(name: str) -> str:
    """Removes or replaces characters forbidden in Windows paths: < > : " / \\ | ? *"""
    if not name:
        return "Unknown"
    # Replace colons with dashes for clean reading
    name = name.replace(":", " - ")
    # Replace other forbidden chars
    name = re.sub(r'[<>"/\\|?*]', "", name)
    # Strip leading/trailing spaces and dots
    name = re.sub(r"\s+", " ", name).strip(". ")
    return name or "Unknown"

def format_output_path(base_dir: str, metadata: dict, template_type: str = "audiophile", extension: str = ".m4a") -> tuple:
    """Computes target file path and folder path based on metadata and selected template."""
    artist = sanitize_filename(metadata.get("artist", "Unknown Artist"))
    album = sanitize_filename(metadata.get("album", "Unknown Album"))
    title = sanitize_filename(metadata.get("title", "Unknown Track"))
    year = sanitize_filename(str(metadata.get("year", "")))
    track_num = metadata.get("track_number", 1)
    try:
        track_str = f"{int(track_num):02d}"
    except Exception:
        track_str = "01"

    ext = extension if extension.startswith(".") else f".{extension}"

    if template_type == "audiophile":
        album_dir_name = f"{album} ({year})" if year else album
        folder = os.path.join(base_dir, artist, album_dir_name)
        filename = f"{track_str} - {title}{ext}"
    elif template_type == "artist_album":
        folder = os.path.join(base_dir, artist, album)
        filename = f"{track_str} - {title}{ext}"
    elif template_type == "artist_track":
        folder = os.path.join(base_dir, artist)
        filename = f"{track_str} - {title}{ext}"
    else:  # flat
        folder = base_dir
        filename = f"{artist} - {title}{ext}"

    full_path = os.path.join(folder, filename)
    return folder, full_path

def tag_audio_file(file_path: str, metadata: dict, cover_bytes: bytes = None, save_folder_cover: bool = True) -> bool:
    """
    Applies standard studio metadata tags and embeds high-res album art.
    Supports FLAC (.flac), AAC/M4A (.m4a), and MP3 (.mp3).
    """
    try:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".flac":
            audio = FLAC(file_path)
            audio.clear()
            if metadata.get("title"):
                audio["TITLE"] = str(metadata["title"])
            if metadata.get("artist"):
                audio["ARTIST"] = str(metadata["artist"])
            if metadata.get("album"):
                audio["ALBUM"] = str(metadata["album"])
            if metadata.get("album_artist"):
                audio["ALBUMARTIST"] = str(metadata["album_artist"])
            elif metadata.get("artist"):
                audio["ALBUMARTIST"] = str(metadata["artist"])
            if metadata.get("year"):
                audio["DATE"] = str(metadata["year"])
                audio["YEAR"] = str(metadata["year"])
            if metadata.get("genre"):
                audio["GENRE"] = str(metadata["genre"])
            if metadata.get("track_number"):
                audio["TRACKNUMBER"] = str(metadata["track_number"])
            if metadata.get("track_total"):
                audio["TRACKTOTAL"] = str(metadata["track_total"])
            if metadata.get("disc_number"):
                audio["DISCNUMBER"] = str(metadata["disc_number"])

            bits = getattr(audio.info, "bits_per_sample", 16)
            sr = getattr(audio.info, "sample_rate", 44100)
            if bits > 16 or sr > 44100:
                audio["COMMENT"] = f"Kanade {bits}-bit / {round(sr/1000, 1)} kHz Hi-Res Studio Master"
                audio["ENCODER"] = f"FLAC {bits}-bit Hi-Res Audio Encoder"
            else:
                audio["COMMENT"] = f"Kanade 16-bit / 44.1 kHz CD Lossless Audio"
                audio["ENCODER"] = "FLAC 16-bit Lossless Audio Encoder"

            if cover_bytes and config.get("embed_cover_art", True):
                audio.clear_pictures()
                pic = Picture()
                pic.type = 3  # Front Cover
                pic.mime = "image/png" if cover_bytes.startswith(b"\x89PNG") else "image/jpeg"
                pic.desc = "Front Cover"
                pic.data = cover_bytes
                audio.add_picture(pic)
            audio.save()

        elif ext in (".m4a", ".mp4"):
            audio = MP4(file_path)
            if audio.tags is None:
                audio.add_tags()

            if metadata.get("title"):
                audio["\xa9nam"] = [str(metadata["title"])]
            if metadata.get("artist"):
                audio["\xa9ART"] = [str(metadata["artist"])]
            if metadata.get("album"):
                audio["\xa9alb"] = [str(metadata["album"])]
            if metadata.get("album_artist"):
                audio["aART"] = [str(metadata["album_artist"])]
            elif metadata.get("artist"):
                audio["aART"] = [str(metadata["artist"])]
            if metadata.get("year"):
                audio["\xa9day"] = [str(metadata["year"])]
            if metadata.get("genre"):
                audio["\xa9gen"] = [str(metadata["genre"])]

            trkn = metadata.get("track_number", 1)
            trkt = metadata.get("track_total", 0)
            try:
                audio["trkn"] = [(int(trkn), int(trkt or 0))]
            except Exception:
                pass

            discn = metadata.get("disc_number", 1)
            try:
                audio["disk"] = [(int(discn), 1)]
            except Exception:
                pass

            audio["\xa9cmt"] = ["Kanade Native Master"]

            if cover_bytes and config.get("embed_cover_art", True):
                img_fmt = MP4Cover.FORMAT_PNG if cover_bytes.startswith(b"\x89PNG") else MP4Cover.FORMAT_JPEG
                audio["covr"] = [MP4Cover(cover_bytes, imageformat=img_fmt)]
            audio.save()

        elif ext == ".mp3":
            try:
                audio = ID3(file_path)
            except Exception:
                audio = ID3()
            audio.delete()
            if metadata.get("title"):
                audio["TIT2"] = TIT2(encoding=3, text=str(metadata["title"]))
            if metadata.get("artist"):
                audio["TPE1"] = TPE1(encoding=3, text=str(metadata["artist"]))
            if metadata.get("album"):
                audio["TALB"] = TALB(encoding=3, text=str(metadata["album"]))
            if metadata.get("year"):
                audio["TDRC"] = TDRC(encoding=3, text=str(metadata["year"]))
            if metadata.get("genre"):
                audio["TCON"] = TCON(encoding=3, text=str(metadata["genre"]))
            if metadata.get("track_number"):
                audio["TRCK"] = TRCK(encoding=3, text=str(metadata["track_number"]))
            audio["COMM"] = COMM(encoding=3, lang="eng", desc="desc", text="Kanade Studio Master")

            if cover_bytes and config.get("embed_cover_art", True):
                mime = "image/png" if cover_bytes.startswith(b"\x89PNG") else "image/jpeg"
                audio["APIC"] = APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover_bytes)
            audio.save(file_path)

        # Save external cover.jpg in album directory if enabled
        if cover_bytes and save_folder_cover:
            album_dir = os.path.dirname(file_path)
            cover_file = os.path.join(album_dir, "cover.jpg")
            if not os.path.exists(cover_file):
                with open(cover_file, "wb") as f:
                    f.write(cover_bytes)

        return True
    except Exception as e:
        print(f"[Tagging Error] {e}")
        return False

# Backwards compatibility alias
tag_flac_file = tag_audio_file

class DownloadTask:
    def __init__(self, task_id: str, item_data: dict, url: str = None, on_progress=None, on_complete=None, on_error=None):
        self.task_id = task_id
        self.metadata = item_data.copy()
        self.url = url
        self.on_progress = on_progress
        self.on_complete = on_complete
        self.on_error = on_error
        self.status = "queued"
        self.percent = 0.0
        self.speed = ""
        self.eta = ""
        self.output_file = ""
        self.error_msg = ""
        self.cancelled = False

class MusicDownloader:
    def __init__(self):
        self.tasks = []
        self.queue_lock = threading.Lock()
        self.worker_thread = None
        self.running = True
        self.ffmpeg_path = get_ffmpeg_path()
        self._start_worker()

    def _start_worker(self):
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def add_search_item_to_queue(self, metadata: dict, on_progress=None, on_complete=None, on_error=None) -> DownloadTask:
        task_id = f"task_{int(time.time()*1000)}_{len(self.tasks)}"
        task = DownloadTask(task_id, metadata, url=None, on_progress=on_progress, on_complete=on_complete, on_error=on_error)
        with self.queue_lock:
            self.tasks.append(task)
        return task

    def add_url_to_queue(self, url: str, custom_metadata: dict = None, on_progress=None, on_complete=None, on_error=None) -> DownloadTask:
        task_id = f"task_{int(time.time()*1000)}_{len(self.tasks)}"
        meta = custom_metadata or {
            "title": "Pending URL Inspection",
            "artist": "Web Stream",
            "album": "Single",
            "year": "",
            "genre": "Music",
            "track_number": 1,
            "artwork_url": "",
        }
        task = DownloadTask(task_id, meta, url=url, on_progress=on_progress, on_complete=on_complete, on_error=on_error)
        with self.queue_lock:
            self.tasks.append(task)
        return task

    def _process_queue(self):
        while self.running:
            task_to_run = None
            with self.queue_lock:
                for t in self.tasks:
                    if t.status == "queued" and not t.cancelled:
                        task_to_run = t
                        task_to_run.status = "downloading"
                        break
            if task_to_run:
                self._execute_download(task_to_run)
            else:
                time.sleep(0.5)

    def _execute_download(self, task: DownloadTask):
        temp_dir = tempfile.mkdtemp(prefix="kanade_")
        temp_out_template = os.path.join(temp_dir, "%(title)s.%(ext)s")

        try:
            # Step 1: If downloading via direct URL, extract info and auto-enrich metadata
            if task.url:
                task.status = "inspecting"
                if task.on_progress:
                    task.on_progress(task.task_id, "Inspecting audio stream & format...", 5, "", "")

                web_title = ""
                web_artist = ""
                web_thumbnail = ""

                # Extract web metadata with a quick timeout
                try:
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "socket_timeout": 8}) as ydl:
                        info = ydl.extract_info(task.url, download=False)
                        if info:
                            web_title = info.get("title", "")
                            web_artist = info.get("uploader", "") or info.get("artist", "")
                            web_thumbnail = info.get("thumbnail", "")
                except Exception as e:
                    print(f"[Downloader] Direct info extraction notice: {e}")
                    # If yt-dlp couldn't extract title, derive from URL filename
                    raw_filename = os.path.basename(task.url.split("?")[0])
                    web_title = os.path.splitext(raw_filename)[0] or "Direct Audio Stream"

                # Clean title and auto-match studio tags
                cleaned = clean_song_query(web_title)
                matched = None
                if cleaned:
                    match_query = f"{web_artist} {cleaned}".strip() if web_artist else cleaned
                    try:
                        matched = search_music_all(match_query, limit_per_source=6)
                        if not matched and " - " in cleaned:
                            matched = search_music_all(cleaned, limit_per_source=6)
                    except Exception:
                        pass

                if matched:
                    m = matched[0]
                    task.metadata.update({
                        "title": m["title"],
                        "artist": m["artist"],
                        "album": m["album"],
                        "album_artist": m["album_artist"],
                        "year": m["year"],
                        "genre": m["genre"],
                        "track_number": m["track_number"],
                        "track_total": m["track_total"],
                        "disc_number": m["disc_number"],
                        "artwork_url": m["artwork_url"],
                    })
                else:
                    # Smart title parsing: "Artist - Title"
                    if " - " in web_title:
                        parts = web_title.split(" - ", 1)
                        task.metadata["artist"] = clean_song_query(parts[0])
                        task.metadata["title"] = clean_song_query(parts[1])
                    else:
                        task.metadata["artist"] = clean_song_query(web_artist) or "Online Artist"
                        task.metadata["title"] = clean_song_query(web_title) or "Lossless Audio Track"
                    if not task.metadata.get("artwork_url") and web_thumbnail:
                        task.metadata["artwork_url"] = web_thumbnail

                download_target = task.url
            else:
                # Search item: Use best audio query matching Artist and Title
                artist = task.metadata.get("artist", "")
                title = task.metadata.get("title", "")
                download_target = f"ytsearch1:{artist} {title} audio"

            downloaded_file_path = None
            quality_preset = config.get("audio_quality_preset", "flac_24bit")
            is_direct_url = bool(task.url)

            # Step 2: If 'hifi_first' or 'flac_24bit' or 'flac_16bit' preset is enabled, attempt zero-account community Hi-Fi gateway / lossless archives
            if quality_preset in ("hifi_first", "flac_24bit", "flac_16bit") and not is_direct_url:
                if task.on_progress:
                    task.on_progress(task.task_id, "Checking Lossless & Studio Archives (Bandcamp, Hi-Fi Gateways)...", 10, "", "")
                try:
                    hifi_info = hifi_resolver.resolve_lossless_stream(task.metadata)
                    if hifi_info and (hifi_info.get("stream_url") or hifi_info.get("direct_url")):
                        stream_url = hifi_info.get("stream_url") or hifi_info.get("direct_url")
                        source_label = hifi_info.get("source", "Lossless Archive")
                        if task.on_progress:
                            task.on_progress(task.task_id, f"Found Lossless FLAC via {source_label}! Downloading...", 15, "", "")
                        temp_flac = os.path.join(temp_dir, "lossless.flac")
                        r = requests.get(stream_url, headers=HIFI_HEADERS, stream=True, timeout=20)
                        if r.status_code == 200:
                            total_bytes = int(r.headers.get("content-length", 0))
                            received = 0
                            last_update = [time.time()]
                            with open(temp_flac, "wb") as f_out:
                                for chunk in r.iter_content(chunk_size=65536):
                                    if chunk:
                                        f_out.write(chunk)
                                        received += len(chunk)
                                        now = time.time()
                                        if now - last_update[0] >= 0.25:
                                            last_update[0] = now
                                            pct = round((received / total_bytes * 85), 1) if total_bytes > 0 else 50
                                            task.percent = pct
                                            if task.on_progress:
                                                task.on_progress(task.task_id, f"Streaming Lossless FLAC ({pct:.0f}%)", pct, "", "")
                            if os.path.exists(temp_flac) and os.path.getsize(temp_flac) > 102400:
                                downloaded_file_path = temp_flac
                except Exception as hifi_err:
                    print(f"[Lossless Resolver Notice] {hifi_err}")

            # Step 3: If not downloaded via Lossless gateway, capture stream and encode into selected FLAC or container
            if not downloaded_file_path:
                compression_lvl = config.get("flac_compression_level", 8)
                try:
                    compression_lvl = int(compression_lvl)
                except Exception:
                    compression_lvl = 8

                if quality_preset == "flac_24bit":
                    target_codec = "flac"
                    action_txt = "Encoding 24-bit / 48 kHz Hi-Res Studio FLAC..."
                    ffmpeg_extra_args = [
                        "-sample_fmt", "s32",
                        "-bits_per_raw_sample", "24",
                        "-ar", "48000",
                        "-compression_level", str(compression_lvl),
                    ]
                elif quality_preset in ("flac_16bit", "flac_legacy", "hifi_first"):
                    target_codec = "flac"
                    action_txt = "Encoding 16-bit / 44.1 kHz CD Lossless FLAC..."
                    ffmpeg_extra_args = [
                        "-sample_fmt", "s16",
                        "-ar", "44100",
                        "-compression_level", str(compression_lvl),
                    ]
                else:  # native_clean
                    target_codec = "m4a"
                    action_txt = "Finalizing Clean M4A Container..."
                    ffmpeg_extra_args = []

                last_progress_emit = [0.0]
                last_pct = [-1.0]

                def ytdl_progress_hook(d):
                    st = d.get("status")
                    if st == "downloading":
                        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                        downloaded = d.get("downloaded_bytes", 0)
                        pct = (downloaded / total_bytes * 100) if total_bytes > 0 else 0
                        speed = d.get("_speed_str", "")
                        eta = d.get("_eta_str", "")
                        task.percent = round(pct, 1)
                        task.speed = speed
                        task.eta = eta
                        task.status = "downloading"

                        now = time.time()
                        if (now - last_progress_emit[0] >= 0.25) or abs(pct - last_pct[0]) >= 2.0 or pct >= 100:
                            last_progress_emit[0] = now
                            last_pct[0] = pct
                            if task.on_progress:
                                task.on_progress(task.task_id, f"Downloading ({pct:.0f}%)", pct, speed, eta)

                    elif st == "finished":
                        task.status = "converting"
                        if task.on_progress:
                            task.on_progress(task.task_id, action_txt, 90, "", "")

                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": temp_out_template,
                    "ffmpeg_location": self.ffmpeg_path,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": target_codec,
                        "preferredquality": "0",
                    }],
                    "quiet": True,
                    "no_warnings": True,
                    "progress_hooks": [ytdl_progress_hook],
                }
                if ffmpeg_extra_args:
                    ydl_opts["postprocessor_args"] = ffmpeg_extra_args

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([download_target])

                # Find generated audio file in temp directory
                audio_candidates = [
                    f for f in os.listdir(temp_dir)
                    if any(f.lower().endswith(ext) for ext in (".m4a", ".flac", ".mp3", ".opus", ".aac", ".ogg", ".wav"))
                ]
                if not audio_candidates:
                    raise Exception("Audio file was not generated by audio encoder.")
                downloaded_file_path = os.path.join(temp_dir, audio_candidates[0])

            actual_ext = os.path.splitext(downloaded_file_path)[1].lower()

            # Step 4: Fetch high-res album artwork
            if task.on_progress:
                task.on_progress(task.task_id, "Fetching HD Album Artwork & Tags...", 95, "", "")

            art_url = task.metadata.get("artwork_url", "")
            art_bytes = fetch_image_bytes(art_url) if art_url else None

            # Step 5: Tag audio file with complete studio metadata & embedded Artwork
            save_ext = config.get("save_external_cover", True)
            tag_audio_file(downloaded_file_path, task.metadata, cover_bytes=art_bytes, save_folder_cover=save_ext)

            # Step 6: Move to user-configured destination directory & template
            base_dir = config.get("download_dir")
            os.makedirs(base_dir, exist_ok=True)
            template = config.get("folder_template", "audiophile")
            target_folder, target_audio_path = format_output_path(base_dir, task.metadata, template, extension=actual_ext)

            os.makedirs(target_folder, exist_ok=True)

            # If target file exists, avoid overwriting: append (1), (2), etc.
            if os.path.exists(target_audio_path):
                base_name, ext = os.path.splitext(target_audio_path)
                count = 1
                while os.path.exists(f"{base_name} ({count}){ext}"):
                    count += 1
                target_audio_path = f"{base_name} ({count}){ext}"

            shutil.move(downloaded_file_path, target_audio_path)

            task.output_file = target_audio_path
            task.status = "completed"
            task.percent = 100.0

            if task.on_progress:
                task.on_progress(task.task_id, "Completed & Tagged!", 100.0, "", "")
            if task.on_complete:
                task.on_complete(task)

        except Exception as e:
            task.status = "failed"
            task.error_msg = str(e)
            print(f"[Downloader Error] {e}")
            if task.on_progress:
                task.on_progress(task.task_id, f"Error: {e}", 0, "", "")
            if task.on_error:
                task.on_error(task, str(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

downloader = MusicDownloader()
