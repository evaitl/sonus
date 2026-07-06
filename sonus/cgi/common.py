from __future__ import annotations

import html
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from sonus.auth import (
    SESSION_COOKIE,
    create_session_token,
    parse_cookie_header,
    parse_session_token,
    session_secret,
)


@dataclass(frozen=True)
class UserRow:
    id: int
    username: str


@dataclass(frozen=True)
class TrackRow:
    id: int
    file_path: str
    file_name: str
    format: str
    file_size: int
    file_mtime: float
    content_hash: str | None
    title: str | None
    sort_title: str | None
    artist: str | None
    album: str | None
    album_artist: str | None
    track_number: int | None
    disc_number: int | None
    year: str | None
    genre: str | None
    duration_seconds: float | None
    art_path: str | None
    first_seen_at: str
    last_scanned_at: str
    is_missing: int


@dataclass(frozen=True)
class PlaylistRow:
    id: int
    name: str
    created_at: str
    updated_at: str
    track_count: int = 0


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_database_path() -> Path:
    return project_root() / "data" / "library.db"


def _resolve_project_path(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = project_root() / path
    return path.resolve()


def _load_yaml_config() -> dict:
    config = project_root() / "config.yaml"
    if not config.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def database_path() -> Path:
    env = os.environ.get("SONUS_DATABASE_PATH")
    if env:
        return Path(env).expanduser().resolve()
    data = _load_yaml_config()
    if data.get("database_path"):
        return _resolve_project_path(Path(data["database_path"]))
    db = _default_database_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    return db


def art_dir() -> Path:
    env = os.environ.get("SONUS_ART_DIR")
    if env:
        path = Path(env).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    data = _load_yaml_config()
    if data.get("art_dir"):
        path = _resolve_project_path(Path(data["art_dir"]))
        path.mkdir(parents=True, exist_ok=True)
        return path
    art = project_root() / "data" / "art"
    art.mkdir(parents=True, exist_ok=True)
    return art


def library_music_dirs() -> list[Path]:
    env = os.environ.get("SONUS_SCAN_PATHS")
    if env:
        return [
            Path(part.strip()).expanduser().resolve()
            for part in env.split(os.pathsep)
            if part.strip()
        ]
    data = _load_yaml_config()
    raw_paths = data.get("scan_paths")
    if isinstance(raw_paths, list) and raw_paths:
        return [_resolve_project_path(Path(str(path))) for path in raw_paths]
    return [Path("/media/music").resolve()]


def static_href() -> str:
    return os.environ.get("SONUS_STATIC_URL", "../static/style.css")


def static_asset(name: str) -> str:
    base = static_href().rsplit("/", 1)[0]
    return f"{base}/{name}"


def cgi_script(name: str) -> str:
    prefix = os.environ.get("SONUS_CGI_PREFIX", "")
    return f"{prefix}{name}"


def art_href(track_id: int, *, version: str | None = None) -> str:
    url = f"{cgi_script('art.py')}?id={track_id}"
    if version:
        url += f"&v={quote(version, safe='')}"
    return url


def stream_href(track_id: int) -> str:
    return f"{cgi_script('stream.py')}?id={track_id}"


def login_action() -> str:
    return cgi_script("login.py")


def register_action() -> str:
    return cgi_script("register.py")


def logout_action() -> str:
    return cgi_script("logout.py")


def fetch_art_action() -> str:
    return cgi_script("fetch_art.py")


def track_edit_action() -> str:
    return cgi_script("track_edit.py")


def admin_mode_action() -> str:
    return cgi_script("admin_mode.py")


TRACK_METADATA_FIELDS = frozenset({"title", "artist", "album", "genre"})


@dataclass(frozen=True)
class LibraryContext:
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    sort: str = "title"
    sort_dir: str = ""


def parse_library_context(
    *,
    title: str = "",
    artist: str = "",
    album: str = "",
    genre: str = "",
    sort: str = "title",
    sort_dir: str = "",
) -> LibraryContext:
    return LibraryContext(
        title=title or "",
        artist=artist or "",
        album=album or "",
        genre=genre or "",
        sort=sort or "title",
        sort_dir=sort_dir or "",
    )


def library_context_from_form(form: object) -> LibraryContext:
    return parse_library_context(
        title=getattr(form, "getfirst")("title", "") or "",
        artist=getattr(form, "getfirst")("artist", "") or "",
        album=getattr(form, "getfirst")("album", "") or "",
        genre=getattr(form, "getfirst")("genre", "") or "",
        sort=getattr(form, "getfirst")("sort", "title") or "title",
        sort_dir=getattr(form, "getfirst")("sort_dir", "") or "",
    )


def library_context_params(library: LibraryContext) -> dict[str, str]:
    sort_dir = normalize_sort_dir(library.sort, library.sort_dir)
    params: dict[str, str] = {}
    if library.title:
        params["title"] = library.title
    if library.artist:
        params["artist"] = library.artist
    if library.album:
        params["album"] = library.album
    if library.genre:
        params["genre"] = library.genre
    if library.sort and library.sort != "title":
        params["sort"] = library.sort
    if sort_dir != DEFAULT_SORT_DIR.get(library.sort, "asc"):
        params["sort_dir"] = sort_dir
    return params


def track_href(track_id: int, *, library: LibraryContext | None = None) -> str:
    url = f"{cgi_script('track.py')}?id={track_id}"
    extra = library_context_params(library) if library else {}
    if not extra:
        return url
    return f"{url}&{urlencode(extra)}"


def playlist_href(playlist_id: int) -> str:
    return f"{cgi_script('playlists.py')}?id={playlist_id}"


def playlist_edit_action() -> str:
    return cgi_script("playlist_edit.py")


def art_cache_version(track: TrackRow) -> str:
    if track.art_path:
        path = project_root() / track.art_path
        if path.is_file():
            return str(int(path.stat().st_mtime))
    return track.last_scanned_at.replace(":", "").replace("-", "").replace("+", "")


def allowed_track_file(file_path: str) -> Path | None:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return None
    for music_dir in library_music_dirs():
        try:
            path.relative_to(music_dir)
            return path
        except ValueError:
            continue
    return None


def connect() -> sqlite3.Connection:
    db = database_path()
    if not db.exists():
        raise FileNotFoundError(f"Library database not found: {db}")
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_rw() -> sqlite3.Connection:
    db = database_path()
    if not db.exists():
        raise FileNotFoundError(f"Library database not found: {db}")
    try:
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError as exc:
        if "readonly" in str(exc).lower() or "unable to open" in str(exc).lower():
            raise PermissionError(
                f"Cannot write to database at {db}. The web server user "
                f"(www-data) needs write permission on the database file and on "
                f"its parent directory {db.parent} (SQLite WAL files)."
            ) from exc
        raise
    return conn


def esc(value: object | None) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def format_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.2f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def row_to_track(row: sqlite3.Row) -> TrackRow:
    return TrackRow(
        id=row["id"],
        file_path=row["file_path"],
        file_name=row["file_name"],
        format=row["format"],
        file_size=row["file_size"],
        file_mtime=row["file_mtime"],
        content_hash=row["content_hash"],
        title=row["title"],
        sort_title=row["sort_title"],
        artist=row["artist"],
        album=row["album"],
        album_artist=row["album_artist"],
        track_number=row["track_number"],
        disc_number=row["disc_number"],
        year=row["year"],
        genre=row["genre"],
        duration_seconds=row["duration_seconds"],
        art_path=row["art_path"],
        first_seen_at=row["first_seen_at"],
        last_scanned_at=row["last_scanned_at"],
        is_missing=row["is_missing"],
    )


SORT_COLUMNS = {
    "title": "COALESCE(NULLIF(tracks.sort_title, ''), NULLIF(tracks.title, ''), tracks.file_name) COLLATE NOCASE",
    "artist": "tracks.artist COLLATE NOCASE",
    "album": "tracks.album COLLATE NOCASE",
    "year": "tracks.year",
    "duration": "tracks.duration_seconds",
    "size": "tracks.file_size",
    "scanned": "tracks.last_scanned_at",
}

DEFAULT_SORT_DIR = {
    "title": "asc",
    "artist": "asc",
    "album": "asc",
    "year": "desc",
    "duration": "desc",
    "size": "desc",
    "scanned": "desc",
}

PAGE_SIZE_OPTIONS = (25, 50, 100, 200)
DEFAULT_PAGE_SIZE = 50


def normalize_page_size(page_size: int | str | None) -> int:
    try:
        size = int(page_size) if page_size is not None and str(page_size).strip() else DEFAULT_PAGE_SIZE
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    return size if size in PAGE_SIZE_OPTIONS else DEFAULT_PAGE_SIZE


def normalize_sort_dir(sort: str, sort_dir: str | None) -> str:
    if sort == "random":
        return "asc"
    if sort_dir in ("asc", "desc"):
        return sort_dir
    return DEFAULT_SORT_DIR.get(sort, "asc")


def sort_order_by(sort: str, sort_dir: str) -> str:
    if sort == "random":
        return "RANDOM()"
    direction = normalize_sort_dir(sort, sort_dir).upper()
    if sort == "year":
        return f"tracks.year IS NULL, tracks.year {direction}"
    if sort == "duration":
        return f"tracks.duration_seconds IS NULL, tracks.duration_seconds {direction}"
    column = SORT_COLUMNS.get(sort, SORT_COLUMNS["title"])
    return f"{column} {direction}"


@dataclass(frozen=True)
class TrackFilter:
    from_sql: str
    where_sql: str
    params: list[object]
    order_by: str


@dataclass(frozen=True)
class FilterOptions:
    genres: list[str]
    albums: list[str]


def load_filter_options(conn: sqlite3.Connection) -> FilterOptions:
    genres = [
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT genre FROM tracks
            WHERE is_missing = 0
              AND genre IS NOT NULL
              AND TRIM(genre) != ''
            ORDER BY genre COLLATE NOCASE
            """
        ).fetchall()
    ]
    albums = [
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT album FROM tracks
            WHERE is_missing = 0
              AND album IS NOT NULL
              AND TRIM(album) != ''
            ORDER BY album COLLATE NOCASE
            """
        ).fetchall()
    ]
    return FilterOptions(genres=genres, albums=albums)


def _search_words(text: str) -> list[str]:
    return [word for word in text.split() if word]


def _fts_quote(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def _fts_column_match(columns: str, word: str) -> str:
    return f"{{{columns}}} : {_fts_quote(word)}"


def _build_fts_match(
    *,
    title: str = "",
    artist: str = "",
    album: str = "",
) -> str | None:
    clauses: list[str] = []
    for word in _search_words(title):
        clauses.append(
            f"({_fts_column_match('title', word)} OR "
            f"{_fts_column_match('sort_title', word)} OR "
            f"{_fts_column_match('file_name', word)})"
        )
    for word in _search_words(artist):
        clauses.append(
            f"({_fts_column_match('artist', word)} OR "
            f"{_fts_column_match('album_artist', word)})"
        )
    for word in _search_words(album):
        clauses.append(_fts_column_match("album", word))
    if not clauses:
        return None
    return " AND ".join(clauses)


def has_search_filters(
    *,
    title: str = "",
    artist: str = "",
    album: str = "",
    genre: str = "",
) -> bool:
    return bool(title.strip() or artist.strip() or album.strip() or genre)


def _track_filter(
    *,
    title: str,
    artist: str,
    album: str,
    genre: str,
    sort: str,
    sort_dir: str = "asc",
) -> TrackFilter:
    order_by = sort_order_by(sort, sort_dir)
    params: list[object] = []
    where: list[str] = ["tracks.is_missing = 0"]
    from_sql = "FROM tracks"

    fts_match = _build_fts_match(title=title, artist=artist, album=album)
    if fts_match:
        from_sql = (
            "FROM tracks INNER JOIN tracks_fts ON tracks_fts.rowid = tracks.id"
        )
        where.append("tracks_fts MATCH ?")
        params.append(fts_match)

    if genre:
        where.append("tracks.genre = ?")
        params.append(genre)

    return TrackFilter(
        from_sql=from_sql,
        where_sql=" AND ".join(where),
        params=params,
        order_by=order_by,
    )


def list_tracks(
    conn: sqlite3.Connection,
    *,
    title: str = "",
    artist: str = "",
    album: str = "",
    genre: str = "",
    sort: str = "title",
    sort_dir: str = "asc",
    page: int = 1,
    page_size: int | str = DEFAULT_PAGE_SIZE,
) -> tuple[list[TrackRow], int, int, int, FilterOptions]:
    sort_dir = normalize_sort_dir(sort, sort_dir)
    page_size = normalize_page_size(page_size)
    library_total = int(
        conn.execute("SELECT COUNT(*) FROM tracks WHERE is_missing = 0").fetchone()[0]
    )
    options = load_filter_options(conn)

    query = _track_filter(
        title=title,
        artist=artist,
        album=album,
        genre=genre,
        sort=sort,
        sort_dir=sort_dir,
    )

    filtered_count = int(
        conn.execute(
            f"SELECT COUNT(*) {query.from_sql} WHERE {query.where_sql}",
            query.params,
        ).fetchone()[0]
    )

    page = max(1, page)

    if sort == "random":
        limit = min(page_size, filtered_count) if filtered_count else 0
        if limit == 0:
            return [], filtered_count, library_total, page, options
        rows = conn.execute(
            f"""
            SELECT tracks.*
            {query.from_sql}
            WHERE {query.where_sql}
            ORDER BY RANDOM()
            LIMIT ?
            """,
            [*query.params, limit],
        ).fetchall()
        return [row_to_track(row) for row in rows], filtered_count, library_total, page, options

    max_page = max(1, (filtered_count + page_size - 1) // page_size)
    if page > max_page:
        page = max_page

    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT tracks.*
        {query.from_sql}
        WHERE {query.where_sql}
        ORDER BY {query.order_by}, tracks.id
        LIMIT ? OFFSET ?
        """,
        [*query.params, page_size, offset],
    ).fetchall()

    return [row_to_track(row) for row in rows], filtered_count, library_total, page, options


def _track_matches_library_filter(
    conn: sqlite3.Connection, track_id: int, library: LibraryContext
) -> bool:
    sort_dir = normalize_sort_dir(library.sort, library.sort_dir)
    query = _track_filter(
        title=library.title,
        artist=library.artist,
        album=library.album,
        genre=library.genre,
        sort=library.sort,
        sort_dir=sort_dir,
    )
    row = conn.execute(
        f"""
        SELECT 1
        {query.from_sql}
        WHERE {query.where_sql} AND tracks.id = ?
        """,
        [*query.params, track_id],
    ).fetchone()
    return row is not None


def effective_library_for_track_nav(
    conn: sqlite3.Connection,
    track_id: int,
    library: LibraryContext,
) -> LibraryContext:
    """Keep sort order but drop filters that no longer include this track."""
    if library.sort == "random":
        return library
    if not has_search_filters(
        title=library.title,
        artist=library.artist,
        album=library.album,
        genre=library.genre,
    ):
        return library
    if _track_matches_library_filter(conn, track_id, library):
        return library
    return parse_library_context(sort=library.sort, sort_dir=library.sort_dir)


def adjacent_library_tracks(
    conn: sqlite3.Connection,
    track_id: int,
    library: LibraryContext,
) -> tuple[int | None, int | None]:
    """Return previous/next track ids in the filtered library sort order."""
    if library.sort == "random":
        return None, None
    library = effective_library_for_track_nav(conn, track_id, library)
    sort_dir = normalize_sort_dir(library.sort, library.sort_dir)
    query = _track_filter(
        title=library.title,
        artist=library.artist,
        album=library.album,
        genre=library.genre,
        sort=library.sort,
        sort_dir=sort_dir,
    )
    row = conn.execute(
        f"""
        SELECT prev_id, next_id FROM (
          SELECT tracks.id,
            LAG(tracks.id) OVER (ORDER BY {query.order_by}, tracks.id) AS prev_id,
            LEAD(tracks.id) OVER (ORDER BY {query.order_by}, tracks.id) AS next_id
          {query.from_sql}
          WHERE {query.where_sql}
        )
        WHERE id = ?
        """,
        [*query.params, track_id],
    ).fetchone()
    if row is None:
        return None, None
    prev_id = int(row["prev_id"]) if row["prev_id"] is not None else None
    next_id = int(row["next_id"]) if row["next_id"] is not None else None
    return prev_id, next_id


def track_library_nav_urls(
    conn: sqlite3.Connection,
    track_id: int,
    library: LibraryContext,
) -> tuple[str, str]:
    effective = effective_library_for_track_nav(conn, track_id, library)
    prev_id, next_id = adjacent_library_tracks(conn, track_id, effective)
    prev_url = track_href(prev_id, library=effective) if prev_id else ""
    next_url = track_href(next_id, library=effective) if next_id else ""
    return prev_url, next_url


def get_track(conn: sqlite3.Connection, track_id: int) -> TrackRow | None:
    row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return row_to_track(row) if row else None


def get_current_user(conn: sqlite3.Connection) -> UserRow | None:
    cookie_header = os.environ.get("HTTP_COOKIE", "")
    token = parse_cookie_header(cookie_header, SESSION_COOKIE)
    if not token:
        return None
    secret = session_secret(fallback_seed=str(database_path()))
    parsed = parse_session_token(token, secret=secret)
    if parsed is None:
        return None
    user_id, username = parsed
    row = conn.execute(
        "SELECT id, username FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None or row["username"] != username:
        return None
    return UserRow(id=int(row["id"]), username=str(row["username"]))


def authenticate_user(
    conn: sqlite3.Connection, *, username: str, password: str
) -> UserRow | None:
    row = conn.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ? COLLATE NOCASE",
        (username.strip(),),
    ).fetchone()
    if row is None:
        return None
    from sonus.auth import verify_password

    if not verify_password(password, row["password_hash"]):
        return None
    return UserRow(id=int(row["id"]), username=str(row["username"]))


def create_session_for_user(user: UserRow) -> str:
    secret = session_secret(fallback_seed=str(database_path()))
    return create_session_token(user_id=user.id, username=user.username, secret=secret)


def safe_referer_location() -> str:
    """Return a same-app redirect target from Referer, or the library index."""
    from urllib.parse import urlparse

    referer = os.environ.get("HTTP_REFERER", "")
    if not referer:
        return cgi_script("index.py")
    parsed = urlparse(referer)
    allowed = ("index.py", "track.py", "playlists.py")
    if not any(parsed.path.rstrip("/").endswith(name) for name in allowed):
        return cgi_script("index.py")
    location = parsed.path
    if parsed.query:
        location += f"?{parsed.query}"
    return location


def update_track_fields(conn: sqlite3.Connection, track_id: int, fields: dict[str, object]) -> None:
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [track_id]
    conn.execute(f"UPDATE tracks SET {columns} WHERE id = ?", values)
    conn.commit()


def parse_track_metadata_form(form) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for field in TRACK_METADATA_FIELDS:
        raw = form.getfirst(field, "")
        cleaned = str(raw or "").strip()
        result[field] = cleaned or None
    return result


def update_track_metadata(
    conn: sqlite3.Connection, track_id: int, fields: dict[str, str | None]
) -> None:
    unknown = set(fields) - TRACK_METADATA_FIELDS
    if unknown:
        raise ValueError(f"invalid metadata fields: {sorted(unknown)}")
    updates = dict(fields)
    if "title" in updates:
        updates["sort_title"] = updates["title"]
    update_track_fields(conn, track_id, updates)


def track_has_placeholder_art(track: TrackRow) -> bool:
    return not (track.art_path or "").strip()


def track_ids_with_album(conn: sqlite3.Connection, album: str | None) -> list[int]:
    """Return track ids sharing the same album name (case-insensitive)."""
    cleaned = (album or "").strip()
    if not cleaned:
        return []
    rows = conn.execute(
        """
        SELECT id FROM tracks
        WHERE is_missing = 0
          AND album IS NOT NULL
          AND TRIM(album) != ''
          AND LOWER(TRIM(album)) = LOWER(?)
        ORDER BY id
        """,
        (cleaned,),
    ).fetchall()
    return [int(row[0]) for row in rows]


def track_ids_with_album_missing_art(
    conn: sqlite3.Connection, album: str | None
) -> list[int]:
    """Return same-album track ids that have no saved album art."""
    cleaned = (album or "").strip()
    if not cleaned:
        return []
    rows = conn.execute(
        """
        SELECT id FROM tracks
        WHERE is_missing = 0
          AND album IS NOT NULL
          AND TRIM(album) != ''
          AND LOWER(TRIM(album)) = LOWER(?)
          AND (art_path IS NULL OR TRIM(art_path) = '')
        ORDER BY id
        """,
        (cleaned,),
    ).fetchall()
    return [int(row[0]) for row in rows]


def propagate_genre_to_album_mates(
    conn: sqlite3.Connection,
    *,
    track_id: int,
    album: str | None,
    genre: str | None,
) -> int:
    """Set genre on same-album tracks that have no genre. Returns rows updated."""
    cleaned_album = (album or "").strip()
    cleaned_genre = (genre or "").strip()
    if not cleaned_album or not cleaned_genre:
        return 0
    cursor = conn.execute(
        """
        UPDATE tracks SET genre = ?
        WHERE is_missing = 0
          AND id != ?
          AND album IS NOT NULL
          AND TRIM(album) != ''
          AND LOWER(TRIM(album)) = LOWER(?)
          AND (genre IS NULL OR TRIM(genre) = '')
        """,
        (cleaned_genre, track_id, cleaned_album),
    )
    conn.commit()
    return int(cursor.rowcount or 0)


def propagate_album_to_album_mates(
    conn: sqlite3.Connection,
    *,
    track_id: int,
    old_album: str | None,
    new_album: str | None,
) -> int:
    """Set album on same-album tracks. Returns rows updated."""
    cleaned_old_album = (old_album or "").strip()
    if not cleaned_old_album:
        return 0
    cleaned_new_album = (new_album or "").strip()
    new_value = cleaned_new_album or None
    cursor = conn.execute(
        """
        UPDATE tracks SET album = ?
        WHERE is_missing = 0
          AND id != ?
          AND album IS NOT NULL
          AND TRIM(album) != ''
          AND LOWER(TRIM(album)) = LOWER(?)
        """,
        (new_value, track_id, cleaned_old_album),
    )
    conn.commit()
    return int(cursor.rowcount or 0)


def update_tracks_art_paths(
    conn: sqlite3.Connection, paths: dict[int, str]
) -> None:
    if not paths:
        return
    for track_id, art_path in paths.items():
        conn.execute(
            "UPDATE tracks SET art_path = ? WHERE id = ?",
            (art_path, track_id),
        )
    conn.commit()


def list_playlists(conn: sqlite3.Connection, *, user_id: int) -> list[PlaylistRow]:
    rows = conn.execute(
        """
        SELECT p.id, p.name, p.created_at, p.updated_at,
               COUNT(pt.track_id) AS track_count
        FROM playlists p
        LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
        WHERE p.user_id = ?
        GROUP BY p.id
        ORDER BY p.name COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    return [
        PlaylistRow(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            track_count=int(row["track_count"]),
        )
        for row in rows
    ]


def get_playlist(
    conn: sqlite3.Connection, playlist_id: int, *, user_id: int | None = None
) -> PlaylistRow | None:
    params: list[object] = [playlist_id]
    user_clause = ""
    if user_id is not None:
        user_clause = " AND p.user_id = ?"
        params.append(user_id)
    row = conn.execute(
        f"""
        SELECT p.id, p.name, p.created_at, p.updated_at,
               COUNT(pt.track_id) AS track_count
        FROM playlists p
        LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
        WHERE p.id = ?{user_clause}
        GROUP BY p.id
        """,
        params,
    ).fetchone()
    if row is None:
        return None
    return PlaylistRow(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        track_count=int(row["track_count"]),
    )


def list_playlist_tracks(
    conn: sqlite3.Connection, playlist_id: int
) -> list[TrackRow]:
    rows = conn.execute(
        """
        SELECT t.*
        FROM playlist_tracks pt
        JOIN tracks t ON t.id = pt.track_id
        WHERE pt.playlist_id = ? AND t.is_missing = 0
        ORDER BY pt.position, t.id
        """,
        (playlist_id,),
    ).fetchall()
    return [row_to_track(row) for row in rows]


def create_playlist(conn: sqlite3.Connection, name: str, *, user_id: int) -> PlaylistRow:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Playlist name cannot be empty")
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO playlists (user_id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (user_id, cleaned, now, now),
    )
    conn.commit()
    playlist = get_playlist(conn, int(cursor.lastrowid), user_id=user_id)
    assert playlist is not None
    return playlist


def rename_playlist(
    conn: sqlite3.Connection, playlist_id: int, name: str, *, user_id: int
) -> None:
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Playlist name cannot be empty")
    now = datetime.now(timezone.utc).isoformat()
    updated = conn.execute(
        "UPDATE playlists SET name = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (cleaned, now, playlist_id, user_id),
    )
    if updated.rowcount == 0:
        raise ValueError("Playlist not found")
    conn.commit()


def delete_playlist(conn: sqlite3.Connection, playlist_id: int, *, user_id: int) -> None:
    deleted = conn.execute(
        "DELETE FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, user_id),
    )
    if deleted.rowcount == 0:
        raise ValueError("Playlist not found")
    conn.commit()


def add_track_to_playlist(
    conn: sqlite3.Connection, playlist_id: int, track_id: int, *, user_id: int
) -> None:
    owned = conn.execute(
        "SELECT 1 FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, user_id),
    ).fetchone()
    if owned is None:
        raise ValueError("Playlist not found")
    row = conn.execute(
        "SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
        (playlist_id, track_id),
    ).fetchone()
    if row is not None:
        return
    max_pos = conn.execute(
        "SELECT COALESCE(MAX(position), -1) FROM playlist_tracks WHERE playlist_id = ?",
        (playlist_id,),
    ).fetchone()[0]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
        (playlist_id, track_id, int(max_pos) + 1),
    )
    conn.execute(
        "UPDATE playlists SET updated_at = ? WHERE id = ?",
        (now, playlist_id),
    )
    conn.commit()


def remove_track_from_playlist(
    conn: sqlite3.Connection, playlist_id: int, track_id: int, *, user_id: int
) -> None:
    owned = conn.execute(
        "SELECT 1 FROM playlists WHERE id = ? AND user_id = ?",
        (playlist_id, user_id),
    ).fetchone()
    if owned is None:
        raise ValueError("Playlist not found")
    conn.execute(
        "DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
        (playlist_id, track_id),
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE playlists SET updated_at = ? WHERE id = ?",
        (now, playlist_id),
    )
    conn.commit()


def playlists_for_track(
    conn: sqlite3.Connection, track_id: int, *, user_id: int
) -> list[PlaylistRow]:
    rows = conn.execute(
        """
        SELECT p.id, p.name, p.created_at, p.updated_at, 0 AS track_count
        FROM playlists p
        JOIN playlist_tracks pt ON pt.playlist_id = p.id
        WHERE pt.track_id = ? AND p.user_id = ?
        ORDER BY p.name COLLATE NOCASE
        """,
        (track_id, user_id),
    ).fetchall()
    return [
        PlaylistRow(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]
