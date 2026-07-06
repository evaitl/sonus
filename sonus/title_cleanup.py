from __future__ import annotations

import re

_LEADING_TRACK_NUMBER = re.compile(r"^\d{1,3}(?:\s*[-_]\s*|\s+)(.+)$")


def clean_leading_track_number_title(title: str) -> str | None:
    """Remove a leading track number prefix from a title, if present."""
    text = title.strip()
    if not text:
        return None
    match = _LEADING_TRACK_NUMBER.match(text)
    if not match:
        return None
    cleaned = match.group(1).strip()
    if not cleaned or cleaned == text:
        return None
    return cleaned
