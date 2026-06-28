from __future__ import annotations

import re
from pathlib import Path

_ARTIST_TITLE_SPACE = re.compile(
    r"^\d{1,3}\s+(.+?)\s+-\s+",
    re.IGNORECASE,
)

_ARTIST_SLUG_DASH = re.compile(
    r"^\d{1,3}-([a-z0-9][a-z0-9_]*?)-",
    re.IGNORECASE,
)

_SMALL_WORDS = frozenset(
    {"a", "an", "and", "at", "by", "for", "in", "of", "on", "or", "the", "to", "vs", "vs."}
)


def _humanize_slug(slug: str) -> str:
    words = slug.replace("_", " ").split()
    if not words:
        return ""
    parts: list[str] = []
    for index, word in enumerate(words):
        lower = word.lower()
        if re.fullmatch(r"\d+cc", lower):
            parts.append(lower)
            continue
        if index > 0 and lower in _SMALL_WORDS:
            parts.append(lower)
        else:
            parts.append(word.capitalize())
    return " ".join(parts)


def artist_from_filename(file_name: str) -> str | None:
    """Best-effort artist name parsed from common scene/release filename patterns."""
    stem = Path(file_name).stem

    match = _ARTIST_TITLE_SPACE.match(stem)
    if match:
        artist = match.group(1).strip()
        return artist or None

    match = _ARTIST_SLUG_DASH.match(stem)
    if match:
        artist = _humanize_slug(match.group(1))
        return artist or None

    return None


def coalesce_artist(*, tag_artist: str | None, file_name: str) -> str | None:
    """Prefer embedded tag artist; fall back to filename parsing."""
    if tag_artist and tag_artist.strip():
        return tag_artist.strip()
    return artist_from_filename(file_name)
