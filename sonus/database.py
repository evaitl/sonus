from pathlib import Path
import os

from sqlalchemy import create_engine, or_, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sonus.config import resolve_scan_path
from sonus.models import Track

SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
CURRENT_SCHEMA_VERSION = 5


def get_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path.resolve()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.execute(text("PRAGMA journal_mode = WAL"))
        conn.commit()
    return engine


def _schema_version(engine: Engine) -> int | None:
    with engine.connect() as conn:
        tables = conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name = 'schema_version'"
            )
        ).fetchone()
        if tables is None:
            return None
        row = conn.execute(text("SELECT MAX(version) FROM schema_version")).fetchone()
        return int(row[0]) if row and row[0] is not None else None


def _apply_schema(engine: Engine, schema_file: Path) -> None:
    ddl = schema_file.read_text(encoding="utf-8")
    with engine.begin() as conn:
        raw = conn.connection.dbapi_connection
        raw.executescript(ddl)


def _apply_migrations(engine: Engine, from_version: int) -> None:
    for version in range(from_version + 1, CURRENT_SCHEMA_VERSION + 1):
        matches = sorted(SCHEMA_DIR.glob(f"{version:03d}_*.sql"))
        if not matches:
            raise FileNotFoundError(f"Missing schema migration for version {version}")
        for schema_file in matches:
            _apply_schema(engine, schema_file)


def init_db(engine: Engine) -> sessionmaker[Session]:
    version = _schema_version(engine)
    if version is None:
        schema_file = SCHEMA_DIR / "001_initial.sql"
        if not schema_file.exists():
            raise FileNotFoundError(f"Missing schema migration: {schema_file}")
        _apply_schema(engine, schema_file)
        version = 1

    if version < CURRENT_SCHEMA_VERSION:
        _apply_migrations(engine, version)
    elif version > CURRENT_SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {version} is newer than "
            f"application version {CURRENT_SCHEMA_VERSION}"
        )

    return sessionmaker(bind=engine, expire_on_commit=False)


def find_track_by_content_hash(session: Session, content_hash: str) -> Track | None:
    return session.scalar(
        select(Track)
        .where(Track.content_hash == content_hash)
        .order_by(Track.id)
        .limit(1)
    )


def remove_wma_tracks(session: Session) -> int:
    """Delete library rows for WMA files (replaced by transcoded MP3 on scan)."""
    from sqlalchemy import delete

    result = session.execute(delete(Track).where(Track.format == "wma"))
    session.commit()
    return int(result.rowcount or 0)


def _track_path_under_roots(file_path: str, roots: list[Path]) -> bool:
    try:
        resolved = Path(file_path).expanduser().resolve()
    except OSError:
        return False
    for root in roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def mark_missing_tracks(session: Session, scan_roots: list[Path]) -> int:
    """Mark indexed tracks missing when their audio file no longer exists on disk."""
    roots = [resolve_scan_path(path) for path in scan_roots]
    if not roots:
        return 0

    prefix_filters = []
    for root in roots:
        root_str = str(root).rstrip(os.sep)
        prefix_filters.append(Track.file_path == root_str)
        prefix_filters.append(Track.file_path.like(f"{root_str}{os.sep}%"))

    tracks = session.scalars(
        select(Track).where(Track.is_missing.is_(False), or_(*prefix_filters))
    ).all()

    marked = 0
    for track in tracks:
        if not _track_path_under_roots(track.file_path, roots):
            continue
        path = Path(track.file_path).expanduser()
        try:
            exists = path.is_file()
        except OSError:
            exists = False
        if not exists:
            track.is_missing = True
            marked += 1

    if marked:
        session.commit()
    return marked


def upsert_track(session: Session, data: dict) -> Track:
    existing = session.scalar(
        select(Track).where(Track.file_path == data["file_path"])
    )
    if existing:
        preserved = {"first_seen_at": existing.first_seen_at}
        for key, value in data.items():
            if key == "first_seen_at":
                continue
            setattr(existing, key, value)
        existing.first_seen_at = preserved["first_seen_at"]
        existing.is_missing = False
        session.add(existing)
        return existing

    if "first_seen_at" not in data:
        data["first_seen_at"] = data["last_scanned_at"]
    track = Track(is_missing=False, **data)
    session.add(track)
    return track
