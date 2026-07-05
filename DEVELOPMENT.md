# Sonus Development Log

This document records design and implementation history. It captures what was built, why, and how the project evolved through iterative requests.

**Inspired by:** [ExLibris](https://github.com/evaitl/ExLibris) — personal ebook library scanner and CGI web UI.

---

## Goal

Build a personal music library web app that:

1. Walks designated directory trees for audio files
2. Extracts metadata into a SQLite database
3. Serves a web UI to search, browse, and play music in the browser
4. Lets signed-in users create and manage multiple playlists

The scanner and web server are separate concerns: scan once (or incrementally), browse anytime.

**Music files stay outside the repo** — scan paths point at directories such as `/media/music` or a local `test_music/` folder (both gitignored).

---

## Architecture (current)

```text
/media/music/       ← default audio library (outside repo)
data/               ← runtime data (gitignored)
  library.db
  art/
  scan.log
scan_music.py       ← standalone scan entry point
sonus/
  schema/           ← SQL migrations (001–004)
  models.py         ← SQLAlchemy ORM
  database.py       ← init, migrations, WAL mode, upsert, WMA cleanup, mark missing
  audio_meta.py     ← Mutagen metadata + embedded art extraction
  transcode.py      ← FFmpeg WMA → MP3 (skip when MP3 exists)
  filename_meta.py  ← artist parsing from filenames
  fetch_art.py      ← online album art (MusicBrainz + iTunes fallback)
  file_hash.py      ← SHA-1 for duplicate detection
  scanner.py        ← directory walk, fast rescan, per-track commit, dedup by hash
  auth.py           ← scrypt passwords, signed session cookies
  users.py          ← account registration
  cgi/
    common.py       ← DB queries, FTS search, playlists, auth helpers
    form.py         ← CGI request parsing (stdlib only; no deprecated cgi module)
    render.py       ← server-side HTML
tests/              ← unittest suite (CGI form parser, etc.)
apache/
  sonus.conf        ← path-based Apache config (/sonus/)
  DEPLOYMENT.md     ← Apache install, permissions, troubleshooting
scripts/
  setup-data-dir.sh ← create data/, chmod CGI scripts
  scan-library.sh   ← cron-friendly scan wrapper
web/
  cgi-bin/          ← index, track, stream, art, playlists, auth, fetch_art
  static/
    style.css
    library.js      ← debounced search, keyboard shortcuts
    player.js       ← bottom player bar, queue playback
```

### Data flow

1. **Scan:** walks configured paths; transcodes WMA to MP3 when needed; skips unchanged files by size/mtime before SHA-1; reads tags with Mutagen; fills artist from filename when tags are empty; upserts `data/library.db`; saves embedded art to `data/art/`; removes stale WMA index rows; marks tracks missing when files disappear.
2. **Browse:** CGI scripts read the database and render HTML with server-side pagination and filters. Text search uses **FTS5** (`tracks_fts`), not `LIKE`.
3. **Play:** `stream.py` serves audio with HTTP Range support. Browsers play MP3/FLAC/OGG/etc.; WMA is not played in-browser (hence transcoding).
4. **Playlists:** signed-in users create per-user playlists; tracks are shared library-wide.
5. **Fetch album art:** MusicBrainz + Cover Art Archive, iTunes fallback; updates `art_path` only.
6. **Auth:** optional accounts for playlists; browsing and playback are open.

---

## Session 1 — Initial build (June 2026)

### User request

Create a personal music library web app similar to ExLibris: search, display, play music through a web browser, and create multiple playlists.

### What was built

- **Python package** `sonus` with Typer CLI (`sonus scan`)
- **SQLite schema** with FTS5 over title, artist, album, genre (`001_initial.sql`)
- **Playlists** (`002_playlists.sql`) — playlist and playlist_tracks tables
- **Scanner** for MP3, FLAC, OGG, Opus, M4A, AAC, WAV, WMA using Mutagen
- **CGI web UI:** library index, track detail, streaming, album art, playlists
- **Frontend:** dark/light theme CSS, debounced search, keyboard shortcuts, bottom player bar
- **Apache** path-based config at `/sonus/`
- **Blue Oak Model License 1.0.0** in `LICENSE.md`

### Design choices

- Mirrored ExLibris patterns (CGI + SQLite + separate scan process).
- Playlists stored in SQLite for simple backup alongside `library.db`.

---

## Session 2 — User accounts, fetch album art, documentation (June 2026)

### User request

Add user accounts and `fetch-album-art` commands. Add Blue Oak license. Save conversation as `DEVELOPMENT.md`.

### User accounts

- **Schema migration** `003_users.sql` — `users` table; playlists rebuilt with `user_id`
- **`sonus/auth.py`**, **`sonus/users.py`**, CGI login/register/logout
- **CLI:** `sonus user create`
- Playlists require sign-in; library browsing does not

### Fetch album art

- **`sonus/fetch_art.py`** — MusicBrainz + Cover Art Archive, iTunes fallback
- **CLI:** `sonus fetch-album-art`
- **CGI:** `fetch_art.py` on track detail (stdlib-only imports for CGI; no pydantic in web path)

---

## Session 3 — WMA transcoding, artist parsing, polish (June 2026)

### WMA → MP3 transcoding

Browsers do not play WMA in HTML5 `<audio>`. The scanner now:

- Transcodes `.wma` to a same-stem `.mp3` next to the source file via FFmpeg, then **deletes the WMA**
- **Skips transcoding** when a matching `.mp3` already exists and is not older than the `.wma` (orphan WMA files are left in place)
- Indexes only the MP3; removes WMA rows from the database on each scan
- Requires FFmpeg only when at least one WMA still needs transcoding

Files: `sonus/transcode.py`, updates to `sonus/scanner.py`.

### Artist from filenames

- **`sonus/filename_meta.py`** — parses `NN Artist - Title` and `NN-artist_slug-title` patterns
- Scanner uses filename artist when Mutagen tags are empty
- **CLI:** `sonus fix-artists` backfills existing rows

### Operations fixes

- CGI scripts must be executable (`chmod +x web/cgi-bin/*.py`); `setup-data-dir.sh` does this
- `fetch_art.py` uses `sonus.cgi.common` only (not `sonus.config`) so the dev server works without the venv

---

## Session 4 — Large-library scale (June 2026)

### User request

Will the site scale to ~32,000 tracks? Implement optimizations.

### Fast rescan

- Before SHA-1, skip files whose path already exists in the DB with the same **file size** and **mtime** and a stored content hash
- First scan still hashes every file; nightly rescans avoid reading unchanged audio

### FTS5 search

- Web search moved from `LIKE '%word%'` to **FTS5** `MATCH` queries on `tracks_fts`
- Migration **`004_scale.sql`**: `idx_tracks_content_hash`; rebuild FTS to index **`sort_title`**
- Search matches whole words (tokens), not arbitrary substrings

### Schema version 4

`CURRENT_SCHEMA_VERSION = 4` in `sonus/database.py`.

---

## Session 5 — Python 3.13 CGI compatibility (June 2026)

### Problem

All CGI scripts used `import cgi` and `cgi.FieldStorage()`. The stdlib **`cgi` module was removed in Python 3.13**.

### Solution

- **`sonus/cgi/form.py`** — `read_cgi_form()` and `CgiForm` parse GET query strings and `application/x-www-form-urlencoded` POST bodies using `urllib.parse` only
- All `web/cgi-bin/*.py` scripts import `read_cgi_form` instead of `cgi`
- **`tests/test_cgi_form.py`** — unittest coverage for GET/POST parsing

Apache CGI deployment is unchanged; only request parsing moved off the removed stdlib module.

---

## Supported audio formats

| Extension | Indexed as | Notes |
|-----------|------------|-------|
| `.mp3` | mp3 | Playable in browser |
| `.flac` | flac | Playable in most browsers |
| `.ogg`, `.oga` | ogg | Playable in most browsers |
| `.opus` | opus | Playable in most browsers |
| `.m4a` | m4a | Playable in most browsers |
| `.aac` | aac | Playable in most browsers |
| `.wav` | wav | Playable in browser |
| `.wma` | — | Transcoded to MP3 on scan; not indexed directly |

---

## CLI reference

```bash
sonus scan [--path PATH]...       # index audio files
sonus fetch-album-art --track-id 1
sonus fetch-album-art --all-missing
sonus fetch-album-art --all-missing --force
sonus fix-artists                 # backfill artist from filenames
sonus fix-artists --force         # overwrite existing artist tags
sonus user create USERNAME        # create web login
```

---

## Web UI features

- Search by title, artist, album via **FTS5** (debounced; each word in a field must match)
- Genre filter — exact match dropdown
- Sort by title, artist, album, year, duration, size, scanned, random
- Pagination (25 / 50 / 100 / 200 per page)
- Play in browser with persistent bottom player
- Per-user playlists (requires account)
- Fetch album art online from track detail page
- Keyboard shortcuts: `/` search, `Esc` clear, `←`/`→` pages, `?` help

---

## Tests

```bash
python -m unittest discover -s tests -v
```

Currently covers the CGI form parser and guards against reintroducing `import cgi` in CGI scripts.

---

## Development server

```bash
cd web
chmod +x cgi-bin/*.py
SONUS_CGI_PREFIX=/cgi-bin/ \
SONUS_STATIC_URL=/static/style.css \
SONUS_DATABASE_PATH="$(pwd)/../data/library.db" \
SONUS_SCAN_PATHS="$(pwd)/../test_music" \
python3 -m http.server --cgi 8080 --bind 127.0.0.1
```

Point `SONUS_SCAN_PATHS` at a music directory **outside** the repo for local testing.

---

## What not to commit

The `.gitignore` excludes:

- `data/` — database, album art, WAL files
- `test_music/`, `music/` — local library folders
- Common audio extensions (`*.mp3`, `*.flac`, `*.wma`, …)
- `.venv/`, `__pycache__/`

Never commit audio files or runtime database state to GitHub.

---

## License

Blue Oak Model License 1.0.0 — see [LICENSE.md](LICENSE.md).
