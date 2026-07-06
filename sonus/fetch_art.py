from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ART_DIR = PROJECT_ROOT / "data" / "art"

USER_AGENT = "Sonus/0.1.0 (personal music library; https://github.com/evaitl/sonus)"
MIN_COVER_BYTES = 500
MIN_COVER_WIDTH = 100
MIN_COVER_HEIGHT = 100
REQUEST_TIMEOUT = 30
MUSICBRAINZ_DELAY = 1.0

_last_musicbrainz_request = 0.0


class FetchArtError(Exception):
    pass


@dataclass
class FetchArtResult:
    art_path: str
    source: str
    updated_track_ids: list[int]
    art_paths: dict[int, str]


def _http_get(url: str, *, accept: str = "*/*") -> bytes:
    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read()


def _musicbrainz_get(path: str) -> dict:
    global _last_musicbrainz_request
    elapsed = time.monotonic() - _last_musicbrainz_request
    if elapsed < MUSICBRAINZ_DELAY:
        time.sleep(MUSICBRAINZ_DELAY - elapsed)
    _last_musicbrainz_request = time.monotonic()

    url = f"https://musicbrainz.org/ws/2/{path}"
    data = _http_get(url, accept="application/json")
    return json.loads(data.decode("utf-8"))


def _escape_lucene(value: str) -> str:
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/])', r"\\\1", value.strip())


def _search_release_mbid(
    *,
    artist: str | None,
    album: str | None,
    title: str | None,
) -> str | None:
    clauses: list[str] = []
    if album:
        clauses.append(f'release:"{_escape_lucene(album)}"')
    if artist:
        clauses.append(f'artist:"{_escape_lucene(artist)}"')
    if not clauses and title:
        clauses.append(f'release:"{_escape_lucene(title)}"')
    if not clauses:
        return None

    query = quote(" AND ".join(clauses))
    payload = _musicbrainz_get(f"release?query={query}&fmt=json&limit=5")
    releases = payload.get("releases") or []
    if not releases:
        return None
    return releases[0].get("id")


def _search_recording_release_mbid(
    *,
    artist: str | None,
    title: str | None,
) -> str | None:
    if not title:
        return None
    clauses = [f'recording:"{_escape_lucene(title)}"']
    if artist:
        clauses.append(f'artist:"{_escape_lucene(artist)}"')
    query = quote(" AND ".join(clauses))
    payload = _musicbrainz_get(f"recording?query={query}&fmt=json&limit=3")
    recordings = payload.get("recordings") or []
    for recording in recordings:
        releases = recording.get("releases") or []
        if releases:
            return releases[0].get("id")
    return None


def _download_cover_art_archive(release_mbid: str) -> bytes | None:
    url = f"https://coverartarchive.org/release/{release_mbid}/front"
    try:
        data = _http_get(url, accept="image/*")
    except HTTPError as exc:
        if exc.code in (404, 307):
            return None
        return None
    except URLError:
        return None
    if not _is_usable_cover(data):
        return None
    return data


def _itunes_cover_url(
    *,
    artist: str | None,
    album: str | None,
    title: str | None,
) -> str | None:
    term_parts = [part for part in (artist, album or title) if part and part.strip()]
    if not term_parts:
        return None
    term = quote(" ".join(term_parts))
    url = f"https://itunes.apple.com/search?term={term}&entity=song&limit=1"
    try:
        data = _http_get(url, accept="application/json")
    except (HTTPError, URLError):
        return None
    payload = json.loads(data.decode("utf-8"))
    results = payload.get("results") or []
    if not results:
        return None
    artwork = results[0].get("artworkUrl100")
    if not artwork:
        return None
    return artwork.replace("100x100bb", "600x600bb")


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    index = 2
    while index < len(data) - 8:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker in (
            0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
        ):
            height = int.from_bytes(data[index + 5 : index + 7], "big")
            width = int.from_bytes(data[index + 7 : index + 9], "big")
            return width, height
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        segment_length = int.from_bytes(data[index + 2 : index + 4], "big")
        index += 2 + segment_length
    return None


def _image_dimensions(data: bytes) -> tuple[int, int] | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        return width, height
    if data.startswith(b"\xff\xd8"):
        return _jpeg_dimensions(data)
    return None


def _is_usable_cover(data: bytes) -> bool:
    if len(data) < MIN_COVER_BYTES:
        return False
    dimensions = _image_dimensions(data)
    if dimensions is None:
        return False
    width, height = dimensions
    return width >= MIN_COVER_WIDTH and height >= MIN_COVER_HEIGHT


def _cover_extension(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"GIF"):
        return ".gif"
    return ".jpg"


def _resolve_art_root(art_dir: Path | None) -> Path:
    if art_dir is not None:
        root = Path(art_dir).expanduser()
        if not root.is_absolute():
            root = PROJECT_ROOT / root
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    env = os.environ.get("SONUS_ART_DIR")
    if env:
        root = Path(env).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root
    DEFAULT_ART_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_ART_DIR


def _save_cover(
    cover_bytes: bytes,
    *,
    track_id: int,
    art_dir: Path | None,
) -> Path:
    art_root = _resolve_art_root(art_dir)
    track_dir = art_root / str(track_id)
    track_dir.mkdir(parents=True, exist_ok=True)
    for existing in track_dir.glob("cover.*"):
        existing.unlink()
    dest = track_dir / f"cover{_cover_extension(cover_bytes)}"
    dest.write_bytes(cover_bytes)
    return dest


def fetch_album_art_online(
    *,
    artist: str | None,
    album: str | None,
    title: str | None,
) -> tuple[bytes, str] | None:
    """Return cover image bytes and source label."""
    artist_s = (artist or "").strip() or None
    album_s = (album or "").strip() or None
    title_s = (title or "").strip() or None

    if not any((artist_s, album_s, title_s)):
        return None

    release_mbid = _search_release_mbid(
        artist=artist_s, album=album_s, title=title_s
    )
    if release_mbid is None:
        release_mbid = _search_recording_release_mbid(
            artist=artist_s, title=title_s
        )

    if release_mbid:
        cover = _download_cover_art_archive(release_mbid)
        if cover:
            return cover, "Cover Art Archive"

    itunes_url = _itunes_cover_url(
        artist=artist_s, album=album_s, title=title_s
    )
    if itunes_url:
        try:
            cover = _http_get(itunes_url, accept="image/*")
        except (HTTPError, URLError):
            cover = None
        if cover and _is_usable_cover(cover):
            return cover, "iTunes"

    return None


def apply_cover_bytes_to_tracks(
    cover_bytes: bytes,
    track_ids: list[int],
    *,
    art_dir: Path | None = None,
) -> dict[int, str]:
    """Write the same cover image for each track id. Returns id → art_path."""
    paths: dict[int, str] = {}
    for track_id in track_ids:
        dest = _save_cover(cover_bytes, track_id=track_id, art_dir=art_dir)
        paths[track_id] = str(dest.relative_to(PROJECT_ROOT))
    return paths


def enrich_track_art(
    *,
    track_id: int,
    artist: str | None,
    album: str | None,
    title: str | None,
    art_dir: Path | None = None,
    track_ids: list[int] | None = None,
) -> FetchArtResult:
    """Fetch album art online and save it for one or more tracks."""
    targets = list(dict.fromkeys(track_ids if track_ids else [track_id]))
    if track_id not in targets:
        targets.insert(0, track_id)

    result = fetch_album_art_online(
        artist=artist,
        album=album,
        title=title,
    )
    if result is None:
        raise FetchArtError(
            "No album art found online. Try adding artist and album metadata."
        )
    cover_bytes, source = result
    paths = apply_cover_bytes_to_tracks(
        cover_bytes, targets, art_dir=art_dir
    )
    return FetchArtResult(
        art_path=paths[track_id],
        source=source,
        updated_track_ids=targets,
        art_paths=paths,
    )
