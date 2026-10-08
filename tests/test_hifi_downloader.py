import os
import tempfile
import unittest
import subprocess
from app.downloader import format_output_path, tag_audio_file, get_ffmpeg_path
from app.hifi_resolver import CommunityHiFiResolver, hifi_resolver
from app.config import config
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.id3 import ID3

class TestHiFiDownloader(unittest.TestCase):

    def test_format_output_path_m4a_and_flac(self):
        meta = {
            "artist": "Daft Punk",
            "album": "Discovery",
            "title": "One More Time",
            "year": "2001",
            "track_number": 1,
        }
        # Default / clean .m4a
        folder_m4a, file_m4a = format_output_path("E:\\Music", meta, template_type="audiophile", extension=".m4a")
        self.assertTrue(file_m4a.endswith("01 - One More Time.m4a"))
        self.assertIn("Discovery (2001)", folder_m4a)

        # Legacy .flac
        folder_flac, file_flac = format_output_path("E:\\Music", meta, template_type="audiophile", extension=".flac")
        self.assertTrue(file_flac.endswith("01 - One More Time.flac"))

        # Flat template with .m4a
        folder_flat, file_flat = format_output_path("E:\\Music", meta, template_type="flat", extension=".m4a")
        self.assertTrue(file_flat.endswith("Daft Punk - One More Time.m4a"))

    def test_format_output_path_sanitization(self):
        meta = {
            "artist": "AC/DC",
            "album": "Back in Black: Live",
            "title": "Hells Bells? *Special*",
            "year": "1980",
            "track_number": 3,
        }
        folder, file_path = format_output_path("E:\\Music", meta, template_type="audiophile", extension=".m4a")
        # Check invalid Windows path characters are stripped or replaced
        for char in ['<', '>', ':', '"', '/', '\\', '|', '?', '*']:
            self.assertNotIn(char, os.path.basename(file_path).replace(".m4a", ""))

    def test_tag_audio_file_m4a(self):
        ffmpeg = get_ffmpeg_path()
        td = tempfile.mkdtemp()
        m4a_path = os.path.join(td, "test.m4a")
        # Generate 0.5s silent AAC/M4A via ffmpeg
        subprocess.run(
            [ffmpeg, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "0.5", "-c:a", "aac", m4a_path, "-y"],
            capture_output=True, check=True
        )

        dummy_cover = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
            + b"\x00" * 64
            + b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )
        meta = {
            "title": "Starboy",
            "artist": "The Weeknd",
            "album": "Starboy",
            "year": "2016",
            "genre": "R&B",
            "track_number": 1,
            "track_total": 18,
        }

        success = tag_audio_file(m4a_path, meta, cover_bytes=dummy_cover, save_folder_cover=False)
        self.assertTrue(success)

        # Verify tags
        audio = MP4(m4a_path)
        self.assertEqual(audio.get("\xa9nam"), ["Starboy"])
        self.assertEqual(audio.get("\xa9ART"), ["The Weeknd"])
        self.assertEqual(audio.get("\xa9alb"), ["Starboy"])
        self.assertEqual(audio.get("\xa9day"), ["2016"])
        self.assertEqual(audio.get("trkn"), [(1, 18)])
        self.assertGreater(len(audio.get("covr", [])), 0)

    def test_tag_audio_file_flac(self):
        ffmpeg = get_ffmpeg_path()
        td = tempfile.mkdtemp()
        flac_path = os.path.join(td, "test.flac")
        # Generate 0.5s silent FLAC via ffmpeg
        subprocess.run(
            [ffmpeg, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "0.5", "-c:a", "flac", flac_path, "-y"],
            capture_output=True, check=True
        )

        dummy_cover = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
            + b"\x00" * 64
            + b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )
        meta = {
            "title": "Get Lucky",
            "artist": "Daft Punk",
            "album": "Random Access Memories",
            "year": "2013",
            "genre": "Disco",
            "track_number": 8,
            "track_total": 13,
        }

        success = tag_audio_file(flac_path, meta, cover_bytes=dummy_cover, save_folder_cover=False)
        self.assertTrue(success)

        # Verify Vorbis comments and Picture block
        audio = FLAC(flac_path)
        self.assertEqual(audio.get("TITLE"), ["Get Lucky"])
        self.assertEqual(audio.get("ARTIST"), ["Daft Punk"])
        self.assertEqual(audio.get("ALBUM"), ["Random Access Memories"])
        self.assertEqual(audio.get("TRACKNUMBER"), ["8"])
        self.assertGreater(len(audio.pictures), 0)

    def test_community_hifi_resolver_bandcamp_direct(self):
        res = hifi_resolver.resolve_lossless_stream({
            "title": "Ambient Track",
            "artist": "Artist",
            "external_url": "https://artist.bandcamp.com/track/ambient-track"
        })
        self.assertIsNotNone(res)
        self.assertEqual(res["format"], "flac")
        self.assertTrue(res["is_true_lossless"])

    def test_community_hifi_resolver_timeout_graceful(self):
        # Resolver with 0.001s timeout will gracefully fail and return None
        fast_resolver = CommunityHiFiResolver(timeout=0.001)
        res = fast_resolver.resolve_lossless_stream({
            "title": "Non-existent Track 99999",
            "artist": "Nobody",
            "isrc": "USXX12345678"
        })
        self.assertIsNone(res)

    def test_flac_24bit_tagging_and_bit_depth(self):
        ffmpeg = get_ffmpeg_path()
        td = tempfile.mkdtemp()
        flac_24_path = os.path.join(td, "test_24bit.flac")
        # Generate 0.5s 24-bit FLAC via ffmpeg
        subprocess.run(
            [ffmpeg, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "0.5",
             "-c:a", "flac", "-sample_fmt", "s32", "-bits_per_raw_sample", "24", "-ar", "48000", flac_24_path, "-y"],
            capture_output=True, check=True
        )

        meta = {
            "title": "Hi-Res Master Track",
            "artist": "Studio Artist",
            "album": "Studio Album",
            "year": "2024",
            "genre": "Classical",
            "track_number": 1,
        }
        success = tag_audio_file(flac_24_path, meta, cover_bytes=None, save_folder_cover=False)
        self.assertTrue(success)

        audio = FLAC(flac_24_path)
        self.assertEqual(audio.info.bits_per_sample, 24)
        self.assertEqual(audio.info.sample_rate, 48000)
        self.assertIn("24-bit", audio.get("COMMENT", [""])[0])
        self.assertIn("Hi-Res", audio.get("COMMENT", [""])[0])

    def test_flac_16bit_tagging_and_bit_depth(self):
        ffmpeg = get_ffmpeg_path()
        td = tempfile.mkdtemp()
        flac_16_path = os.path.join(td, "test_16bit.flac")
        # Generate 0.5s 16-bit FLAC via ffmpeg
        subprocess.run(
            [ffmpeg, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "0.5",
             "-c:a", "flac", "-sample_fmt", "s16", "-ar", "44100", flac_16_path, "-y"],
            capture_output=True, check=True
        )

        meta = {
            "title": "CD Track",
            "artist": "CD Artist",
            "album": "CD Album",
            "year": "1999",
            "genre": "Pop",
            "track_number": 2,
        }
        success = tag_audio_file(flac_16_path, meta, cover_bytes=None, save_folder_cover=False)
        self.assertTrue(success)

        audio = FLAC(flac_16_path)
        self.assertEqual(audio.info.bits_per_sample, 16)
        self.assertEqual(audio.info.sample_rate, 44100)
        self.assertIn("16-bit", audio.get("COMMENT", [""])[0])

if __name__ == "__main__":
    unittest.main()
