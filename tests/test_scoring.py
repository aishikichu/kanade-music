"""
Unit tests for metadata scoring and ranking engine in app/scoring.py
"""

import unittest
from app.scoring import (
    score_track,
    score_track_detailed,
    rank_tracks,
    extract_isrc,
    extract_duration,
    detect_unwanted_tags,
    is_isrc,
    normalize_text,
)


class TestScoringEngine(unittest.TestCase):
    def setUp(self):
        # Sample candidate tracks for "Daft Punk - One More Time"
        self.original_track = {
            "id": "1",
            "title": "One More Time",
            "artist": "Daft Punk",
            "album": "Discovery",
            "isrc": "USIR10000305",
            "duration_sec": 320,
        }

        self.remix_track = {
            "id": "2",
            "title": "One More Time (Club Mix)",
            "artist": "Daft Punk",
            "album": "Discovery (Club Remixes)",
            "isrc": "FR0101010101",
            "duration_sec": 480,
        }

        self.live_track = {
            "id": "3",
            "title": "One More Time (Live - Alive 2007)",
            "artist": "Daft Punk",
            "album": "Alive 2007",
            "isrc": "FR0101010102",
            "duration_sec": 375,
        }

        self.tribute_cover_track = {
            "id": "4",
            "title": "One More Time",
            "artist": "One More Time - A Tribute to Daft Punk",
            "album": "The Ultimate Daft Punk Tribute",
            "isrc": "USXX00000001",
            "duration_sec": 318,
        }

        self.acoustic_cover_track = {
            "id": "5",
            "title": "One More Time (Acoustic Cover)",
            "artist": "Various Artists",
            "album": "Acoustic Pop Covers",
            "isrc": "GB0000000001",
            "duration_sec": 210,
        }

        self.radio_edit_track = {
            "id": "6",
            "title": "One More Time [Radio Edit]",
            "artist": "Daft Punk",
            "album": "One More Time - Single",
            "isrc": "USIR10000306",
            "duration_sec": 235,
        }

    def test_original_ranked_first_for_clean_query(self):
        query = "Daft Punk One More Time"
        tracks = [
            self.remix_track,
            self.live_track,
            self.tribute_cover_track,
            self.acoustic_cover_track,
            self.radio_edit_track,
            self.original_track,
        ]

        ranked = rank_tracks(query, tracks)
        # Original track should be #1 by a significant margin
        self.assertEqual(ranked[0]["id"], self.original_track["id"])
        self.assertGreater(ranked[0]["match_score"], ranked[1]["match_score"])

    def test_remix_penalty_applied_when_not_in_query(self):
        query = "Daft Punk One More Time"
        details_orig = score_track_detailed(query, self.original_track)
        details_remix = score_track_detailed(query, self.remix_track)

        self.assertEqual(details_orig["penalty"], 0.0)
        self.assertGreater(details_remix["penalty"], 0.0)
        self.assertTrue(any("remix" in p.lower() for p in details_remix["penalties_applied"]))
        self.assertGreater(details_orig["total_score"], details_remix["total_score"] + 40)

    def test_live_penalty_applied_when_not_in_query(self):
        query = "Daft Punk One More Time"
        details_live = score_track_detailed(query, self.live_track)
        self.assertGreater(details_live["penalty"], 0.0)
        self.assertTrue(any("live" in p.lower() for p in details_live["penalties_applied"]))

    def test_cover_and_tribute_penalties_applied(self):
        query = "Daft Punk One More Time"
        details_tribute = score_track_detailed(query, self.tribute_cover_track)
        details_cover = score_track_detailed(query, self.acoustic_cover_track)

        self.assertGreater(details_tribute["penalty"], 50.0)
        self.assertGreater(details_cover["penalty"], 50.0)

    def test_no_penalty_when_user_explicitly_queries_remix(self):
        query = "Daft Punk One More Time Club Mix"
        details_remix = score_track_detailed(query, self.remix_track)
        # Since 'Club Mix' is explicitly in the query, remix penalty should NOT apply
        self.assertFalse(any("remix" in p.lower() for p in details_remix["penalties_applied"]))

        # Remix track should rank #1 for this explicit query
        ranked = rank_tracks(query, [self.original_track, self.remix_track])
        self.assertEqual(ranked[0]["id"], self.remix_track["id"])

    def test_exact_artist_priority_over_partial_artist(self):
        # Queen vs Queen Tribute Band vs The Queen Experience
        track_queen = {
            "title": "Bohemian Rhapsody",
            "artist": "Queen",
            "album": "A Night at the Opera",
        }
        track_tribute = {
            "title": "Bohemian Rhapsody",
            "artist": "The Queen Tribute Band",
            "album": "Tribute to Queen",
        }
        track_experience = {
            "title": "Bohemian Rhapsody",
            "artist": "The Queen Experience",
            "album": "Live Experience",
        }

        query = "Queen Bohemian Rhapsody"
        score_queen = score_track(query, track_queen)
        score_tribute = score_track(query, track_tribute)
        score_exp = score_track(query, track_experience)

        self.assertGreater(score_queen, score_tribute + 50)
        self.assertGreater(score_queen, score_exp + 50)

    def test_exact_artist_priority_single_word_artist(self):
        track_adele = {"title": "Hello", "artist": "Adele"}
        track_adelitas = {"title": "Hello", "artist": "Adelitas Way"}
        track_tribute = {"title": "Hello", "artist": "Adele Tribute Project"}

        query = "Adele"
        score_adele = score_track(query, track_adele)
        score_adelitas = score_track(query, track_adelitas)
        score_tribute = score_track(query, track_tribute)

        self.assertGreater(score_adele, score_adelitas + 50)
        self.assertGreater(score_adele, score_tribute + 50)

    def test_isrc_matching(self):
        query = "USIR10000305"
        score_match = score_track(query, self.original_track)
        score_other = score_track(query, self.remix_track)

        self.assertGreater(score_match, 900.0)
        self.assertLess(score_other, 100.0)

    def test_duration_matching(self):
        # Query specifies exact duration 5:20 (320s)
        query_with_dur = "Daft Punk One More Time 5:20"
        score_orig = score_track(query_with_dur, self.original_track)  # 320s
        score_edit = score_track(query_with_dur, self.radio_edit_track)  # 235s

        self.assertGreater(score_orig, score_edit)

        # Structured query with duration
        structured_target = {
            "artist": "Daft Punk",
            "title": "One More Time",
            "duration": 320,
        }
        score_exact_dur = score_track(structured_target, self.original_track)
        score_mismatch_dur = score_track(structured_target, self.remix_track)  # 480s
        self.assertGreater(score_exact_dur, score_mismatch_dur + 30)

    def test_negative_filtering_strict_mode(self):
        query = "Daft Punk One More Time"
        tracks = [
            self.remix_track,
            self.live_track,
            self.original_track,
            self.tribute_cover_track,
        ]

        # Without filter: returns all 4 sorted
        all_ranked = rank_tracks(query, tracks, filter_unwanted=False)
        self.assertEqual(len(all_ranked), 4)

        # With filter: drops tracks that received unwanted penalties
        clean_ranked = rank_tracks(query, tracks, filter_unwanted=True)
        self.assertEqual(len(clean_ranked), 1)
        self.assertEqual(clean_ranked[0]["id"], self.original_track["id"])

    def test_filter_unwanted_fallback_if_all_penalized(self):
        # If every candidate has a penalty, filter_unwanted safely returns sorted list rather than empty
        query = "Rare Track"
        tracks = [self.remix_track, self.live_track]
        clean_ranked = rank_tracks(query, tracks, filter_unwanted=True)
        self.assertEqual(len(clean_ranked), 2)

    def test_hyphenated_isrc_extraction_and_matching(self):
        query = "Track US-IR1-00-00305"
        score_match = score_track(query, self.original_track)
        self.assertGreater(score_match, 900.0)

    def test_diacritics_normalization(self):
        track_accent = {
            "title": "Army of Me",
            "artist": "Björk",
            "album": "Post",
        }
        query_plain = "Bjork Army of Me"
        query_accent = "Björk Army of Me"

        score1 = score_track(query_plain, track_accent)
        score2 = score_track(query_accent, track_accent)
        self.assertEqual(score1, score2)
        self.assertGreater(score1, 150.0)

    def test_karaoke_and_in_the_style_of_penalty(self):
        track_karaoke = {
            "title": "One More Time (In the Style of Daft Punk) [Karaoke Version]",
            "artist": "The Karaoke Universe",
            "album": "Electro Karaoke Vol. 1",
        }
        query = "Daft Punk One More Time"
        details = score_track_detailed(query, track_karaoke)
        self.assertGreater(details["penalty"], 60.0)
        self.assertLess(details["total_score"], 40.0)

    def test_radio_edit_penalty_when_not_in_query(self):
        query = "Daft Punk One More Time"
        details = score_track_detailed(query, self.radio_edit_track)
        self.assertTrue(any("edit" in p.lower() for p in details["penalties_applied"]))
        self.assertGreater(details["penalty"], 0.0)

    def test_radio_edit_no_penalty_when_requested(self):
        query = "Daft Punk One More Time Radio Edit"
        details = score_track_detailed(query, self.radio_edit_track)
        self.assertEqual(details["penalty"], 0.0)
        ranked = rank_tracks(query, [self.original_track, self.radio_edit_track])
        self.assertEqual(ranked[0]["id"], self.radio_edit_track["id"])


if __name__ == "__main__":
    unittest.main()
