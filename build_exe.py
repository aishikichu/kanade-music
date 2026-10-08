"""
Build script to compile Kanade into a high-performance standalone Windows .exe
"""
import os
import sys
import shutil
import imageio_ffmpeg
from PyInstaller.__main__ import run as pyinstaller_run

def build():
    print("=" * 65)
    print(" Compiling Kanade 奏 (Fast & Responsive Native Desktop .exe)")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(base_dir, "dist")
    web_dir = os.path.join(base_dir, "app", "web")
    ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

    print(f"[Build] Base directory: {base_dir}")
    print(f"[Build] Web assets directory: {web_dir}")
    print(f"[Build] Detected FFmpeg binary: {ffmpeg_bin}")

    # Build Arguments
    args = [
        "main.py",
        "--name=Kanade",
        "--onefile",
        "--noconsole",
        "--clean",
        "--add-data", f"{web_dir};app/web",
        "--collect-all=bottle",
        "--collect-all=pywebview",
        "--collect-all=pythonnet",
        "--collect-all=clr_loader",
        "--collect-all=customtkinter",
        "--collect-all=imageio_ffmpeg",
        "--collect-all=yt_dlp",
        "--collect-all=mutagen",
        "--collect-all=pygame",
        "--add-binary", f"{ffmpeg_bin};.",
        "--add-binary", f"{ffmpeg_bin};imageio_ffmpeg/binaries",
    ]

    print("[Build] Executing PyInstaller...")
    pyinstaller_run(args)

    exe_path = os.path.join(dist_dir, "Kanade.exe")
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print("=" * 65)
        print(f" SUCCESS! Compiled executable: {exe_path}")
        print(f" File Size: {size_mb:.1f} MB")
        print("=" * 65)

        # Copy companion ffmpeg.exe next to Kanade.exe
        ffmpeg_copy = os.path.join(dist_dir, "ffmpeg.exe")
        shutil.copy2(ffmpeg_bin, ffmpeg_copy)

        # Place directly in root workspace
        root_exe = os.path.join(base_dir, "Kanade.exe")
        try:
            shutil.copy2(exe_path, root_exe)
            print(f"[Build] Placed main executable in root workspace: {root_exe}")
        except Exception as e:
            print(f"[Build Warning] Could not overwrite root Kanade.exe (likely running): {e}")
            print(f"[Build] Latest executable is always ready in dist: {exe_path}")

        root_ffmpeg = os.path.join(base_dir, "ffmpeg.exe")
        if not os.path.exists(root_ffmpeg):
            shutil.copy2(ffmpeg_bin, root_ffmpeg)
            print(f"[Build] Placed companion ffmpeg.exe in root workspace: {root_ffmpeg}")

    else:
        print("[Build Error] Kanade.exe was not found in dist directory.")

if __name__ == "__main__":
    build()
