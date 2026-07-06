# Sonus

Sonus scans a directory tree for audio files, extracts metadata into a SQLite database, and serves a web UI to search, browse, play, and organize your music collection into playlists.

Inspired by [ExLibris](https://github.com/evaitl/ExLibris), but built for music.

Supported formats: **MP3**, **FLAC**, **OGG**, **Opus**, **M4A**, **AAC**, **WAV**. **WMA** files are transcoded to MP3 during scan (requires [FFmpeg](https://ffmpeg.org/)).

## Requirements

- **Python 3.11+** (including 3.13; CGI scripts do not use the removed stdlib `cgi` module)
- **pip** and **venv** (on Debian/Ubuntu: `python3-venv` and `python3-pip`)
- **[FFmpeg](https://ffmpeg.org/)** — required when your library contains WMA files (transcoded to MP3 on scan)

Verify FFmpeg is installed:

```bash
ffmpeg -version
```

On Debian/Ubuntu:

```bash
sudo apt install ffmpeg
```

## Installation

Clone or download this repository, then create a virtual environment and install Sonus:

```bash
cd sonus
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create the runtime data directory:

```bash
./scripts/setup-data-dir.sh
```

Optional: copy the example config and edit it:

```bash
cp config.yaml.example config.yaml
```

## Layout

```text
sonus/
  data/            ← runtime data (gitignored)
    library.db
    art/
  web/cgi-bin/     ← web UI
  sonus/           ← Python package

/media/music/      ← default location for audio files (outside the repo)
```

By default, Sonus scans `/media/music` and stores the database and album art under `data/`.

**Keep your music outside this repository.** The `.gitignore` excludes common audio formats and local library folders such as `test_music/`. Only the Sonus application code belongs in git.

## Add music

Place your audio files under `/media/music` (subdirectories are scanned recursively):

```text
/media/music/
  Artist/
    Album/
      01 - Track.flac
      02 - Track.flac
```

Create the directory if needed: `sudo mkdir -p /media/music`

## Scan the library

```bash
source .venv/bin/activate
sonus scan
```

Or use the standalone entry point (defaults to `scan` when run with no arguments):

```bash
python scan_music.py
```

Scan specific paths instead of the default:

```bash
sonus scan --path ~/Music --path /media/music
python scan_music.py scan --path ~/Music
```

The scanner:

- Walks each path recursively for supported audio files
- Transcodes **WMA** to MP3 when no matching `.mp3` exists (existing MP3s are reused; newly transcoded WMA files are removed)
- Fills missing **artist** tags from common filename patterns when embedded metadata is absent
- Skips unchanged files using **file size and modification time** before re-hashing (fast rescans on large libraries)
- Computes SHA-1 to skip duplicate files and detect content changes
- Reads metadata with [Mutagen](https://mutagen.readthedocs.io/)
- Saves embedded album art to `data/art/`
- Upserts records into `data/library.db`
- **Marks missing files** — after indexing, any track under the scanned paths whose audio file no longer exists is hidden from the library (`is_missing = 1`). If the file returns on a later scan, it is re-indexed automatically.

Large libraries can take a while on the first scan. Each track is committed as it is processed, so the web UI updates while a scan is running.

### Fetch album art online

For tracks without embedded art, fetch cover images from MusicBrainz (Cover Art Archive) with an iTunes Search API fallback:

```bash
sonus fetch-album-art --track-id 42
sonus fetch-album-art --all-missing
sonus fetch-album-art --all-missing --force
```

You can also use **Fetch album art** on a track detail page in the web UI (administrators only; see `admins.txt`). When the track has an album name, the same artwork is applied to every indexed track with that album.

### Fix missing artist tags

When tags lack an artist, Sonus can parse common filename patterns (`01 Artist - Title.mp3`, `01-artist_slug-title.flac`):

```bash
sonus fix-artists
```

New scans apply the same logic automatically when metadata is missing.

To rebuild from scratch:

```bash
rm -rf data/
./scripts/setup-data-dir.sh
sonus scan
```

### Scheduled scans (cron)

```bash
chmod +x scripts/scan-library.sh
crontab -e
```

Add (replace `/path/to/sonus` with your clone location):

```cron
0 4 * * * /path/to/sonus/scripts/scan-library.sh
```

Nightly scans pick up new files, skip unchanged ones quickly, and mark deleted files as missing.

## User accounts

Browsing and playback do not require an account. **Playlists** are per-user and require sign-in.

Create the first account from the CLI:

```bash
sonus user create yourname
```

Or use **Create account** in the web UI header.

### Administrators (`admins.txt`)

The **Fetch album art** button and **Edit metadata** form on track pages are shown only to signed-in users listed in **`admins.txt`** (one username per line; `#` comments allowed). Matching is case-insensitive.

Listed users must also enable **admin** in the header (checkbox next to Log out) during that browser session. The toggle is stored in a cookie and cleared on log out.

Default location: `admins.txt` in the Sonus install directory. Override with `data/admins.txt` (takes precedence if present) or `SONUS_ADMINS_FILE`.

```text
# admins.txt
evaitl
```

CLI `sonus fetch-album-art` is not restricted — only the web UI admin actions (`fetch_art.py`, `track_edit.py`).

### Web server write access (Apache)

Registration, playlists, **Fetch album art**, and **Edit metadata** update `data/library.db`. Apache runs CGI as **`www-data`**, which must be able to **write** the database file and the **`data/`** directory (SQLite also creates `library.db-wal` and `library.db-shm` there).

If account creation fails with a read-only or permission error, run these from your Sonus install directory (replace `/path/to/sonus` if needed):

```bash
cd /path/to/sonus
./scripts/setup-data-dir.sh   # creates data/ and prints permission hints

# Share data/ with www-data via your login group (recommended)
sudo usermod -aG "$(id -gn)" www-data
sudo chgrp "$(id -gn)" data data/art
sudo chmod 2775 data data/art

# If library.db already exists, give the group write on it too
sudo chgrp "$(id -gn)" data/library.db 2>/dev/null || true
chmod g+rw data/library.db 2>/dev/null || true

# www-data must traverse the install tree (read-only is fine outside data/)
chmod g+rX . web sonus

sudo systemctl reload apache2
```

You may need to **log out and back in** (or reboot) after `usermod` so group membership applies to new processes. Then try **Create account** again.

**Workaround:** create accounts from the CLI as your own user (no `www-data` write access required for this step):

```bash
sonus user create yourname
```

Playlist and art-fetch features still need the permissions above when using the web UI.

See [apache/DEPLOYMENT.md](apache/DEPLOYMENT.md) for the full Apache permission and troubleshooting guide.

For production, set a stable session secret:

```bash
export SONUS_SESSION_SECRET="a-long-random-string"
```

## Run the web UI

Sonus serves the library through a Python CGI frontend in `web/`.

### Web UI features

- **Search** by title, artist, and album using SQLite FTS5 (each word in a field must match)
- **Genre filter** — exact match from a dropdown of indexed genres
- **Pagination** with configurable page size (25, 50, 100, or 200)
- **Sort** by title, artist, album, year, duration, size, last scanned, or random
- **Play** tracks in the browser with a persistent bottom player bar
- **Playlists** — per-user playlists (sign in to create, add tracks, play all)
- **Administrators** — edit title/artist/album/genre and fetch album art (see `admins.txt`); enable **admin** in the header
- **Fetch album art** — online cover art; same image applied to all tracks with matching album name
- **Accounts** — optional sign-in for playlists; browsing and playback are open
- **Keyboard shortcuts** — press <kbd>?</kbd> for help (`/` focus search, `Esc` clear, `←`/`→` change page)

### CGI environment variables

| Variable | Purpose |
|----------|---------|
| `SONUS_DATABASE_PATH` | Path to `data/library.db` |
| `SONUS_CGI_PREFIX` | URL prefix for CGI scripts (e.g. `/sonus/cgi-bin/`) |
| `SONUS_STATIC_URL` | URL to the CSS file (e.g. `/sonus/static/style.css`) |
| `SONUS_SCAN_PATHS` | Colon-separated list of music directories |
| `SONUS_SESSION_SECRET` | Session cookie signing secret (recommended in production) |
| `SONUS_ADMINS_FILE` | Path to `admins.txt` (optional; default `data/admins.txt` or `admins.txt`) |

Audio is streamed only from files under configured scan paths (default: `/media/music`).

### Development server (quick test)

```bash
cd web
chmod +x cgi-bin/*.py
SONUS_CGI_PREFIX=/cgi-bin/ \
SONUS_STATIC_URL=/static/style.css \
SONUS_DATABASE_PATH="$(pwd)/../data/library.db" \
SONUS_SCAN_PATHS="$(pwd)/../test_music" \
python3 -m http.server --cgi 8080 --bind 127.0.0.1
```

Open [http://127.0.0.1:8080/cgi-bin/index.py](http://127.0.0.1:8080/cgi-bin/index.py).

### Apache

Sonus mounts on a **URL path** (for example `/sonus/`) on the default Apache site. See **[apache/DEPLOYMENT.md](apache/DEPLOYMENT.md)** for the full guide: prerequisites, `sonus.conf` variables, `www-data` permissions, Python/CGI setup, HTTPS, cron scans, and troubleshooting.

Quick start after installing Sonus and running an initial `sonus scan`:

```bash
sudo apt install apache2
sudo a2enmod cgi env
chmod +x web/cgi-bin/*.py
./scripts/setup-data-dir.sh
```

Edit `SONUS_ROOT` (and optionally `SONUS_SCAN_PATHS`, `SONUS_SESSION_SECRET`) in `apache/sonus.conf`, then:

```bash
sudo cp apache/sonus.conf /etc/apache2/conf-available/sonus.conf
sudo a2enconf sonus
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Open **http://localhost/sonus/**.

Set **`SONUS_SCAN_PATHS`** in `sonus.conf` so playback works. Set **`SONUS_SESSION_SECRET`** before exposing the site on a network.

## Configuration

`config.yaml` settings:

| Field | Description |
|-------|-------------|
| `scan_paths` | Directories to scan recursively (default: `/media/music`) |
| `database_path` | SQLite database file (default: `data/library.db`) |
| `art_dir` | Album art directory (default: `data/art`) |

Environment variables (prefix `SONUS_`) override config values, for example `SONUS_DATABASE_PATH`.

## How it works

1. **Scanner** (`sonus scan`) indexes audio files and writes metadata to SQLite. WMA is converted to MP3 for browser playback; only MP3 rows are stored. Rescans skip unchanged files by size/mtime; deleted files are marked missing.
2. **Web UI** (`web/cgi-bin/`) reads the database, streams audio, and manages per-user playlists. Search uses FTS5 over title, artist, album, and related fields.
3. **Album art** can be fetched online with `sonus fetch-album-art` or from the track detail page (admins). Matching album names receive the same artwork.
4. **Artist backfill** with `sonus fix-artists` parses filenames when tags are empty.
5. **Administrators** edit metadata in the web UI when listed in `admins.txt` and **admin** mode is enabled in the header.

Scanning and serving are separate processes, so you can re-index on a schedule without restarting the web server.

### Tests

```bash
python -m unittest discover -s tests -v
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for implementation history.

## License

Blue Oak Model License 1.0.0 — see [LICENSE.md](LICENSE.md).
