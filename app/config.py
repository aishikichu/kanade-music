import os
import sys
import json
import shutil
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CONFIG_FILE = os.path.join(APP_DIR, "settings.json")

def get_default_download_dir():
    # If E:\ drive exists and is accessible, use E:\HiRes Music
    if os.path.exists("E:\\"):
        default_path = "E:\\HiRes Music"
    elif os.path.exists("D:\\"):
        default_path = "D:\\HiRes Music"
    else:
        user_music = os.path.join(os.path.expanduser("~"), "Music")
        default_path = os.path.join(user_music, "HiRes Music")
    return default_path

DEFAULT_CONFIG = {
    "download_dir": get_default_download_dir(),
    "folder_template": "audiophile",  # 'audiophile', 'artist_album', 'artist_track', 'flat'
    "embed_cover_art": True,
    "save_external_cover": True,
    "artwork_resolution": "1400x1400",  # '1000x1000', '1400x1400', '3000x3000'
    "flac_compression_level": 8,        # 0-8 (8 is highest lossless compression)
    "audio_quality_preset": "flac_24bit",  # 'flac_24bit' (24-bit Hi-Res Studio FLAC), 'flac_16bit' (16-bit Lossless CD FLAC), 'hifi_first' (Lossless Archives + FLAC), 'native_clean' (Compact AAC M4A)
    "theme_mode": "dark",
    "color_accent": "blue",
    "max_concurrent_downloads": 2,
}

class AppConfig:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self.config.update(saved)
            except Exception as e:
                print(f"[Config] Error loading settings: {e}")
        # Ensure download directory is valid and exists
        download_dir = self.config.get("download_dir", get_default_download_dir())
        try:
            os.makedirs(download_dir, exist_ok=True)
        except Exception:
            self.config["download_dir"] = os.path.join(os.path.expanduser("~"), "Music", "HiRes Music")
            os.makedirs(self.config["download_dir"], exist_ok=True)

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"[Config] Error saving settings: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def get_available_drives(self):
        """Scans Windows drive letters A-Z and returns drives with capacity and free space."""
        import string
        drives = []
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                try:
                    usage = shutil.disk_usage(drive_path)
                    total_gb = usage.total / (1024 ** 3)
                    free_gb = usage.free / (1024 ** 3)
                    used_gb = usage.used / (1024 ** 3)
                    percent = (usage.used / usage.total) * 100 if usage.total > 0 else 0
                    drives.append({
                        "letter": f"{letter}:",
                        "path": f"{letter}:\\HiRes Music",
                        "root": drive_path,
                        "total_gb": round(total_gb, 1),
                        "free_gb": round(free_gb, 1),
                        "used_gb": round(used_gb, 1),
                        "percent_used": round(percent, 1)
                    })
                except Exception:
                    pass
        return drives

    def get_drive_info(self, path=None):
        """Returns drive statistics for the target folder: drive letter, total_gb, used_gb, free_gb, percent_used"""
        target = path or self.get("download_dir")
        try:
            drive = os.path.splitdrive(os.path.abspath(target))[0]
            if not drive:
                drive = "C:"
            usage = shutil.disk_usage(target if os.path.exists(target) else drive + "\\")
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            percent = (usage.used / usage.total) * 100 if usage.total > 0 else 0
            return {
                "drive": drive,
                "total_gb": round(total_gb, 1),
                "used_gb": round(used_gb, 1),
                "free_gb": round(free_gb, 1),
                "percent_used": round(percent, 1),
                "path": target
            }
        except Exception as e:
            return {
                "drive": "Unknown",
                "total_gb": 0,
                "used_gb": 0,
                "free_gb": 0,
                "percent_used": 0,
                "path": str(target),
                "error": str(e)
            }

config = AppConfig()
