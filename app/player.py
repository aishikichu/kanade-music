import os
import tempfile
import threading
import requests
import pygame

class AudioPlayer:
    def __init__(self):
        self.is_initialized = False
        self.current_track = None
        self.is_paused = False
        self.temp_preview_file = None
        self._init_mixer()

    def _init_mixer(self):
        try:
            pygame.mixer.init()
            pygame.mixer.music.set_volume(0.85)
            self.is_initialized = True
        except Exception as e:
            print(f"[AudioPlayer] Mixer initialization failed: {e}")

    def play_url(self, url: str, track_info: dict, on_playback_started=None):
        """Streams a 30s preview URL in a background thread and begins playback."""
        if not self.is_initialized or not url:
            return

        def _fetch_and_play():
            try:
                self.stop()
                r = requests.get(url, stream=True, timeout=8)
                if r.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                        self.temp_preview_file = tmp.name
                        for chunk in r.iter_content(chunk_size=16384):
                            tmp.write(chunk)

                    pygame.mixer.music.load(self.temp_preview_file)
                    pygame.mixer.music.play()
                    self.current_track = track_info.copy()
                    self.is_paused = False
                    if on_playback_started:
                        on_playback_started(self.current_track)
            except Exception as e:
                print(f"[AudioPlayer] Playback error: {e}")

        threading.Thread(target=_fetch_and_play, daemon=True).start()

    def play_local_file(self, file_path: str, track_info: dict = None, on_playback_started=None):
        """Plays a local FLAC / audio file from disk."""
        if not self.is_initialized or not os.path.exists(file_path):
            return

        try:
            self.stop()
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            self.current_track = track_info or {"title": os.path.basename(file_path), "artist": "Local FLAC"}
            self.is_paused = False
            if on_playback_started:
                on_playback_started(self.current_track)
        except Exception as e:
            print(f"[AudioPlayer] Error playing local file: {e}")

    def toggle_play_pause(self):
        if not self.is_initialized:
            return False
        if pygame.mixer.music.get_busy():
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
                return True
            else:
                pygame.mixer.music.pause()
                self.is_paused = True
                return False
        return False

    def stop(self):
        if not self.is_initialized:
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass
        self.is_paused = False
        self.current_track = None
        if self.temp_preview_file and os.path.exists(self.temp_preview_file):
            try:
                os.remove(self.temp_preview_file)
            except Exception:
                pass
            self.temp_preview_file = None

    def set_volume(self, volume_float: float):
        """Sets playback volume between 0.0 and 1.0"""
        if self.is_initialized:
            vol = max(0.0, min(1.0, volume_float))
            pygame.mixer.music.set_volume(vol)

    def is_playing(self):
        if not self.is_initialized:
            return False
        return pygame.mixer.music.get_busy() and not self.is_paused

player = AudioPlayer()
