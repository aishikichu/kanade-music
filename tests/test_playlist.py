"""
Unit tests for Playlist Resolver Service (Spotify, Apple Music, Deezer).
"""

import unittest
from app.playlist import (
    Track,
    Playlist,
    identify_platform_and_id,
    fetch_deezer_playlist,
    fetch_spotify_playlist,
    fetch_apple_music_playlist,
    playlist_resolver,
)


class TestPlaylistResolver(unittest.TestCase):
    def test_identify_spotify_urls(self):
        urls = [
            ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M", ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
            ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=e2938472", ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
            ("https://open.spotify.com/intl-es/playlist/37i9dQZF1DXcBWIGoYBM5M", ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
            ("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", ("spotify", "37i9dQZF1DXcBWIGoYBM5M")),
        ]
        for url, expected in urls:
            plat, pid = identify_platform_and_id(url)
            self.assertEqual((plat, pid), expected, f"Failed for {url}")

    def test_identify_deezer_urls(self):
        urls = [
            ("https://www.deezer.com/en/playlist/3155776842", ("deezer", "3155776842")),
            ("https://deezer.com/playlist/3155776842", ("deezer", "3155776842")),
            ("https://www.deezer.com/fr/playlist/123456789?utm_source=test", ("deezer", "123456789")),
        ]
        for url, expected in urls:
            plat, pid = identify_platform_and_id(url)
            self.assertEqual((plat, pid), expected, f"Failed for {url}")

    def test_identify_apple_music_urls(self):
        urls = [
            (
                "https://music.apple.com/us/playlist/alpha/pl.bcb2f44b6e194cfa8950a796b4e65cd1",
                ("apple_music", "pl.bcb2f44b6e194cfa8950a796b4e65cd1"),
            ),
            (
                "https://music.apple.com/playlist/pl.2b0e6e332fdf4b7a91164da3162127b5",
                ("apple_music", "pl.2b0e6e332fdf4b7a91164da3162127b5"),
            ),
            (
                "https://music.apple.com/gb/playlist/my-top-tracks/pl.u-1234abcd",
                ("apple_music", "pl.u-1234abcd"),
            ),
        ]
        for url, expected in urls:
            plat, pid = identify_platform_and_id(url)
            self.assertEqual((plat, pid), expected, f"Failed for {url}")

    def test_identify_invalid_url(self):
        plat, pid = identify_platform_and_id("https://youtube.com/watch?v=12345")
        self.assertIsNone(plat)
        self.assertIsNone(pid)

    def test_track_schema_to_dict(self):
        t = Track(
            title="One More Time",
            artist="Daft Punk",
            album="Discovery",
            duration_sec=320,
            isrc="USIR10000305",
            id="deezer_3167846",
        )
        d = t.to_dict()
        self.assertEqual(d["title"], "One More Time")
        self.assertEqual(d["artist"], "Daft Punk")
        self.assertEqual(d["album"], "Discovery")
        self.assertEqual(d["album_artist"], "Daft Punk")
        self.assertEqual(d["duration_sec"], 320)
        self.assertEqual(d["isrc"], "USIR10000305")
        # Ensure schema matches keys required by downloader
        required_keys = ["title", "artist", "album", "album_artist", "duration_sec", "isrc", "id"]
        for k in required_keys:
            self.assertIn(k, d)

    def test_live_deezer_playlist_resolver(self):
        url = "https://www.deezer.com/en/playlist/3155776842"
        pl = playlist_resolver.resolve(url, limit=5)
        self.assertEqual(pl.platform, "deezer")
        self.assertEqual(pl.playlist_id, "3155776842")
        self.assertGreater(len(pl.tracks), 0)
        first = pl.tracks[0]
        self.assertTrue(bool(first.title))
        self.assertTrue(bool(first.artist))
        self.assertGreater(first.duration_sec, 0)

    def test_live_spotify_playlist_resolver(self):
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        pl = playlist_resolver.resolve(url, limit=5)
        self.assertEqual(pl.platform, "spotify")
        self.assertEqual(pl.playlist_id, "37i9dQZF1DXcBWIGoYBM5M")
        self.assertGreater(len(pl.tracks), 0)
        first = pl.tracks[0]
        self.assertTrue(bool(first.title))
        self.assertTrue(bool(first.artist))
        self.assertGreater(first.duration_sec, 0)

    def test_live_apple_music_playlist_resolver(self):
        url = "https://music.apple.com/us/playlist/alpha/pl.bcb2f44b6e194cfa8950a796b4e65cd1"
        pl = playlist_resolver.resolve(url, limit=5)
        self.assertEqual(pl.platform, "apple_music")
        self.assertEqual(pl.playlist_id, "pl.bcb2f44b6e194cfa8950a796b4e65cd1")
        self.assertGreater(len(pl.tracks), 0)
        first = pl.tracks[0]
        self.assertTrue(bool(first.title))
        self.assertTrue(bool(first.artist))
        self.assertGreater(first.duration_sec, 0)


if __name__ == "__main__":
    unittest.main()
