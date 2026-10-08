import re
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import io

from app.scoring import (
    score_track,
    score_track_detailed,
    rank_tracks,
    is_isrc,
    extract_isrc,
    extract_duration,
    detect_unwanted_tags,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def clean_song_query(text: str) -> str:
    """Strips video junk like (Official Music Video), [HD], 4K, lyrics, etc. for better metadata matching."""
    if not text:
        return ""
    # Remove bracketed/parenthetical phrases with common video keywords
    patterns = [
        r"\((?:official\s*)?(?:music\s*)?(?:video|audio|lyric|lyrics|visualizer).*?\)",
        r"\[(?:official\s*)?(?:music\s*)?(?:video|audio|lyric|lyrics|visualizer|4k|hd).*?\]",
        r"\b(?:official\s*video|official\s*audio|lyrics|hd|4k)\b",
        r"\s*-\s*topic\b",
    ]
    cleaned = text
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE)
    # Collapse excess spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def lookup_deezer_isrc(isrc: str):
    """Direct lookup for a specific ISRC from Deezer API."""
    if not isrc:
        return None
    clean = re.sub(r"[- ]", "", isrc).strip().upper()
    try:
        url = f"https://api.deezer.com/track/isrc:{clean}"
        r = requests.get(url, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            item = r.json()
            if "id" in item and not item.get("error"):
                artist_obj = item.get("artist", {})
                album_obj = item.get("album", {})
                hd_art = album_obj.get("cover_xl") or album_obj.get("cover_big") or album_obj.get("cover_medium", "")
                thumb_art = album_obj.get("cover_medium") or album_obj.get("cover_small", "")
                return {
                    "id": f"deezer_{item.get('id')}",
                    "title": item.get("title", "Unknown Track"),
                    "title_version": item.get("title_version", ""),
                    "artist": artist_obj.get("name", "Unknown Artist"),
                    "album": album_obj.get("title", "Unknown Album"),
                    "album_artist": artist_obj.get("name", "Unknown Artist"),
                    "year": item.get("release_date", "")[:4],
                    "release_date": item.get("release_date", ""),
                    "genre": "Music",
                    "track_number": item.get("track_position", 1),
                    "track_total": 1,
                    "disc_number": item.get("disk_number", 1),
                    "artwork_url": hd_art,
                    "thumbnail_url": thumb_art,
                    "preview_url": item.get("preview", ""),
                    "duration_sec": int(item.get("duration", 0)),
                    "isrc": item.get("isrc", clean),
                    "source": "Deezer Hi-Fi Catalog"
                }
    except Exception as e:
        print(f"[Metadata] Deezer ISRC lookup error: {e}")
    return None

def search_itunes(query: str, limit: int = 15, resolution: str = "1400x1400"):
    results = []
    try:
        url = "https://itunes.apple.com/search"
        params = {"term": query, "entity": "song", "limit": limit}
        r = requests.get(url, params=params, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("results", []):
                raw_art = item.get("artworkUrl100", "")
                hd_art = raw_art.replace("100x100bb", f"{resolution}bb") if raw_art else ""
                thumb_art = raw_art.replace("100x100bb", "150x150bb") if raw_art else ""
                year = item.get("releaseDate", "")[:4]
                results.append({
                    "id": f"itunes_{item.get('trackId')}",
                    "title": item.get("trackName", "Unknown Track"),
                    "title_version": "",
                    "artist": item.get("artistName", "Unknown Artist"),
                    "album": item.get("collectionName", "Unknown Album"),
                    "album_artist": item.get("artistName", "Unknown Artist"),
                    "year": year,
                    "release_date": item.get("releaseDate", ""),
                    "genre": item.get("primaryGenreName", "Music"),
                    "track_number": item.get("trackNumber", 1),
                    "track_total": item.get("trackCount", 1),
                    "disc_number": item.get("discNumber", 1),
                    "artwork_url": hd_art,
                    "thumbnail_url": thumb_art,
                    "preview_url": item.get("previewUrl", ""),
                    "duration_sec": int(item.get("trackTimeMillis", 0) / 1000),
                    "isrc": item.get("isrc", ""),
                    "source": "Apple / iTunes Catalog"
                })
    except Exception as e:
        print(f"[Metadata] iTunes search error: {e}")
    return results

def search_deezer(query: str, limit: int = 15):
    results = []
    try:
        url = "https://api.deezer.com/search"
        params = {"q": query, "limit": limit}
        r = requests.get(url, params=params, headers=HEADERS, timeout=6)
        if r.status_code == 200:
            data = r.json()
            for item in data.get("data", []):
                artist_obj = item.get("artist", {})
                album_obj = item.get("album", {})
                hd_art = album_obj.get("cover_xl") or album_obj.get("cover_big") or album_obj.get("cover_medium", "")
                thumb_art = album_obj.get("cover_medium") or album_obj.get("cover_small", "")
                results.append({
                    "id": f"deezer_{item.get('id')}",
                    "title": item.get("title", "Unknown Track"),
                    "title_version": item.get("title_version", ""),
                    "artist": artist_obj.get("name", "Unknown Artist"),
                    "album": album_obj.get("title", "Unknown Album"),
                    "album_artist": artist_obj.get("name", "Unknown Artist"),
                    "year": "",  # Deezer search root does not always have release year; fetched on detail if needed
                    "release_date": "",
                    "genre": "Music",
                    "track_number": item.get("track_position", 1),
                    "track_total": 1,
                    "disc_number": item.get("disk_number", 1),
                    "artwork_url": hd_art,
                    "thumbnail_url": thumb_art,
                    "preview_url": item.get("preview", ""),
                    "duration_sec": int(item.get("duration", 0)),
                    "isrc": item.get("isrc", ""),
                    "source": "Deezer Hi-Fi Catalog"
                })
    except Exception as e:
        print(f"[Metadata] Deezer search error: {e}")
    return results

def search_music_all(
    query: str,
    limit_per_source: int = 15,
    resolution: str = "1400x1400",
    filter_unwanted: bool = False
):
    """
    Runs parallel searches across iTunes and Deezer, merges results,
    and applies metadata scoring to prioritize original studio recordings
    over remixes, live versions, and covers.
    """
    raw_query = query.strip() if query else ""
    if not raw_query:
        return []

    isrc_code = extract_isrc(raw_query)

    # For broad queries, clean out video clutter if present
    cleaned = clean_song_query(raw_query)
    search_term = cleaned if cleaned else raw_query

    with ThreadPoolExecutor(max_workers=3) as executor:
        f_itunes = executor.submit(search_itunes, search_term, limit_per_source, resolution)
        f_deezer = executor.submit(search_deezer, search_term, limit_per_source)
        f_isrc = executor.submit(lookup_deezer_isrc, isrc_code) if isrc_code else None

        res_itunes = f_itunes.result()
        res_deezer = f_deezer.result()
        res_isrc = f_isrc.result() if f_isrc else None

    # Merge and deduplicate by (title.lower(), artist.lower())
    seen = set()
    combined = []

    if res_isrc:
        key = (res_isrc["title"].strip().lower(), res_isrc["artist"].strip().lower())
        seen.add(key)
        combined.append(res_isrc)

    # Apple results generally have fuller tags (year, genre, track count)
    for track in res_itunes:
        key = (track["title"].strip().lower(), track["artist"].strip().lower())
        if key not in seen:
            seen.add(key)
            combined.append(track)

    for track in res_deezer:
        key = (track["title"].strip().lower(), track["artist"].strip().lower())
        if key not in seen:
            seen.add(key)
            combined.append(track)

    # Rank results with metadata scoring engine
    ranked = rank_tracks(raw_query, combined, filter_unwanted=filter_unwanted)
    return ranked

def fetch_image_bytes(image_url: str):
    """Downloads image bytes from URL and verifies with Pillow. Returns bytes or None."""
    if not image_url:
        return None
    try:
        r = requests.get(image_url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and len(r.content) > 1000:
            # Verify image is valid
            img = Image.open(io.BytesIO(r.content))
            img.verify()
            return r.content
    except Exception as e:
        print(f"[Metadata] Error downloading image from {image_url}: {e}")
    return None

def fetch_pil_image(image_url: str, size: tuple = (100, 100)):
    """Downloads and returns a Pillow Image resized for GUI display, or None."""
    img_bytes = fetch_image_bytes(image_url)
    if img_bytes:
        try:
            img = Image.open(io.BytesIO(img_bytes))
            img = img.convert("RGBA")
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return img
        except Exception as e:
            print(f"[Metadata] Error processing thumbnail: {e}")
    return None
