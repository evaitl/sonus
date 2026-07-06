from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from sonus.audio_meta import AudioMetaError, extract_art, read_metadata
from sonus.config import PROJECT_ROOT, resolve_art_dir, resolve_scan_path
from sonus.database import (
    find_track_by_content_hash,
    mark_missing_tracks,
    remove_wma_tracks,
    upsert_track,
)
from sonus.file_hash import sha1_file
from sonus.filename_meta import coalesce_artist
from sonus.models import Track
from sonus.transcode import (
    TranscodeError,
    find_ffmpeg,
    needs_transcode,
    resolve_wma_to_mp3,
)

WMA_EXTENSION = ".wma"
INDEX_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".ogg",
    ".oga",
    ".opus",
    ".m4a",
    ".aac",
    ".wav",
}
SUPPORTED_EXTENSIONS = INDEX_EXTENSIONS | {WMA_EXTENSION}

ScanProgressCallback = Callable[[int, int, Path, str], None]


@dataclass(frozen=True)
class SkippedEntry:
    path: Path
    reason: str


@dataclass
class ScanStats:
    scanned: int = 0
    added_or_updated: int = 0
    skipped: int = 0
    unchanged: int = 0
    transcoded: int = 0
    removed_wma: int = 0
    marked_missing: int = 0
    errors: list[str] | None = None
    skipped_entries: list[SkippedEntry] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
        if self.skipped_entries is None:
            self.skipped_entries = []


def _record_skip(
    skipped: list[SkippedEntry] | None,
    path: Path,
    reason: str,
    *,
    verbose: bool,
) -> None:
    if not verbose or skipped is None:
        return
    skipped.append(SkippedEntry(path.resolve(), reason))


def safe_console_text(value: str | Path) -> str:
    """Make text safe to print on the current stdout encoding."""
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def print_skipped_entries(entries: list[SkippedEntry]) -> None:
    if not entries:
        return
    print(f"\nSkipped ({len(entries)}):", flush=True)
    for entry in entries:
        print(
            f"  {entry.reason}: {safe_console_text(entry.path)}",
            flush=True,
        )


def iter_track_files(root: Path):
    if not root.exists():
        return
    if root.is_file():
        if root.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield root.resolve()
        return
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path.resolve()


def collect_track_files(
    paths: list[Path],
    *,
    ffmpeg_cmd: str | None = None,
    verbose: bool = False,
    skipped: list[SkippedEntry] | None = None,
) -> tuple[list[Path], list[str], int]:
    files: list[Path] = []
    seen: set[Path] = set()
    errors: list[str] = []
    transcoded = 0
    for root in paths:
        root = resolve_scan_path(root)
        if not root.exists():
            message = "path not found"
            errors.append(f"{message}: {root}")
            _record_skip(skipped, root, message, verbose=verbose)
            continue
        if root.is_file():
            suffix = root.suffix.lower()
            if suffix in SUPPORTED_EXTENSIONS:
                candidates = [root.resolve()]
            else:
                _record_skip(
                    skipped,
                    root,
                    f"unsupported file type ({suffix or 'none'})",
                    verbose=verbose,
                )
                candidates = []
        else:
            candidates = []
            try:
                for path in root.rglob("*"):
                    if not path.is_file():
                        continue
                    suffix = path.suffix.lower()
                    if suffix not in SUPPORTED_EXTENSIONS:
                        _record_skip(
                            skipped,
                            path,
                            f"unsupported file type ({suffix or 'none'})",
                            verbose=verbose,
                        )
                        continue
                    candidates.append(path.resolve())
            except OSError as exc:
                message = f"cannot read directory ({exc})"
                errors.append(f"{root}: {message}")
                _record_skip(skipped, root, message, verbose=verbose)
                continue

        for path in candidates:
            suffix = path.suffix.lower()
            if suffix == WMA_EXTENSION:
                try:
                    mp3_path, was_transcoded = resolve_wma_to_mp3(
                        path, ffmpeg_cmd=ffmpeg_cmd
                    )
                    if not mp3_path.is_file():
                        errors.append(
                            f"{path}: transcoded MP3 missing at {mp3_path}"
                        )
                        continue
                    if was_transcoded:
                        transcoded += 1
                    if mp3_path not in seen:
                        seen.add(mp3_path)
                        files.append(mp3_path)
                except TranscodeError as exc:
                    errors.append(f"{path}: {exc}")
                except OSError as exc:
                    errors.append(f"{path}: {exc}")
                continue
            if suffix in INDEX_EXTENSIONS:
                if path.with_suffix(WMA_EXTENSION).is_file():
                    _record_skip(
                        skipped,
                        path,
                        "companion WMA exists",
                        verbose=verbose,
                    )
                    continue
                if path not in seen:
                    seen.add(path)
                    files.append(path)
    return files, errors, transcoded


def scan_paths_need_wma_transcode(paths: list[Path]) -> bool:
    """True when at least one WMA lacks a current matching MP3."""
    for root in paths:
        root = resolve_scan_path(root)
        if not root.exists():
            continue
        for path in iter_track_files(root):
            if path.suffix.lower() == WMA_EXTENSION and needs_transcode(path):
                return True
    return False


def _unchanged_by_stat(existing: Track, *, file_size: int, file_mtime: float) -> bool:
    return (
        not existing.is_missing
        and bool(existing.content_hash)
        and existing.file_size == file_size
        and existing.file_mtime == file_mtime
    )


def _skip_reason_before_meta(
    session: Session,
    *,
    file_path_str: str,
    content_hash: str,
) -> str | None:
    existing = session.scalar(select(Track).where(Track.file_path == file_path_str))
    canonical = find_track_by_content_hash(session, content_hash)

    if canonical is not None and (existing is None or canonical.id != existing.id):
        return "duplicate"

    if (
        existing is not None
        and existing.content_hash == content_hash
        and not existing.is_missing
    ):
        return "unchanged"

    return None


def print_scan_progress(current: int, total: int, path: Path, status: str) -> None:
    width = len(str(total))
    print(
        f"[{current:>{width}}/{total}] {status}: {safe_console_text(path.name)}",
        flush=True,
    )


def scan_paths(
    session: Session,
    paths: list[Path],
    *,
    art_dir: Path | None = None,
    ffmpeg_cmd: str | None = None,
    verbose: bool = False,
    on_progress: ScanProgressCallback | None = None,
) -> ScanStats:
    stats = ScanStats()
    now = datetime.now(timezone.utc)
    art_root = resolve_art_dir(art_dir)

    if scan_paths_need_wma_transcode(paths):
        find_ffmpeg(ffmpeg_cmd)

    track_files, path_errors, stats.transcoded = collect_track_files(
        paths,
        ffmpeg_cmd=ffmpeg_cmd,
        verbose=verbose,
        skipped=stats.skipped_entries,
    )
    stats.errors.extend(path_errors)
    stats.removed_wma = remove_wma_tracks(session)
    total = len(track_files)

    if on_progress and total:
        print(f"Scanning {total:,} audio file(s)...", flush=True)
        if stats.removed_wma:
            print(f"Removed {stats.removed_wma:,} indexed WMA record(s).", flush=True)
        if stats.transcoded:
            print(f"Transcoded {stats.transcoded:,} WMA file(s) to MP3.", flush=True)

    for index, file_path in enumerate(track_files, start=1):
        stats.scanned += 1
        try:
            stat = file_path.stat()
            file_path_str = str(file_path)

            existing = session.scalar(
                select(Track).where(Track.file_path == file_path_str)
            )
            if existing is not None and _unchanged_by_stat(
                existing,
                file_size=stat.st_size,
                file_mtime=stat.st_mtime,
            ):
                stats.unchanged += 1
                _record_skip(
                    stats.skipped_entries, file_path, "unchanged", verbose=verbose
                )
                if on_progress:
                    on_progress(index, total, file_path, "unchanged")
                elif verbose:
                    print(f"unchanged: {safe_console_text(file_path)}", flush=True)
                continue

            content_hash = sha1_file(file_path)
            skip_reason = _skip_reason_before_meta(
                session,
                file_path_str=file_path_str,
                content_hash=content_hash,
            )
            if skip_reason == "duplicate":
                stats.skipped += 1
                canonical = find_track_by_content_hash(session, content_hash)
                duplicate_reason = (
                    f"duplicate (same as {canonical.file_path})"
                    if canonical
                    else "duplicate"
                )
                _record_skip(
                    stats.skipped_entries,
                    file_path,
                    duplicate_reason,
                    verbose=verbose,
                )
                if on_progress:
                    on_progress(index, total, file_path, "duplicate")
                elif verbose:
                    print(
                        f"duplicate: {safe_console_text(file_path)} "
                        f"({safe_console_text(duplicate_reason)})",
                        flush=True,
                    )
                continue

            if skip_reason == "unchanged":
                stats.unchanged += 1
                _record_skip(
                    stats.skipped_entries, file_path, "unchanged", verbose=verbose
                )
                if on_progress:
                    on_progress(index, total, file_path, "unchanged")
                elif verbose:
                    print(f"unchanged: {safe_console_text(file_path)}", flush=True)
                continue

            meta = read_metadata(file_path)
            if meta.errors and verbose:
                stats.errors.extend(f"{file_path}: {err}" for err in meta.errors)

            track = upsert_track(
                session,
                {
                    "file_path": file_path_str,
                    "file_name": file_path.name,
                    "format": meta.format or file_path.suffix.lower().lstrip("."),
                    "file_size": stat.st_size,
                    "file_mtime": stat.st_mtime,
                    "content_hash": content_hash,
                    "title": meta.title or file_path.stem,
                    "sort_title": meta.sort_title,
                    "artist": coalesce_artist(
                        tag_artist=meta.artist, file_name=file_path.name
                    ),
                    "album": meta.album,
                    "album_artist": meta.album_artist,
                    "track_number": meta.track_number,
                    "disc_number": meta.disc_number,
                    "year": meta.year,
                    "genre": meta.genre,
                    "duration_seconds": meta.duration_seconds,
                    "last_scanned_at": now,
                },
            )
            session.flush()

            art_file = extract_art(file_path, art_root / str(track.id))
            if art_file:
                track.art_path = str(art_file.relative_to(PROJECT_ROOT))
                session.add(track)

            session.commit()
            stats.added_or_updated += 1
            if on_progress:
                on_progress(index, total, file_path, "indexed")
            elif verbose:
                title = track.title or track.file_name
                print(f"indexed: {safe_console_text(title)}", flush=True)
        except AudioMetaError as exc:
            session.rollback()
            stats.errors.append(f"{file_path}: {exc}")
            if on_progress:
                on_progress(index, total, file_path, "error")
        except Exception as exc:
            session.rollback()
            stats.errors.append(f"{file_path}: {exc}")
            if on_progress:
                on_progress(index, total, file_path, "error")

    resolved_roots = [resolve_scan_path(path) for path in paths]
    stats.marked_missing = mark_missing_tracks(session, resolved_roots)
    if stats.marked_missing and on_progress:
        print(f"Marked {stats.marked_missing:,} missing file(s).", flush=True)
    elif stats.marked_missing and verbose:
        print(f"marked missing: {stats.marked_missing}", flush=True)

    return stats
