"""
youtube_summary_tool – get a transcript and summarize a YouTube video.

Uses youtube-transcript-api (no API key). Chunks the transcript and
returns key content. Handles videos without transcripts gracefully.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from cachetools import TTLCache

from src.tools._base import BaseTool, truncate

logger = logging.getLogger(__name__)

_CACHE: TTLCache = TTLCache(maxsize=64, ttl=300)
_MAX_TRANSCRIPT_CHARS = 6000
_MODEL_MAX = 800


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    # Try query param
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "v" in qs:
        return qs["v"][0]
    return None


class YouTubeSummaryTool(BaseTool):
    """Retrieve and summarize the transcript of a YouTube video by URL. Returns key content chunks; gracefully handles videos without available transcripts."""

    name = "youtube_summary"
    description = (
        "Get a summary of a YouTube video's transcript from its URL. "
        "Use when the user shares a YouTube link and wants to know what the video is about."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The YouTube video URL (e.g. https://youtube.com/watch?v=...).",
            }
        },
        "required": ["url"],
    }
    category = "web"

    def run(self, url: str, **_: Any) -> str:  # type: ignore[override]
        """Fetch YouTube transcript for *url* and return condensed content."""
        url = url.strip()
        video_id = _extract_video_id(url)
        if not video_id:
            return f"[Error] Could not extract a YouTube video ID from: {url}"

        if video_id in _CACHE:
            return _CACHE[video_id]

        try:
            from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled  # noqa: PLC0415
        except ImportError:
            return "[Error] youtube-transcript-api is not installed. Run: pip install youtube-transcript-api"

        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        except TranscriptsDisabled:
            result = f"[No transcript] Video {video_id} has transcripts disabled."
            _CACHE[video_id] = result
            return result
        except NoTranscriptFound:
            # Try fetching any available language
            try:
                tl = YouTubeTranscriptApi.list_transcripts(video_id)
                transcript_list = next(iter(tl)).fetch()
            except Exception:
                result = f"[No transcript] No transcript is available for video {video_id}."
                _CACHE[video_id] = result
                return result
        except Exception as exc:
            return f"[Error] Could not fetch transcript: {exc}"

        # Combine transcript text
        full_text = " ".join(item.get("text", "") for item in transcript_list)
        full_text = full_text[:_MAX_TRANSCRIPT_CHARS]

        # Return first chunk (model gets ~800 chars; full text kept server-side)
        result = f"YouTube Video ID: {video_id}\nTranscript excerpt:\n" + truncate(full_text, _MODEL_MAX)
        _CACHE[video_id] = result
        return result
