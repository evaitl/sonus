from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class TranscodeError(Exception):
    pass


def find_ffmpeg(explicit: str | None = None) -> str:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.exists():
            raise TranscodeError(f"ffmpeg not found at {path}")
        return str(path.resolve())
    found = shutil.which("ffmpeg")
    if not found:
        raise TranscodeError("ffmpeg not found on PATH (required to transcode WMA files)")
    return found


def mp3_path_for_wma(wma_path: Path) -> Path:
    return wma_path.with_suffix(".mp3")


def find_existing_mp3_for_wma(wma_path: Path) -> Path | None:
    """Return a same-stem MP3 next to the WMA file, if one exists."""
    wma_path = wma_path.resolve()
    expected = mp3_path_for_wma(wma_path)
    if expected.is_file():
        return expected
    for candidate in wma_path.parent.iterdir():
        if (
            candidate.is_file()
            and candidate.stem == wma_path.stem
            and candidate.suffix.lower() == ".mp3"
        ):
            return candidate.resolve()
    return None


def needs_transcode(wma_path: Path, mp3_path: Path | None = None) -> bool:
    mp3 = mp3_path if mp3_path is not None else find_existing_mp3_for_wma(wma_path)
    if mp3 is None:
        return True
    return wma_path.stat().st_mtime > mp3.stat().st_mtime


def resolve_wma_to_mp3(
    wma_path: Path,
    *,
    ffmpeg_cmd: str | None = None,
) -> tuple[Path, bool]:
    """Return the MP3 to index; transcode only when no matching MP3 exists."""
    wma_path = wma_path.resolve()
    if not wma_path.is_file():
        raise TranscodeError(f"WMA file not found: {wma_path}")

    existing_mp3 = find_existing_mp3_for_wma(wma_path)
    if existing_mp3 is not None and not needs_transcode(wma_path, existing_mp3):
        return existing_mp3, False

    return transcode_wma_to_mp3(wma_path, ffmpeg_cmd=ffmpeg_cmd)


def transcode_wma_to_mp3(
    wma_path: Path,
    *,
    ffmpeg_cmd: str | None = None,
) -> tuple[Path, bool]:
    """Transcode WMA to MP3 alongside the source file. Returns (mp3_path, was_transcoded)."""
    wma_path = wma_path.resolve()
    if not wma_path.is_file():
        raise TranscodeError(f"WMA file not found: {wma_path}")

    mp3_path = mp3_path_for_wma(wma_path)
    existing_mp3 = find_existing_mp3_for_wma(wma_path)
    if existing_mp3 is not None:
        mp3_path = existing_mp3
    if not needs_transcode(wma_path, mp3_path):
        return mp3_path, False

    cmd = find_ffmpeg(ffmpeg_cmd)
    args = [
        cmd,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(wma_path),
        "-map_metadata",
        "0",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(mp3_path),
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        raise TranscodeError(f"Timed out transcoding {wma_path.name}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise TranscodeError(detail or f"ffmpeg exited with {result.returncode}")

    if not mp3_path.is_file():
        raise TranscodeError(f"ffmpeg did not create {mp3_path}")

    return mp3_path, True
