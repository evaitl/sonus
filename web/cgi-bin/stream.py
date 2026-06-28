#!/usr/bin/env python3
"""CGI entry point: stream an audio file for browser playback."""

from __future__ import annotations

import cgi
import mimetypes
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sonus.cgi.common import allowed_track_file, connect

CHUNK_SIZE = 1024 * 256


def _parse_range(range_header: str, file_size: int) -> tuple[int, int] | None:
    match = re.match(r"bytes=(\d+)-(\d*)", range_header.strip())
    if not match:
        return None
    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1
    if start > end or start >= file_size:
        return None
    end = min(end, file_size - 1)
    return start, end


def _stream_file(path: Path, start: int, end: int) -> None:
    length = end - start + 1
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            chunk = handle.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            sys.stdout.buffer.write(chunk)
            remaining -= len(chunk)
    sys.stdout.buffer.flush()


def main() -> None:
    form = cgi.FieldStorage()
    raw_id = form.getfirst("id")

    if not raw_id or not str(raw_id).isdigit():
        print("Status: 400 Bad Request")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Bad request")
        return

    track_id = int(raw_id)

    try:
        with connect() as conn:
            row = conn.execute(
                "SELECT file_path, file_name, is_missing FROM tracks WHERE id = ?",
                (track_id,),
            ).fetchone()
    except FileNotFoundError:
        print("Status: 503 Service Unavailable")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Database unavailable")
        return

    if row is None or row["is_missing"]:
        print("Status: 404 Not Found")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Track not found")
        return

    track_file = allowed_track_file(row["file_path"])
    if track_file is None:
        print("Status: 404 Not Found")
        print("Content-Type: text/plain; charset=utf-8")
        print()
        print("Track file unavailable")
        return

    file_size = track_file.stat().st_size
    mime, _ = mimetypes.guess_type(str(track_file))
    content_type = mime or "application/octet-stream"

    range_header = os.environ.get("HTTP_RANGE", "")
    byte_range = _parse_range(range_header, file_size) if range_header else None

    if byte_range:
        start, end = byte_range
        length = end - start + 1
        print("Status: 206 Partial Content")
        print(f"Content-Type: {content_type}")
        print(f"Content-Length: {length}")
        print(f"Content-Range: bytes {start}-{end}/{file_size}")
        print("Accept-Ranges: bytes")
        print("Cache-Control: private, max-age=3600")
        print()
        sys.stdout.flush()
        _stream_file(track_file, start, end)
        return

    print(f"Content-Type: {content_type}")
    print(f"Content-Length: {file_size}")
    print("Accept-Ranges: bytes")
    print("Cache-Control: private, max-age=3600")
    print()
    sys.stdout.flush()
    _stream_file(track_file, 0, file_size - 1)


if __name__ == "__main__":
    main()
