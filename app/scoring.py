"""
Metadata Scoring and Ranking Engine for Kanade Music Search Service.

Provides intelligent ranking to prioritize original studio recordings over
remixes, covers, live versions, and edits, with exact artist prioritization,
negative filtering/penalties, ISRC matching, and duration verification.
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple, Union

# Regex for ISRC: 2 alpha chars, 3 alphanumeric, 2 digits (year), 5 digits (designation)
ISRC_REGEX = re.compile(r"\b([A-Z]{2})[- ]?([A-Z0-9]{3})[- ]?([0-9]{2})[- ]?([0-9]{5})\b", re.IGNORECASE)

# Common unwanted tag definitions with regex patterns, keywords, and default penalty weights
UNWANTED_TAG_SPECS = {
    "remix": {
        "keywords": [
            "remix", "re-mix", "rmx", "club mix", "extended mix", "dub mix",
            "vip mix", "dance mix", "bootleg", "mashup", "flip", "trance mix",
            "house mix", "techno mix", "dnb mix", "drum and bass mix", "trap mix", "mix"
        ],
        "regex": re.compile(
            r"\b(?:re-?mix(?:es)?|rmx|bootleg|mashup|flip|(?:club|dance|extended|dub|vip|house|techno|trance|disco|acoustic|spanish|vocal|instrumental|radio|electronic|summer|winter|album|original)\s+mix)\b|\([^\)]*\bmix(?:es)?\b[^\)]*\)|\[[^\]]*\bmix(?:es)?\b[^\)]*\]",
            re.IGNORECASE,
        ),
        "penalty": 55.0,
        "description": "Remix or alternative club/electronic mix",
    },
    "live": {
        "keywords": [
            "live", "live at", "live from", "in concert", "on tour",
            "live version", "live session", "unplugged", "acoustic live",
            "live in", "live recording", "en vivo"
        ],
        "regex": re.compile(
            r"\b(?:live(?:\s+at|\s+from|\s+in|\s+on|\s+version|\s+session|\s+recording|\s+tour|\s+concert)?|in concert|on tour|unplugged|en vivo)\b|\([^\)]*\blive\b[^\)]*\)|\[[^\]]*\blive\b[^\]]*\]",
            re.IGNORECASE,
        ),
        "penalty": 55.0,
        "description": "Live concert recording",
    },
    "cover": {
        "keywords": [
            "cover", "tribute", "karaoke", "originally performed by",
            "in the style of", "made famous by", "backing track", "instrumental version",
            "tribute band", "cover band", "acoustic cover", "piano cover", "lofi", "lo-fi"
        ],
        "regex": re.compile(
            r"\b(?:cover(?:ed)?|tribute(?:\s+to|\s+band)?|karaoke|originally performed by|in the style of|made famous by|backing track|lo-?fi(?:\s+cover|\s+fruits)?)\b|\([^\)]*\b(?:cover|tribute|karaoke)\b[^\)]*\)|\[[^\]]*\b(?:cover|tribute|karaoke)\b[^\)]*\]",
            re.IGNORECASE,
        ),
        "penalty": 75.0,
        "description": "Cover version, tribute band, or karaoke backing track",
    },
    "edit": {
        "keywords": [
            "edit", "radio edit", "club edit", "short edit", "clean edit",
            "extended edit", "single edit"
        ],
        "regex": re.compile(
            r"\b(?:(?:radio|club|short|clean|extended|single|album)\s+edit|edit)\b|\([^\)]*\bedit\b[^\)]*\)|\[[^\]]*\bedit\b[^\]]*\]",
            re.IGNORECASE,
        ),
        "penalty": 35.0,
        "description": "Radio edit or shortened / altered version",
    },
    "acoustic": {
        "keywords": ["acoustic", "acoustic version"],
        "regex": re.compile(r"\b(?:acoustic(?:\s+version)?)\b", re.IGNORECASE),
        "penalty": 30.0,
        "description": "Acoustic rendition",
    },
    "instrumental": {
        "keywords": ["instrumental", "orchestral version", "piano version", "minus one"],
        "regex": re.compile(r"\b(?:instrumental(?:\s+version)?|orchestral version|piano version|minus one)\b", re.IGNORECASE),
        "penalty": 40.0,
        "description": "Instrumental or non-vocal version",
    },
    "speed": {
        "keywords": ["sped up", "speed up", "slowed", "nightcore", "slowed down", "reverb"],
        "regex": re.compile(r"\b(?:sped up|speed up|slowed(?:\s+down|\s*\+\s*reverb)?|nightcore)\b", re.IGNORECASE),
        "penalty": 65.0,
        "description": "Altered speed, Nightcore, or reverb remix",
    },
}

DEFAULT_WEIGHTS = {
    "artist_exact": 100.0,
    "artist_token": 90.0,
    "artist_featured": 60.0,
    "artist_partial": 20.0,
    "title_exact": 100.0,
    "title_clean_exact": 85.0,
    "title_tokens": 60.0,
    "title_partial": 30.0,
    "album_exact": 30.0,
    "album_partial": 15.0,
    "isrc_match": 1000.0,
    "duration_exact": 30.0,  # <= 2s diff
    "duration_close": 20.0,  # <= 5s diff
    "duration_ok": 10.0,     # <= 12s diff
    "clean_studio_bonus": 15.0,
}


def normalize_text(text: str) -> str:
    """Normalizes text by removing diacritics, lowering case, and stripping punctuation."""
    if not text:
        return ""
    # Normalize unicode (decompose accented chars like e -> e)
    norm = unicodedata.normalize("NFKD", str(text))
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = norm.lower()
    # Replace non-alphanumeric chars with spaces
    norm = re.sub(r"[^a-z0-9]+", " ", norm)
    # Collapse whitespace
    return re.sub(r"\s+", " ", norm).strip()


def strip_parentheses_and_brackets(text: str) -> str:
    """Strips all parenthetical and bracketed clauses from a title."""
    if not text:
        return ""
    cleaned = re.sub(r"\([^)]*\)", "", text)
    cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_isrc(text: str) -> bool:
    """Returns True if text is a valid 12-character ISRC code."""
    if not text:
        return False
    clean = re.sub(r"[- ]", "", text.strip())
    return bool(re.match(r"^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$", clean, re.IGNORECASE))


def extract_isrc(text: str) -> Optional[str]:
    """Extracts a normalized 12-character ISRC from free text if present."""
    if not text:
        return None
    match = ISRC_REGEX.search(text)
    if match:
        return "".join(match.groups()).upper()
    clean = re.sub(r"[- ]", "", text.strip())
    if is_isrc(clean):
        return clean.upper()
    return None


def extract_duration(text: str) -> Optional[int]:
    """Extracts target duration in seconds from query strings (e.g. '3:45', '225s')."""
    if not text:
        return None
    # Pattern: '3:45' or '03:45'
    m_time = re.search(r"(?:^|\s)(?:duration[:=]\s*)?(\d{1,2}):(\d{2})(?:\s|$)", text, re.IGNORECASE)
    if m_time:
        mins, secs = int(m_time.group(1)), int(m_time.group(2))
        return mins * 60 + secs

    # Pattern: '225s' or '225 sec' or '225 seconds'
    m_sec = re.search(r"(?:^|\s)(\d{2,4})\s*(?:s|sec|seconds)(?:\s|$)", text, re.IGNORECASE)
    if m_sec:
        return int(m_sec.group(1))

    return None


def parse_query(query: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parses a query string or target dictionary into structured search criteria.
    Extracts explicit fields, ISRC hints, duration hints, and detected query terms.
    """
    if isinstance(query, dict):
        artist = str(query.get("artist") or "").strip()
        title = str(query.get("title") or "").strip()
        album = str(query.get("album") or "").strip()
        isrc_val = extract_isrc(str(query.get("isrc") or ""))
        dur_val = query.get("duration") or query.get("duration_sec")
        try:
            target_dur = int(dur_val) if dur_val is not None else None
        except (ValueError, TypeError):
            target_dur = None

        raw_q = str(query.get("query") or f"{artist} {title}").strip()
        return {
            "artist": artist,
            "title": title,
            "album": album,
            "isrc": isrc_val,
            "duration": target_dur,
            "raw_query": raw_q,
            "norm_query": normalize_text(raw_q),
            "is_structured": True,
        }

    # Free text query
    raw_query = str(query).strip()
    norm_query = normalize_text(raw_query)

    isrc_found = extract_isrc(raw_query)
    duration_found = extract_duration(raw_query)

    cleaned_text = raw_query
    if isrc_found:
        cleaned_text = re.sub(ISRC_REGEX, "", cleaned_text).strip()
    if duration_found:
        cleaned_text = re.sub(r"(?:duration[:=]\s*)?\d{1,2}:\d{2}", "", cleaned_text).strip()
        cleaned_text = re.sub(r"\d{2,4}\s*(?:s|sec|seconds)", "", cleaned_text).strip()

    artist_candidate = ""
    title_candidate = ""

    # Common 'Artist - Title' separator
    if " - " in cleaned_text:
        parts = cleaned_text.split(" - ", 1)
        artist_candidate = parts[0].strip()
        title_candidate = parts[1].strip()

    return {
        "artist": artist_candidate,
        "title": title_candidate,
        "album": "",
        "isrc": isrc_found,
        "duration": duration_found,
        "raw_query": raw_query,
        "norm_query": norm_query,
        "is_structured": False,
    }


def query_contains_tag_category(norm_query: str, category_name: str) -> bool:
    """Checks whether the user query explicitly contains keywords from an unwanted category."""
    if not norm_query:
        return False
    spec = UNWANTED_TAG_SPECS.get(category_name)
    if not spec:
        return False
    # Check if any keyword appears in normalized query
    for kw in spec["keywords"]:
        norm_kw = normalize_text(kw)
        if norm_kw and f" {norm_kw} " in f" {norm_query} ":
            return True
        if norm_kw == norm_query:
            return True
    return False


def detect_unwanted_tags(track: Dict[str, Any], norm_query: str = "") -> List[Dict[str, Any]]:
    """
    Scans track metadata (Title, Version, Album, Artist) for tags like (Remix), (Live),
    (Cover), [Edit], etc. Returns only tags whose terms were NOT requested in the query.
    """
    raw_title = str(track.get("title", ""))
    title_version = str(track.get("title_version", ""))
    raw_album = str(track.get("album", ""))
    raw_artist = str(track.get("artist", ""))

    inspected_text = f"{raw_title} {title_version} {raw_album} {raw_artist}"
    norm_inspected = normalize_text(inspected_text)

    penalties = []

    for cat_name, spec in UNWANTED_TAG_SPECS.items():
        # If user explicitly requested this term in query, DO NOT penalize
        if query_contains_tag_category(norm_query, cat_name):
            continue

        matched = False
        matched_term = ""

        # Check regex against raw title/version/album/artist
        m = spec["regex"].search(raw_title) or spec["regex"].search(title_version)
        if m:
            matched = True
            matched_term = m.group(0)
        else:
            # Check album for live/tribute/cover
            if cat_name in ("live", "cover"):
                m_alb = spec["regex"].search(raw_album)
                if m_alb:
                    matched = True
                    matched_term = f"Album: {m_alb.group(0)}"

            # Check artist for cover/tribute/karaoke
            if cat_name == "cover":
                m_art = spec["regex"].search(raw_artist)
                if m_art:
                    matched = True
                    matched_term = f"Artist: {m_art.group(0)}"

            # Also check normalized inspection
            if not matched:
                for kw in spec["keywords"]:
                    n_kw = normalize_text(kw)
                    if n_kw and f" {n_kw} " in f" {norm_inspected} ":
                        matched = True
                        matched_term = kw
                        break

        if matched:
            penalties.append({
                "category": cat_name,
                "term": matched_term,
                "penalty": spec["penalty"],
                "description": spec["description"],
            })

    return penalties


def compute_artist_score(
    norm_track_artist: str,
    norm_query_artist: str,
    norm_query: str,
    weights: Dict[str, float]
) -> Tuple[float, str]:
    """
    Scores artist match with overwhelming priority given to exact artist matches.
    """
    if not norm_track_artist:
        return 0.0, "missing_artist"

    # Strip leading 'the ' for relaxed comparison while retaining distinction
    def strip_the(s: str) -> str:
        return re.sub(r"^the\s+", "", s).strip()

    ta_nothe = strip_the(norm_track_artist)

    # 1. Exact match against target artist (if provided) or entire query
    if norm_query_artist:
        qa_nothe = strip_the(norm_query_artist)
        if norm_track_artist == norm_query_artist:
            return weights["artist_exact"], "exact_target_artist"
        if ta_nothe == qa_nothe and ta_nothe:
            return weights["artist_exact"] * 0.98, "exact_target_artist_no_the"

    if norm_query:
        q_nothe = strip_the(norm_query)
        if norm_track_artist == norm_query:
            return weights["artist_exact"], "exact_query_is_artist"
        if ta_nothe == q_nothe and ta_nothe:
            return weights["artist_exact"] * 0.98, "exact_query_is_artist_no_the"

    # 2. Exact artist token sequence in query (e.g. query: 'daft punk one more time')
    # Track artist 'daft punk' is an exact discrete phrase in the query
    if norm_track_artist in norm_query:
        pattern = r"(?:^|\s)" + re.escape(norm_track_artist) + r"(?:\s|$)"
        if re.search(pattern, norm_query):
            # Track artist is an exact whole-word phrase in the query
            return weights["artist_token"], "exact_artist_token_in_query"

    # Check without 'the'
    if ta_nothe and ta_nothe in norm_query:
        pattern = r"(?:^|\s)" + re.escape(ta_nothe) + r"(?:\s|$)"
        if re.search(pattern, norm_query):
            return weights["artist_token"] * 0.95, "exact_artist_token_in_query_no_the"

    # 3. Collaboration / Featured match (e.g. 'Daft Punk feat. Pharrell Williams')
    collab_markers = [" feat ", " ft ", " featuring ", " with ", " vs "]
    for marker in collab_markers:
        if marker in f" {norm_track_artist} ":
            lead_artist = norm_track_artist.split(marker.strip())[0].strip()
            if lead_artist and (lead_artist == norm_query_artist or lead_artist in norm_query):
                return weights["artist_featured"], f"lead_artist_in_collab ({lead_artist})"

    # 4. Partial / Word Overlap match (e.g. 'Queen Tribute Band' vs 'Queen')
    track_words = set(norm_track_artist.split())
    query_words = set(norm_query.split())
    overlap = track_words.intersection(query_words)
    if overlap:
        # Heavily discounted: partial word match cannot compete with exact artist
        overlap_ratio = len(overlap) / max(len(track_words), 1)
        return weights["artist_partial"] * overlap_ratio, f"partial_artist_overlap ({overlap_ratio:.2f})"

    return 0.0, "no_artist_match"


def compute_title_score(
    raw_track_title: str,
    norm_query_title: str,
    norm_query: str,
    norm_track_artist: str,
    weights: Dict[str, float]
) -> Tuple[float, str]:
    """Scores title match, rewarding clean exact titles and penalizing mismatches."""
    if not raw_track_title:
        return 0.0, "missing_title"

    norm_track_title = normalize_text(raw_track_title)
    clean_title = strip_parentheses_and_brackets(raw_track_title)
    norm_clean_title = normalize_text(clean_title)

    # Calculate residual query by removing known artist phrase from query if present
    residual_query = norm_query
    if norm_track_artist and norm_track_artist in norm_query:
        # Strip exact artist phrase
        pattern = r"(?:^|\s)" + re.escape(norm_track_artist) + r"(?:\s|$)"
        residual_query = re.sub(pattern, " ", norm_query)
        residual_query = re.sub(r"\s+", " ", residual_query).strip()

    # 1. Exact match against explicit query title or full query
    if norm_query_title:
        if norm_track_title == norm_query_title:
            return weights["title_exact"], "exact_target_title"
        if norm_clean_title == norm_query_title:
            return weights["title_clean_exact"], "exact_clean_target_title"

    if norm_query:
        if norm_track_title == norm_query:
            return weights["title_exact"], "exact_query_is_title"
        if norm_clean_title == norm_query:
            return weights["title_clean_exact"], "exact_clean_query_is_title"

    # 2. Match against residual query (the portion of query corresponding to track title)
    if residual_query:
        if norm_track_title == residual_query:
            return weights["title_exact"], "exact_full_title_matches_residual_query"
        if norm_clean_title == residual_query:
            return weights["title_clean_exact"], "exact_clean_title_matches_residual_query"

    # 3. Check full raw title in query (e.g. 'one more time club mix' in 'daft punk one more time club mix')
    if norm_track_title and norm_track_title in norm_query:
        pattern = r"(?:^|\s)" + re.escape(norm_track_title) + r"(?:\s|$)"
        if re.search(pattern, norm_query):
            # Check if this title left unconsumed extra words in residual_query
            if residual_query:
                res_words = set(residual_query.split())
                title_words = set(norm_track_title.split())
                if res_words == title_words:
                    return weights["title_exact"], "exact_full_title_in_query"
                coverage = len(title_words.intersection(res_words)) / max(len(res_words), 1)
                score = weights["title_partial"] + (weights["title_clean_exact"] - weights["title_partial"]) * coverage
                return score, f"full_title_in_query_partial_residual ({coverage:.2f})"
            return weights["title_exact"], "exact_full_title_in_query"

    # 4. Clean title is an exact discrete phrase in the query
    if norm_clean_title and norm_clean_title in norm_query:
        pattern = r"(?:^|\s)" + re.escape(norm_clean_title) + r"(?:\s|$)"
        if re.search(pattern, norm_query):
            if residual_query:
                res_words = set(residual_query.split())
                c_words = set(norm_clean_title.split())
                coverage = len(c_words.intersection(res_words)) / max(len(res_words), 1)
                score = weights["title_partial"] + (weights["title_clean_exact"] - weights["title_partial"]) * coverage
                return score, f"clean_title_in_query_partial_residual ({coverage:.2f})"
            return weights["title_clean_exact"], "exact_clean_title_in_query"

    # 5. Word token overlap
    title_words = set(norm_clean_title.split())
    query_words = set(norm_query.split())
    if title_words and query_words:
        overlap = title_words.intersection(query_words)
        if overlap == title_words:
            # All words of the clean title are in query
            return weights["title_tokens"], "all_title_words_in_query"
        elif overlap:
            ratio = len(overlap) / len(title_words)
            return weights["title_partial"] * ratio, f"partial_title_overlap ({ratio:.2f})"

    return 0.0, "no_title_match"


def compute_album_score(
    norm_track_album: str,
    norm_query_album: str,
    norm_query: str,
    weights: Dict[str, float]
) -> Tuple[float, str]:
    """Scores album match if query or target specifies album information."""
    if not norm_track_album:
        return 0.0, "no_album_data"

    if norm_query_album:
        if norm_track_album == norm_query_album:
            return weights["album_exact"], "exact_album_match"
        if norm_query_album in norm_track_album:
            return weights["album_partial"], "partial_album_match"

    if norm_query and norm_track_album in norm_query:
        pattern = r"(?:^|\s)" + re.escape(norm_track_album) + r"(?:\s|$)"
        if re.search(pattern, norm_query):
            return weights["album_exact"], "album_in_query"

    return 0.0, "no_album_match"


def compute_isrc_score(
    track_isrc: str,
    target_isrc: Optional[str],
    weights: Dict[str, float]
) -> Tuple[float, str]:
    """Scores ISRC match with absolute priority for positive matches."""
    if not track_isrc or not target_isrc:
        return 0.0, "no_isrc_comparison"

    clean_track = re.sub(r"[- ]", "", str(track_isrc)).upper()
    clean_target = re.sub(r"[- ]", "", str(target_isrc)).upper()

    if clean_track == clean_target and len(clean_track) == 12:
        return weights["isrc_match"], f"exact_isrc_match ({clean_track})"

    return 0.0, "isrc_mismatch"


def compute_duration_score(
    track_dur_sec: Optional[int],
    target_dur_sec: Optional[int],
    weights: Dict[str, float]
) -> Tuple[float, str]:
    """
    Scores duration match against target duration (if present) or performs sanity checks.
    """
    if track_dur_sec is None or track_dur_sec <= 0:
        return 0.0, "no_track_duration"

    if target_dur_sec is not None and target_dur_sec > 0:
        diff = abs(track_dur_sec - target_dur_sec)
        if diff <= 2:
            return weights["duration_exact"], f"duration_exact_diff_{diff}s"
        elif diff <= 5:
            return weights["duration_close"], f"duration_close_diff_{diff}s"
        elif diff <= 12:
            return weights["duration_ok"], f"duration_ok_diff_{diff}s"
        elif diff > 60:
            # Large duration mismatch penalty (e.g. 3m original vs 8m live/remix)
            return -25.0, f"duration_mismatch_diff_{diff}s"
        elif diff > 30:
            return -10.0, f"duration_minor_mismatch_diff_{diff}s"
        return 0.0, f"duration_neutral_diff_{diff}s"

    # Sanity checks when no target duration specified
    if track_dur_sec < 45:
        # Ringtone, preview snippet, intro, soundbite
        return -30.0, "too_short_under_45s"
    if track_dur_sec > 900:
        # DJ set, full album stream, or mega-mix
        return -15.0, "too_long_over_15m"

    return 0.0, "duration_standard_studio_range"


def score_track_detailed(
    query_or_target: Union[str, Dict[str, Any]],
    track: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Evaluates track metadata against the query and returns a comprehensive score breakdown.
    """
    w = DEFAULT_WEIGHTS.copy()
    if weights:
        w.update(weights)

    pq = parse_query(query_or_target)
    norm_query = pq["norm_query"]

    # Normalize track metadata
    raw_artist = str(track.get("artist") or track.get("album_artist") or "")
    norm_track_artist = normalize_text(raw_artist)

    raw_title = str(track.get("title") or "")
    norm_track_title = normalize_text(raw_title)

    raw_album = str(track.get("album") or "")
    norm_track_album = normalize_text(raw_album)

    track_isrc = track.get("isrc") or ""

    track_dur = track.get("duration_sec") or track.get("duration")
    try:
        track_dur_sec = int(track_dur) if track_dur is not None else None
    except (ValueError, TypeError):
        track_dur_sec = None

    reasons = []

    # 1. ISRC comparison
    isrc_score, isrc_reason = compute_isrc_score(track_isrc, pq["isrc"], w)
    if isrc_score > 0:
        reasons.append(isrc_reason)

    # 2. Artist score (Requirement 3: prioritize exact artist over partial)
    artist_score, artist_reason = compute_artist_score(
        norm_track_artist,
        normalize_text(pq["artist"]),
        norm_query,
        w
    )
    reasons.append(artist_reason)

    # 3. Title score
    title_score, title_reason = compute_title_score(
        raw_title,
        normalize_text(pq["title"]),
        norm_query,
        norm_track_artist,
        w
    )
    reasons.append(title_reason)

    # 4. Album score
    album_score, album_reason = compute_album_score(
        norm_track_album,
        normalize_text(pq["album"]),
        norm_query,
        w
    )
    if album_score > 0:
        reasons.append(album_reason)

    # 5. Duration score
    dur_score, dur_reason = compute_duration_score(track_dur_sec, pq["duration"], w)
    if dur_score != 0.0:
        reasons.append(dur_reason)

    # 6. Negative penalties for (Remix), (Live), (Cover), [Edit] (Requirement 2)
    unwanted_tags = detect_unwanted_tags(track, norm_query)
    total_penalty = 0.0
    penalties_applied = []
    for tag in unwanted_tags:
        pen = tag["penalty"]
        total_penalty += pen
        penalties_applied.append(f"{tag['category']}:{tag['term']} (-{pen:.0f} pts)")
        reasons.append(f"penalty_{tag['category']} ({tag['term']})")

    # 7. Clean Studio Cut Bonus
    # If the track has no brackets/parentheses and no unwanted tags, reward original cut,
    # provided the user did not explicitly query for a remix/live/edit/etc. version.
    studio_bonus = 0.0
    user_requested_modifier = any(query_contains_tag_category(norm_query, c) for c in UNWANTED_TAG_SPECS)
    if not user_requested_modifier and not unwanted_tags and "(" not in raw_title and "[" not in raw_title and "-" not in raw_title:
        studio_bonus = w["clean_studio_bonus"]
        reasons.append("clean_studio_title_bonus")

    # Final tally
    total_score = (
        isrc_score
        + artist_score
        + title_score
        + album_score
        + dur_score
        + studio_bonus
        - total_penalty
    )

    return {
        "total_score": round(total_score, 2),
        "artist_score": round(artist_score, 2),
        "title_score": round(title_score, 2),
        "album_score": round(album_score, 2),
        "isrc_score": round(isrc_score, 2),
        "duration_score": round(dur_score, 2),
        "studio_bonus": round(studio_bonus, 2),
        "penalty": round(total_penalty, 2),
        "penalties_applied": penalties_applied,
        "is_unwanted": len(unwanted_tags) > 0,
        "reasons": reasons,
    }


def score_track(
    query_or_target: Union[str, Dict[str, Any]],
    track: Dict[str, Any],
    weights: Optional[Dict[str, float]] = None
) -> float:
    """Computes and returns the overall numerical ranking score for a track."""
    breakdown = score_track_detailed(query_or_target, track, weights=weights)
    return breakdown["total_score"]


def rank_tracks(
    query_or_target: Union[str, Dict[str, Any]],
    tracks: List[Dict[str, Any]],
    filter_unwanted: bool = False,
    weights: Optional[Dict[str, float]] = None
) -> List[Dict[str, Any]]:
    """
    Ranks a list of track metadata dictionaries against query/target criteria.

    - Sorts descending by match score.
    - Annotates each track with 'match_score' and 'score_breakdown'.
    - If filter_unwanted is True, filters out tracks with unwanted penalties,
      unless doing so would return an empty list (safe fallback).
    """
    if not tracks:
        return []

    scored_list = []
    for t in tracks:
        item = dict(t)
        details = score_track_detailed(query_or_target, item, weights=weights)
        item["match_score"] = details["total_score"]
        item["score_breakdown"] = details
        scored_list.append(item)

    # Sort primarily by match_score descending
    scored_list.sort(key=lambda x: x["match_score"], reverse=True)

    if filter_unwanted:
        clean_tracks = [t for t in scored_list if not t["score_breakdown"]["is_unwanted"]]
        # Only apply hard filter if at least one clean track exists
        if clean_tracks:
            return clean_tracks

    return scored_list
