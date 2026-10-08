#!/usr/bin/env python3
"""
Kanade 奏 - Hi-Res Lossless Downloader & Studio Tagger
High-Performance Native Windows Desktop Application
"""
import sys
import os
import time
import traceback

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def log(msg):
    try:
        app_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(app_dir, "app_log.txt")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

from app.server import start_server_background

def launch_app():
    log("Starting Kanade...")
    # 1. Start lightweight local HTTP server
    port = start_server_background(8765)
    app_url = f"http://127.0.0.1:{port}"
    log(f"Local server started on {app_url}")

    # Brief delay to allow local socket to bind
    time.sleep(0.3)

    # 2. Launch native desktop window via WebView2
    try:
        import webview
        log("Imported webview successfully. Creating window...")
        window = webview.create_window(
            title="Kanade 奏 — Hi-Res Lossless Downloader",
            url=app_url,
            width=1260,
            height=820,
            min_size=(980, 640),
            background_color="#080c14",
        )
        log("Window created. Starting webview...")
        webview.start(gui="edgechromium", debug=False)
        log("Webview closed normally.")
    except Exception as e:
        err_msg = traceback.format_exc()
        log(f"PyWebView error:\n{err_msg}")
        log("Falling back to default web browser...")
        import webbrowser
        webbrowser.open(app_url)
        # Keep process alive while server runs
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    launch_app()
