"""
Community Hi-Fi Lossless Resolver (Zero-Account Required).

Queries open community Hi-Fi gateways and public lossless archives (Bandcamp, Archive.org)
to resolve authentic 16-bit / 44.1 kHz FLAC audio streams without requiring personal
subscriptions, tokens, or credentials from the user.
"""

import os
import re
import tempfile
from typing import Any, Dict, Optional
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}


class CommunityHiFiResolver:
    """Zero-account Community Hi-Fi Stream & File Resolver."""

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout
        # Public community endpoints / mirrors that pool Hi-Fi tokens
        self.community_gateways = [
            "https://api.doubledouble.top",
            "https://api.deezload.com",
        ]

    def resolve_lossless_stream(self, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Attempts to resolve an authentic lossless FLAC stream or download link
        using track ISRC, artist, and title.

        Returns:
            Dict with keys: 'stream_url', 'format' ('flac'), 'is_true_lossless' (True)
            or None if no community gateway has the authentic FLAC available.
        """
        title = metadata.get("title", "").strip()
        artist = metadata.get("artist", "").strip()
        isrc = metadata.get("isrc", "").strip()
        external_url = metadata.get("external_url", "")

        # 1. Direct Bandcamp / Archive.org (Authentic native FLAC)
        if "bandcamp.com" in external_url or "archive.org" in external_url:
            return {
                "source": "Native Lossless Archive",
                "direct_url": external_url,
                "format": "flac",
                "is_true_lossless": True,
            }

        # 2. Try Community Hi-Fi Gateways if ISRC or title available
        # Note: We run with a fast timeout so that if public mirrors are experiencing
        # downtime or rate-limits, we seamlessly fall back without blocking the user.
        for gateway in self.community_gateways:
            try:
                # Query mirror with ISRC (most accurate) or Artist + Title
                params = {"isrc": isrc} if isrc else {"q": f"{artist} {title}"}
                resp = requests.get(f"{gateway}/resolve", params=params, headers=HEADERS, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    flac_url = data.get("flac_url") or data.get("download_url")
                    if flac_url and (data.get("bitrate") == 1411 or "flac" in str(data.get("format", "")).lower()):
                        return {
                            "source": f"Community Hi-Fi ({gateway})",
                            "stream_url": flac_url,
                            "format": "flac",
                            "is_true_lossless": True,
                        }
            except Exception:
                # Gateway offline, rate-limited, or blocked by Cloudflare; continue to next
                continue

        return None


# Global instance
hifi_resolver = CommunityHiFiResolver()
