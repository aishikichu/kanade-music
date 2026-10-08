"""
Playlist Resolver Service for Spotify, Apple Music, and Deezer.

Resolves playlist URLs, extracts tracks with standard metadata
(Track Name, Artist, Album, Duration, ISRC), and returns standardized Track objects
compatible with the search and download queue.
"""

import json
import os
import re
import urllib.parse
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import requests

from app.config import config

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Track:
    """Standardized internal Track schema used across search and download queue."""
    title: str
    artist: str
    album: str = "Unknown Album"
    duration_sec: int = 0
    isrc: str = ""
    id: str = ""
    album_artist: str = ""
    year: str = ""
    genre: str = "Music"
    track_number: int = 1
    track_total: int = 1
    disc_number: int = 1
    artwork_url: str = ""
    thumbnail_url: str = ""
    preview_url: str = ""
    source: str = ""
    platform: str = ""
    external_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d.get("album_artist"):
            d["album_artist"] = d["artist"]
        return d


@dataclass
class Playlist:
    """Standardized internal Playlist schema."""
    platform: str  # 'spotify', 'apple_music', 'deezer'
    playlist_id: str
    title: str
    description: str = ""
    cover_url: str = ""
    creator: str = ""
    total_tracks: int = 0
    tracks: List[Track] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "playlist_id": self.playlist_id,
            "title": self.title,
            "description": self.description,
            "cover_url": self.cover_url,
            "creator": self.creator,
            "total_tracks": self.total_tracks,
            "tracks": [t.to_dict() for t in self.tracks],
        }


def unshorten_url(url: str, timeout: int = 5) -> str:
    """Follows HTTP redirects to resolve shortened URLs (e.g. spotify.link, deezer.page.link)."""
    if "spotify.link" in url or "deezer.page.link" in url or "t.co" in url or "bit.ly" in url:
        try:
            resp = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=timeout)
            return resp.url
        except Exception:
            try:
                resp = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=timeout)
                return resp.url
            except Exception:
                pass
    return url


def identify_platform_and_id(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Identifies music streaming platform and extracts the playlist ID.
    Supported platforms: 'spotify', 'apple_music', 'deezer'.
    """
    if not url or not isinstance(url, str):
        return None, None

    clean_url = unshorten_url(url.strip())

    # 1. Spotify
    # Patterns:
    # - https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=...
    # - https://open.spotify.com/intl-xx/playlist/37i9dQZF1DXcBWIGoYBM5M
    # - spotify:playlist:37i9dQZF1DXcBWIGoYBM5M
    sp_match = re.search(r"open\.spotify\.com/(?:[a-zA-Z\-]+/)?playlist/([a-zA-Z0-9]{22})", clean_url, re.I)
    if sp_match:
        return "spotify", sp_match.group(1)

    sp_uri_match = re.search(r"spotify:playlist:([a-zA-Z0-9]{22})", clean_url, re.I)
    if sp_uri_match:
        return "spotify", sp_uri_match.group(1)

    # 2. Deezer
    # Patterns:
    # - https://www.deezer.com/en/playlist/3155776842
    # - https://deezer.com/playlist/3155776842
    dz_match = re.search(r"deezer\.com/(?:[a-zA-Z]{2}/)?playlist/(\d+)", clean_url, re.I)
    if dz_match:
        return "deezer", dz_match.group(1)

    # 3. Apple Music
    # Patterns:
    # - https://music.apple.com/us/playlist/alpha/pl.bcb2f44b6e194cfa8950a796b4e65cd1
    # - https://music.apple.com/playlist/pl.2b0e6e332fdf4b7a91164da3162127b5
    # - https://music.apple.com/us/playlist/my-favorites/pl.u-a1b2c3d4e5
    am_match = re.search(r"music\.apple\.com/(?:[a-zA-Z]{2}/)?playlist/(?:[^/]+/)?(pl\.[a-zA-Z0-9\-]+)", clean_url, re.I)
    if am_match:
        return "apple_music", am_match.group(1)

    return None, None


# ---------------- Deezer Playlist Resolver ----------------

def fetch_deezer_playlist(playlist_id: str, limit: int = 200, timeout: int = 10) -> Playlist:
    """Fetches tracklist from Deezer Public API."""
    url = f"https://api.deezer.com/playlist/{playlist_id}"
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    if resp.status_code != 200:
        raise ValueError(f"Deezer playlist not found (HTTP {resp.status_code})")

    data = resp.json()
    if data.get("error"):
        err_msg = data["error"].get("message", "Unknown Deezer error")
        raise ValueError(f"Deezer API Error: {err_msg}")

    p_title = data.get("title", "Deezer Playlist")
    p_desc = data.get("description", "")
    p_cover = data.get("picture_xl") or data.get("picture_big") or data.get("picture_medium", "")
    p_creator = data.get("creator", {}).get("name", "Deezer User")
    total = data.get("nb_tracks", 0)

    tracks_data = data.get("tracks", {}).get("data", [])

    # If playlist has more than 100 tracks, paginate up to requested limit
    if total > len(tracks_data) and len(tracks_data) < limit:
        current_index = len(tracks_data)
        while current_index < min(total, limit):
            page_url = f"https://api.deezer.com/playlist/{playlist_id}/tracks?limit=100&index={current_index}"
            try:
                page_resp = requests.get(page_url, headers=HEADERS, timeout=timeout)
                if page_resp.status_code == 200:
                    page_data = page_resp.json()
                    new_tracks = page_data.get("data", [])
                    if not new_tracks:
                        break
                    tracks_data.extend(new_tracks)
                    current_index += len(new_tracks)
                else:
                    break
            except Exception:
                break

    tracks = []
    for idx, item in enumerate(tracks_data[:limit], 1):
        artist_obj = item.get("artist", {})
        album_obj = item.get("album", {})
        hd_art = album_obj.get("cover_xl") or album_obj.get("cover_big") or album_obj.get("cover_medium", "")
        thumb_art = album_obj.get("cover_medium") or album_obj.get("cover_small", "")
        duration = int(item.get("duration", 0))
        isrc = item.get("isrc", "")

        t = Track(
            title=item.get("title", "Unknown Track"),
            artist=artist_obj.get("name", "Unknown Artist"),
            album=album_obj.get("title", "Unknown Album"),
            album_artist=artist_obj.get("name", "Unknown Artist"),
            duration_sec=duration,
            isrc=isrc,
            id=f"deezer_{item.get('id')}",
            track_number=item.get("track_position", idx),
            track_total=total,
            artwork_url=hd_art or p_cover,
            thumbnail_url=thumb_art or p_cover,
            preview_url=item.get("preview", ""),
            source="Deezer Playlist",
            platform="deezer",
            external_url=item.get("link", f"https://www.deezer.com/track/{item.get('id')}"),
        )
        tracks.append(t)

    return Playlist(
        platform="deezer",
        playlist_id=str(playlist_id),
        title=p_title,
        description=p_desc,
        cover_url=p_cover,
        creator=p_creator,
        total_tracks=len(tracks),
        tracks=tracks,
    )


# ---------------- Spotify Playlist Resolver ----------------

def _get_spotify_access_token(client_id: str, client_secret: str, timeout: int = 8) -> Optional[str]:
    """Obtains a client_credentials access token from Spotify Accounts API."""
    token_url = "https://accounts.spotify.com/api/token"
    try:
        r = requests.post(
            token_url,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"User-Agent": HEADERS["User-Agent"]},
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception as e:
        print(f"[Spotify] Auth token error: {e}")
    return None


def fetch_spotify_playlist(playlist_id: str, limit: int = 200, timeout: int = 10) -> Playlist:
    """
    Fetches playlist from Spotify.
    Attempts official Spotify Web API if client credentials are provided,
    otherwise uses high-reliability Spotify Embed __NEXT_DATA__ extraction (zero credentials required).
    """
    client_id = os.environ.get("SPOTIFY_CLIENT_ID") or config.get("spotify_client_id", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET") or config.get("spotify_client_secret", "")

    # Method 1: Official Spotify Web API with Client Credentials
    if client_id and client_secret:
        token = _get_spotify_access_token(client_id, client_secret, timeout=timeout)
        if token:
            try:
                return _fetch_spotify_via_api(playlist_id, token, limit=limit, timeout=timeout)
            except Exception as e:
                print(f"[Spotify] Web API error, falling back to embed extraction: {e}")

    # Method 2: Spotify Embed Extraction (No API key required)
    return _fetch_spotify_via_embed(playlist_id, limit=limit, timeout=timeout)


def _fetch_spotify_via_api(playlist_id: str, token: str, limit: int = 200, timeout: int = 10) -> Playlist:
    headers = {"Authorization": f"Bearer {token}", "User-Agent": HEADERS["User-Agent"]}
    api_url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
    resp = requests.get(api_url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        raise ValueError(f"Spotify API error (HTTP {resp.status_code})")

    data = resp.json()
    p_title = data.get("name", "Spotify Playlist")
    p_desc = data.get("description", "")
    images = data.get("images", [])
    p_cover = images[0].get("url", "") if images else ""
    p_creator = data.get("owner", {}).get("display_name", "Spotify User")

    tracks = []
    items = data.get("tracks", {}).get("items", [])
    total = data.get("tracks", {}).get("total", len(items))

    for idx, item in enumerate(items[:limit], 1):
        tr = item.get("track")
        if not tr:
            continue
        artists = [a.get("name", "") for a in tr.get("artists", []) if a.get("name")]
        artist_name = ", ".join(artists) or "Unknown Artist"
        album_obj = tr.get("album", {})
        album_name = album_obj.get("name", "Unknown Album")
        alb_images = album_obj.get("images", [])
        hd_art = alb_images[0].get("url", "") if alb_images else p_cover
        thumb_art = alb_images[-1].get("url", "") if alb_images else p_cover
        duration = int(tr.get("duration_ms", 0) / 1000)
        isrc = tr.get("external_ids", {}).get("isrc", "")
        year = (album_obj.get("release_date") or "")[:4]

        t = Track(
            title=tr.get("name", "Unknown Track"),
            artist=artist_name,
            album=album_name,
            album_artist=artists[0] if artists else artist_name,
            year=year,
            duration_sec=duration,
            isrc=isrc,
            id=f"spotify_{tr.get('id')}",
            track_number=tr.get("track_number", idx),
            track_total=total,
            artwork_url=hd_art,
            thumbnail_url=thumb_art,
            preview_url=tr.get("preview_url") or "",
            source="Spotify Playlist",
            platform="spotify",
            external_url=tr.get("external_urls", {}).get("spotify", f"https://open.spotify.com/track/{tr.get('id')}"),
        )
        tracks.append(t)

    return Playlist(
        platform="spotify",
        playlist_id=str(playlist_id),
        title=p_title,
        description=p_desc,
        cover_url=p_cover,
        creator=p_creator,
        total_tracks=len(tracks),
        tracks=tracks,
    )


def _fetch_spotify_via_embed(playlist_id: str, limit: int = 200, timeout: int = 10) -> Playlist:
    embed_url = f"https://open.spotify.com/embed/playlist/{playlist_id}"
    resp = requests.get(embed_url, headers=HEADERS, timeout=timeout)
    if resp.status_code != 200:
        raise ValueError(f"Spotify playlist not found (HTTP {resp.status_code})")

    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
    if not match:
        raise ValueError("Could not extract playlist metadata from Spotify embed page.")

    try:
        data = json.loads(match.group(1))
    except Exception as e:
        raise ValueError(f"Failed to parse Spotify embed data: {e}")

    entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
    p_title = entity.get("title", "Spotify Playlist")
    p_desc = entity.get("subtitle", "")
    p_cover = entity.get("visualIdentity", {}).get("image", [{}])[0].get("url", "")
    track_list = entity.get("trackList", [])

    tracks = []
    for idx, item in enumerate(track_list[:limit], 1):
        uri = item.get("uri", "")
        track_id = uri.split(":")[-1] if ":" in uri else f"track_{idx}"
        duration = int(item.get("duration", 0) / 1000)
        audio_preview = item.get("audioPreview", {}).get("url", "")

        t = Track(
            title=item.get("title", "Unknown Track"),
            artist=item.get("subtitle", "Unknown Artist"),
            album="Spotify Playlist Collection",
            album_artist=item.get("subtitle", "Unknown Artist"),
            duration_sec=duration,
            isrc=item.get("isrc") or "",
            id=f"spotify_{track_id}",
            track_number=idx,
            track_total=len(track_list),
            artwork_url=p_cover,
            thumbnail_url=p_cover,
            preview_url=audio_preview or "",
            source="Spotify Playlist",
            platform="spotify",
            external_url=f"https://open.spotify.com/track/{track_id}" if track_id else "",
        )
        tracks.append(t)

    return Playlist(
        platform="spotify",
        playlist_id=str(playlist_id),
        title=p_title,
        description=p_desc,
        cover_url=p_cover,
        creator="Spotify",
        total_tracks=len(tracks),
        tracks=tracks,
    )


# ---------------- Apple Music Playlist Resolver ----------------

def _parse_iso8601_duration(dur_str: str) -> int:
    """Parses ISO 8601 duration strings like 'PT3M45S' into total seconds."""
    if not dur_str:
        return 0
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", dur_str)
    if not m:
        return 0
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    secs = int(m.group(3) or 0)
    return hours * 3600 + mins * 60 + secs


def fetch_apple_music_playlist(url_or_id: str, limit: int = 200, timeout: int = 10) -> Playlist:
    """
    Fetches playlist tracklist from Apple Music public web interface using
    serialized server data and JSON-LD structured metadata.
    """
    if url_or_id.startswith("http"):
        canonical_url = url_or_id
        _, p_id = identify_platform_and_id(url_or_id)
        playlist_id = p_id or "apple_playlist"
    else:
        playlist_id = url_or_id
        canonical_url = f"https://music.apple.com/us/playlist/{playlist_id}"

    resp = requests.get(canonical_url, headers=HEADERS, timeout=timeout)
    if resp.status_code != 200:
        raise ValueError(f"Apple Music playlist not found (HTTP {resp.status_code})")

    html = resp.text
    tracks = []
    p_title = "Apple Music Playlist"
    p_desc = ""
    p_cover = ""

    # Strategy A: Extract from serialized-server-data (highest detail: artist, album, full track list)
    m_server = re.findall(r'<script[^>]*id="serialized-server-data"[^>]*>(.*?)</script>', html, re.DOTALL)
    if m_server:
        try:
            s_data = json.loads(m_server[0])
            items_container = s_data.get("data", [])
            if items_container:
                sections = items_container[0].get("data", {}).get("sections", [])
                for sec in sections:
                    sub_items = sec.get("items", [])
                    # The tracklist section contains multiple track items with duration or artistName
                    if len(sub_items) >= 2 and any(it.get("duration") or it.get("artistName") for it in sub_items):
                        for idx, itm in enumerate(sub_items[:limit], 1):
                            title = itm.get("title") or "Unknown Track"
                            artist = itm.get("artistName") or "Unknown Artist"
                            # Album name from tertiaryLinks
                            album = "Unknown Album"
                            tertiary = itm.get("tertiaryLinks", [])
                            if tertiary and tertiary[0].get("title"):
                                album = tertiary[0].get("title")

                            # Duration in ms
                            duration_ms = itm.get("duration") or 0
                            duration_sec = int(duration_ms / 1000)

                            # High-res artwork
                            art_dict = itm.get("artwork", {}).get("dictionary", {})
                            art_template = art_dict.get("url", "")
                            hd_art = art_template.replace("{w}x{h}bb.{f}", "1400x1400bb.jpg") if art_template else ""
                            thumb_art = art_template.replace("{w}x{h}bb.{f}", "150x150bb.jpg") if art_template else ""

                            adam_id = itm.get("contentDescriptor", {}).get("identifiers", {}).get("storeAdamID", f"{idx}")

                            t = Track(
                                title=title,
                                artist=artist,
                                album=album,
                                album_artist=artist,
                                duration_sec=duration_sec,
                                isrc="",
                                id=f"apple_{adam_id}",
                                track_number=idx,
                                track_total=len(sub_items),
                                artwork_url=hd_art,
                                thumbnail_url=thumb_art,
                                preview_url="",
                                source="Apple Music Playlist",
                                platform="apple_music",
                                external_url=f"https://music.apple.com/song/{adam_id}",
                            )
                            tracks.append(t)
                        break
        except Exception as e:
            print(f"[AppleMusic] Error parsing serialized-server-data: {e}")

    # Strategy B: JSON-LD Fallback
    if not tracks:
        ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
        for block in ld_matches:
            try:
                ld = json.loads(block)
                if ld.get("@type") == "MusicPlaylist":
                    p_title = ld.get("name", p_title)
                    ld_tracks = ld.get("track", [])
                    for idx, it in enumerate(ld_tracks[:limit], 1):
                        name = it.get("name", "Unknown Track")
                        dur_str = it.get("duration", "")
                        dur_sec = _parse_iso8601_duration(dur_str)
                        audio_obj = it.get("audio", {})
                        thumb = audio_obj.get("thumbnailUrl", "")
                        hd_art = thumb.replace("1200x630bb.jpg", "1400x1400bb.jpg") if thumb else ""
                        url_song = it.get("url", "")
                        adam_id = url_song.split("/")[-1] if "/" in url_song else f"{idx}"

                        t = Track(
                            title=name,
                            artist="Apple Music Artist",
                            album=p_title,
                            album_artist="Apple Music Artist",
                            duration_sec=dur_sec,
                            isrc="",
                            id=f"apple_{adam_id}",
                            track_number=idx,
                            track_total=len(ld_tracks),
                            artwork_url=hd_art,
                            thumbnail_url=thumb,
                            source="Apple Music Playlist",
                            platform="apple_music",
                            external_url=url_song,
                        )
                        tracks.append(t)
            except Exception:
                pass

    # Extract playlist title from title tag if empty
    if p_title == "Apple Music Playlist":
        m_head = re.search(r"<title>(.*?)(?: - Playlist by .*?| on Apple Music)?</title>", html, re.I)
        if m_head:
            p_title = m_head.group(1).strip()

    return Playlist(
        platform="apple_music",
        playlist_id=str(playlist_id),
        title=p_title,
        description=p_desc,
        cover_url=p_cover or (tracks[0].artwork_url if tracks else ""),
        creator="Apple Music",
        total_tracks=len(tracks),
        tracks=tracks,
    )


# ---------------- Master Playlist Resolver Service ----------------

class PlaylistResolverService:
    """Universal Playlist Resolver Service for Spotify, Apple Music, and Deezer."""

    def __init__(self):
        pass

    def identify(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """Identifies platform and extracts playlist ID."""
        return identify_platform_and_id(url)

    def resolve(self, url: str, limit: int = 200) -> Playlist:
        """
        Accepts any playlist URL from Spotify, Deezer, or Apple Music,
        resolves the platform and ID, and extracts standard Tracklist metadata.
        """
        platform, playlist_id = self.identify(url)
        if not platform or not playlist_id:
            raise ValueError(
                f"Unsupported or unrecognized playlist URL. Please provide a valid link from Spotify, Apple Music, or Deezer.\nInput: {url}"
            )

        if platform == "deezer":
            return fetch_deezer_playlist(playlist_id, limit=limit)
        elif platform == "spotify":
            return fetch_spotify_playlist(playlist_id, limit=limit)
        elif platform == "apple_music":
            return fetch_apple_music_playlist(url, limit=limit)
        else:
            raise ValueError(f"Platform '{platform}' is not supported.")

    def queue_playlist(self, url: str, downloader_instance=None, limit: int = 200) -> Dict[str, Any]:
        """
        Resolves playlist and queues all tracks into the downloader queue.
        Returns playlist details and assigned task IDs.
        """
        from app.downloader import downloader as default_downloader
        dl = downloader_instance or default_downloader

        playlist = self.resolve(url, limit=limit)
        task_ids = []

        for track in playlist.tracks:
            task = dl.add_search_item_to_queue(track.to_dict())
            task_ids.append(task.task_id)

        return {
            "success": True,
            "platform": playlist.platform,
            "playlist_title": playlist.title,
            "total_tracks": len(playlist.tracks),
            "task_ids": task_ids,
            "playlist": playlist.to_dict(),
        }


# Global singleton instance
playlist_resolver = PlaylistResolverService()
