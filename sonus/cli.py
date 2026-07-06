from pathlib import Path

import typer

from sonus.config import load_settings, resolve_art_dir, resolve_database_path
from sonus.database import get_engine, init_db
from sonus.fetch_art import FetchArtError, enrich_track_art
from sonus.console import safe_console_text
from sonus.scanner import print_scan_progress, print_skipped_entries, scan_paths
from sonus.users import UserError, register_user

_PLAIN_CLI = {
    "pretty_exceptions_enable": False,
    "rich_markup_mode": None,
    "context_settings": {"color": False},
}

app = typer.Typer(
    no_args_is_help=True,
    help="Sonus — scan music directories and browse your library.",
    **_PLAIN_CLI,
)

user_app = typer.Typer(
    no_args_is_help=True,
    help="Manage library user accounts.",
    **_PLAIN_CLI,
)
app.add_typer(user_app, name="user")


@app.callback()
def main() -> None:
    """Sonus — personal music library."""


@app.command()
def scan(
    scan_paths_arg: list[Path] = typer.Argument(
        None, help="Directory or file to scan (overrides config)"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config.yaml"
    ),
    path: list[Path] = typer.Option(
        None, "--path", "-p", help="Directory or file to scan (overrides config)"
    ),
    ffmpeg: str | None = typer.Option(
        None, "--ffmpeg", help="Path to ffmpeg executable (for WMA transcoding)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Report directories and files that are skipped"
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress per-file progress"),
) -> None:
    """Scan directories for audio files and update the library database."""
    settings = load_settings(config)
    explicit_paths: list[Path] = []
    if scan_paths_arg:
        explicit_paths.extend(scan_paths_arg)
    if path:
        explicit_paths.extend(path)
    scan_targets = [p.expanduser() for p in explicit_paths] if explicit_paths else settings.scan_paths
    if not scan_targets:
        typer.echo(
            "No scan paths configured. Set scan_paths in config.yaml or pass a path."
        )
        raise typer.Exit(code=1)

    engine = get_engine(resolve_database_path(settings.database_path))
    SessionLocal = init_db(engine)

    with SessionLocal() as session:
        stats = scan_paths(
            session,
            scan_targets,
            art_dir=resolve_art_dir(settings.art_dir),
            ffmpeg_cmd=ffmpeg,
            verbose=verbose,
            on_progress=None if quiet else print_scan_progress,
        )

    summary = (
        f"Scanned {stats.scanned} files, updated {stats.added_or_updated} records"
    )
    if stats.transcoded:
        summary += f", transcoded {stats.transcoded} WMA to MP3"
    if stats.removed_wma:
        summary += f", removed {stats.removed_wma} WMA index entries"
    if stats.skipped:
        summary += f", skipped {stats.skipped} duplicates"
    if stats.unchanged:
        summary += f", skipped {stats.unchanged} unchanged"
    if stats.marked_missing:
        summary += f", marked {stats.marked_missing} missing"
    if verbose and stats.skipped_entries:
        pre_scan_skips = sum(
            1
            for entry in stats.skipped_entries
            if not entry.reason.startswith("duplicate")
            and entry.reason != "unchanged"
        )
        if pre_scan_skips:
            summary += f", skipped {pre_scan_skips} other file(s)/path(s)"
    typer.echo(f"{summary}.")
    if verbose and stats.skipped_entries:
        print_skipped_entries(stats.skipped_entries)
    if stats.errors:
        typer.echo(f"{len(stats.errors)} issue(s):")
        for err in stats.errors:
            typer.echo(f"  - {safe_console_text(err)}")


@app.command("fetch-album-art")
def fetch_album_art(
    track_id: int | None = typer.Option(
        None, "--track-id", "-t", help="Fetch art for a single track id"
    ),
    all_missing: bool = typer.Option(
        False, "--all-missing", help="Fetch art for all tracks without album art"
    ),
    force: bool = typer.Option(
        False, "--force", help="Replace existing album art"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config.yaml"
    ),
) -> None:
    """Fetch album art online for tracks missing embedded art."""
    if track_id is None and not all_missing:
        typer.echo("Pass --track-id or --all-missing.")
        raise typer.Exit(code=1)
    if track_id is not None and all_missing:
        typer.echo("Pass only one of --track-id or --all-missing.")
        raise typer.Exit(code=1)

    settings = load_settings(config)
    db_path = resolve_database_path(settings.database_path)
    engine = get_engine(db_path)
    init_db(engine)

    import sqlite3

    from sonus.cgi.common import track_ids_with_album, update_tracks_art_paths

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if track_id is not None:
            rows = conn.execute(
                "SELECT id, title, artist, album, art_path FROM tracks WHERE id = ? AND is_missing = 0",
                (track_id,),
            ).fetchall()
        else:
            if force:
                rows = conn.execute(
                    "SELECT id, title, artist, album, art_path FROM tracks WHERE is_missing = 0 ORDER BY id"
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, title, artist, album, art_path FROM tracks
                    WHERE is_missing = 0
                      AND (art_path IS NULL OR TRIM(art_path) = '')
                    ORDER BY id
                    """
                ).fetchall()

        if not rows:
            typer.echo("No matching tracks.")
            return

        updated = 0
        errors: list[str] = []
        art_dir = resolve_art_dir(settings.art_dir)
        completed_albums: set[str] = set()

        for row in rows:
            if row["art_path"] and not force:
                continue
            album_key = (row["album"] or "").strip().casefold()
            if album_key and album_key in completed_albums:
                continue
            try:
                track_id = int(row["id"])
                album_track_ids = track_ids_with_album(conn, row["album"])
                if not album_track_ids:
                    album_track_ids = [track_id]

                result = enrich_track_art(
                    track_id=track_id,
                    artist=row["artist"],
                    album=row["album"],
                    title=row["title"],
                    art_dir=art_dir,
                    track_ids=album_track_ids,
                )
                update_tracks_art_paths(conn, result.art_paths)
                updated += len(result.updated_track_ids)
                if album_key:
                    completed_albums.add(album_key)
                label = row["title"] or row["id"]
                if len(result.updated_track_ids) > 1:
                    typer.echo(
                        f"updated: {label} ({result.source}, "
                        f"{len(result.updated_track_ids)} tracks)"
                    )
                else:
                    typer.echo(f"updated: {label} ({result.source})")
            except FetchArtError as exc:
                errors.append(f"{row['id']}: {exc}")

        typer.echo(f"Updated album art for {updated} track(s).")
        if errors:
            typer.echo(f"{len(errors)} issue(s):")
            for err in errors:
                typer.echo(f"  - {safe_console_text(err)}")
    finally:
        conn.close()


@user_app.command("create")
def user_create(
    username: str = typer.Argument(help="Login username"),
    password: str = typer.Option(
        ...,
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
        help="Account password",
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config.yaml"
    ),
) -> None:
    """Create a web login account."""
    cleaned = username.strip()
    if not cleaned:
        typer.echo("Username cannot be empty.")
        raise typer.Exit(code=1)

    settings = load_settings(config)
    db_path = resolve_database_path(settings.database_path)
    engine = get_engine(db_path)
    init_db(engine)

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        register_user(conn, username=cleaned, password=password)
    except UserError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    finally:
        conn.close()

    typer.echo(f"Created user {cleaned!r}.")


@app.command("fix-artists")
def fix_artists(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite artist even when tags already provide one",
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config.yaml"
    ),
) -> None:
    """Fill missing artist fields by parsing track file names."""
    from sonus.filename_meta import artist_from_filename

    settings = load_settings(config)
    db_path = resolve_database_path(settings.database_path)
    engine = get_engine(db_path)
    init_db(engine)

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, file_name, artist
            FROM tracks
            WHERE is_missing = 0
            """
        ).fetchall()

        updated = 0
        for row in rows:
            current = (row["artist"] or "").strip()
            if current and not force:
                continue
            parsed = artist_from_filename(row["file_name"])
            if not parsed:
                continue
            if current == parsed:
                continue
            conn.execute(
                "UPDATE tracks SET artist = ? WHERE id = ?",
                (parsed, row["id"]),
            )
            updated += 1
        conn.commit()
    finally:
        conn.close()

    typer.echo(f"Updated artist for {updated} track(s).")


@app.command("fix-titles")
def fix_titles(
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Path to config.yaml"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Print each updated title"
    ),
) -> None:
    """Remove leading track-number prefixes from stored titles."""
    from sonus.title_cleanup import clean_leading_track_number_title

    settings = load_settings(config)
    db_path = resolve_database_path(settings.database_path)
    engine = get_engine(db_path)
    init_db(engine)

    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, title, sort_title
            FROM tracks
            WHERE is_missing = 0
            """
        ).fetchall()

        updated = 0
        for row in rows:
            title = row["title"] or ""
            sort_title = row["sort_title"] or ""
            new_title = clean_leading_track_number_title(title) if title else None
            new_sort = (
                clean_leading_track_number_title(sort_title) if sort_title else None
            )

            updates: dict[str, str] = {}
            if new_title and new_title != title:
                updates["title"] = new_title
            if new_sort and new_sort != sort_title:
                updates["sort_title"] = new_sort
            if not updates:
                continue

            assignments = ", ".join(f"{column} = ?" for column in updates)
            conn.execute(
                f"UPDATE tracks SET {assignments} WHERE id = ?",
                [*updates.values(), row["id"]],
            )
            updated += 1
            if verbose:
                label = updates.get("title", title)
                typer.echo(f"updated: {label!r}")
        conn.commit()
    finally:
        conn.close()

    typer.echo(f"Updated title for {updated} track(s).")


if __name__ == "__main__":
    app()
