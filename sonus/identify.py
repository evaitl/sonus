from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sonus.fetch_art import USER_AGENT

ACOUSTID_URL = "https://api.acoustid.org/v2/lookup"
MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording/"
REQUEST_TIMEOUT = 30


class IdentifyTrackError(Exception):
    pass


@dataclass(frozen=True)
class IdentifiedMetadata:
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    genre: str | None = None


def _http_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _run_fpcalc(file_path: Path) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["fpcalc", "-json", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise IdentifyTrackError(
            "Track identification requires fpcalc (Chromaprint) to be installed."
        ) from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip() or "fpcalc failed"
        raise IdentifyTrackError(message)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise IdentifyTrackError("fpcalc returned invalid JSON output.") from exc
    duration = int(payload.get("duration") or 0)
    fingerprint = str(payload.get("fingerprint") or "")
    if duration <= 0 or not fingerprint:
        raise IdentifyTrackError("fpcalc did not return a usable fingerprint.")
    return duration, fingerprint


def _lookup_acoustid(client_key: str, duration: int, fingerprint: str) -> dict:
    params = urlencode(
        {
            "client": client_key,
            "duration": str(duration),
            "fingerprint": fingerprint,
            "meta": "recordings+releasegroups+releases+compress",
            "format": "json",
        }
    )
    payload = _http_json(f"{ACOUSTID_URL}?{params}")
    if payload.get("status") != "ok":
        error = str(payload.get("error", {}).get("message") or "AcoustID lookup failed.")
        raise IdentifyTrackError(error)
    return payload


def _pick_best_recording(payload: dict) -> tuple[dict, str | None]:
    best_recording: dict | None = None
    best_recording_id: str | None = None
    best_score = -1.0
    for result in payload.get("results") or []:
        score = float(result.get("score") or 0.0)
        for recording in result.get("recordings") or []:
            if score > best_score:
                best_score = score
                best_recording = recording
                best_recording_id = str(recording.get("id") or "") or None
    if best_recording is None:
        raise IdentifyTrackError("AcoustID could not identify this track.")
    return best_recording, best_recording_id


def _join_artists(recording: dict) -> str | None:
    artists = recording.get("artists") or []
    if not artists:
        return None
    return "".join(
        f"{artist.get('name', '')}{artist.get('joinphrase', '')}" for artist in artists
    ).strip() or None


def _recording_album(recording: dict) -> str | None:
    releasegroups = recording.get("releasegroups") or []
    if releasegroups:
        title = str(releasegroups[0].get("title") or "").strip()
        if title:
            return title
    releases = recording.get("releases") or []
    if releases:
        title = str(releases[0].get("title") or "").strip()
        if title:
            return title
    return None


def _musicbrainz_genre(recording_id: str) -> str | None:
    payload = _http_json(f"{MUSICBRAINZ_URL}{recording_id}?inc=genres&fmt=json")
    genres = payload.get("genres") or []
    if genres:
        name = str(genres[0].get("name") or "").strip()
        if name:
            return name.title()
    tags = payload.get("tags") or []
    if tags:
        name = str(tags[0].get("name") or "").strip()
        if name:
            return name.title()
    return None


def identify_track(file_path: str | Path, *, client_key: str) -> IdentifiedMetadata:
    cleaned_client = client_key.strip()
    if not cleaned_client:
        raise IdentifyTrackError(
            "Track identification requires an AcoustID client key."
        )
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise IdentifyTrackError(f"Track file not found: {path}")
    duration, fingerprint = _run_fpcalc(path)
    payload = _lookup_acoustid(cleaned_client, duration, fingerprint)
    recording, recording_id = _pick_best_recording(payload)
    title = str(recording.get("title") or "").strip() or None
    artist = _join_artists(recording)
    album = _recording_album(recording)
    genre = _musicbrainz_genre(recording_id) if recording_id else None
    return IdentifiedMetadata(
        title=title,
        artist=artist,
        album=album,
        genre=genre,
    )


def metadata_updates_from_identification(
    *,
    current_title: str | None,
    current_artist: str | None,
    current_album: str | None,
    current_genre: str | None,
    identified: IdentifiedMetadata,
) -> dict[str, str | None]:
    updates: dict[str, str | None] = {}
    if identified.title:
        updates["title"] = identified.title
    if not (current_artist or "").strip() and identified.artist:
        updates["artist"] = identified.artist
    if not (current_album or "").strip() and identified.album:
        updates["album"] = identified.album
    if not (current_genre or "").strip() and identified.genre:
        updates["genre"] = identified.genre
    return updates
