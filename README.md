# 🌸 Kanade (奏)
> **Fast, subscription-free Hi-Res (24-bit / 16-bit) FLAC music downloader, studio metadata tagger, and acoustic spectrogram inspector.**

[![Format](https://img.shields.io/badge/Audio-24--bit%20%7C%2016--bit%20FLAC-00f0ff?style=flat-square)](https://flac.sourceforge.net/)
[![Platform](https://img.shields.io/badge/Platform-Windows-blue?style=flat-square)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blueviolet?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

**Kanade (奏)** is an audiophile-focused, subscription-free desktop music suite designed to search, stream, download, and archive pristine **24-bit Hi-Res & 16-bit CD-lossless FLAC audio** directly to any storage drive, complete with high-resolution artwork and built-in acoustic frequency verification.

---

## ✨ Key Features

### 1. 👑 True Lossless & Hi-Res Audio (24-bit & 16-bit)
- **24-bit Studio Master FLAC:** Encoded with `-sample_fmt s32 -bits_per_raw_sample 24 -ar 48000` for high-resolution depth and dynamics.
- **16-bit CD Quality FLAC:** Clean Red Book standard 44.1 kHz audio with Flac Level 8 lossless compression.
- **Instant Quick-Quality Switcher:** Toggle between 24-bit Hi-Res, 16-bit CD, and Native stream in one click.

### 2. 🔬 Built-in Acoustic Spectrogram Inspector
- Verify whether an audio file is **genuine Hi-Res** or an upsampled fake FLAC right from your library.
- Integrated FFmpeg `showspectrumpic` acoustic frequency rendering.
- Visualizes frequency ceiling, ultrasonic harmonics above 20 kHz, and flags lossy transcode "brick-wall" compression cutoffs.

### 3. 🔍 Universal Search & Lossless Grabber
- Search across global studio databases (Apple Music, iTunes, and Deezer catalogs) for any artist, song, or album.
- Preview 30-second studio auditions before downloading.
- Batch download entire albums and search result pages in a single click.

### 4. 🔗 Multi-Source URL & Playlist Downloader
- Paste links from **YouTube, YouTube Music, SoundCloud, Bandcamp, Audiomack, or direct streaming URLs**.
- Automatically enriches titles (strips video tags like `[Official Music Video]` or `(Lyrics)`), matches studio catalogs, and injects official tags.

### 5. 🎨 Studio Metadata & Embedded HD Artwork
- Injects full-resolution album covers (1400x1400 up to 3000x3000px) directly into FLAC Picture blocks.
- Standards-compliant Vorbis comments (`TITLE`, `ARTIST`, `ALBUM`, `ALBUMARTIST`, `DATE`, `GENRE`, `TRACKNUMBER`, `TRACKTOTAL`, `COMMENT`).
- Optional companion `cover.jpg` for car head units, Plex, Foobar2000, and Roon.

### 6. 📁 Storage Monitor & Custom File Routing
- Direct target drive routing (`C:`, `D:`, `E:`, external SSD, USB, or NAS).
- Real-time disk capacity meter showing Used / Free storage.
- Customizable folder structure templates (e.g., `{Artist}/{Album} ({Year})/{Track:02d} - {Title}.flac`).

---

## 🚀 Getting Started

### Prerequisites
- Windows 10 or 11
- Python 3.10+ (Python 3.12 recommended)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aishikichu/kanade-music.git
   cd kanade-music
   ```

2. **Create and activate a virtual environment:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch Kanade:**
   - Double-click `run.bat` or `run_debug.bat`, or run:
   ```powershell
   python main.py
   ```

---

## 🛠️ Standalone Executable Build

To compile a self-contained, high-performance Windows `.exe`:
```powershell
python build_exe.py
```
The compiled application will be generated in `dist/Kanade.exe`.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
