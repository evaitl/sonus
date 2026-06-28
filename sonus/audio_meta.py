from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.flac import Picture


class AudioMetaError(Exception):
    pass


@dataclass
class AudioMetadata:
    format: str | None = None
    title: str | None = None
    sort_title: str | None = None
    artist: str | None = None
    album: str | None = None
    album_artist: str | None = None
    track_number: int | None = None
    disc_number: int | None = None
    year: str | None = None
    genre: str | None = None
    duration_seconds: float | None = None
    errors: list[str] = field(default_factory=list)


def _first_text(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        return _first_text(value[0])
    text = str(value).strip()
    return text or None


def _parse_int(value: object | None) -> int | None:
    text = _first_text(value)
    if not text:
        return None
    if "/" in text:
        text = text.split("/", 1)[0]
    try:
        return int(text)
    except ValueError:
        return None


def read_metadata(file_path: Path) -> AudioMetadata:
    meta = AudioMetadata(format=file_path.suffix.lower().lstrip("."))
    try:
        audio = MutagenFile(file_path, easy=True)
    except Exception as exc:
        raise AudioMetaError(str(exc)) from exc

    if audio is None:
        meta.errors.append("unsupported or unreadable audio file")
        return meta

    tags = audio.tags or {}

    meta.title = _first_text(tags.get("title"))
    meta.sort_title = _first_text(tags.get("titlesort"))
    meta.artist = _first_text(tags.get("artist"))
    meta.album = _first_text(tags.get("album"))
    meta.album_artist = _first_text(tags.get("albumartist"))
    meta.track_number = _parse_int(tags.get("tracknumber"))
    meta.disc_number = _parse_int(tags.get("discnumber"))
    meta.genre = _first_text(tags.get("genre"))
    meta.year = _first_text(tags.get("date") or tags.get("year"))

    if audio.info and getattr(audio.info, "length", None):
        meta.duration_seconds = float(audio.info.length)

    return meta


def extract_art(file_path: Path, dest_dir: Path) -> Path | None:
    """Extract embedded album art to dest_dir; returns the saved file path."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        audio = MutagenFile(file_path)
    except Exception:
        return None

    if audio is None:
        return None

    picture_data: bytes | None = None
    mime: str | None = None

    if hasattr(audio, "pictures") and audio.pictures:
        pic: Picture = audio.pictures[0]
        picture_data = pic.data
        mime = pic.mime
    elif audio.tags:
        for key in ("APIC:", "APIC"):
            frame = audio.tags.get(key)
            if frame is not None:
                picture_data = getattr(frame, "data", None)
                mime = getattr(frame, "mime", None)
                break

    if not picture_data:
        return None

    ext = ".jpg"
    if mime:
        if "png" in mime.lower():
            ext = ".png"
        elif "gif" in mime.lower():
            ext = ".gif"
        elif "webp" in mime.lower():
            ext = ".webp"

    dest = dest_dir / f"cover{ext}"
    dest.write_bytes(picture_data)
    return dest
