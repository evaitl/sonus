# Sonus

Sonus scans a directory tree for audio files, extracts metadata into a SQLite database, and serves a web UI to search, browse, play, and organize your music collection into playlists.

Inspired by [ExLibris](https://github.com/evaitl/ExLibris), but built for music.

Supported formats: **MP3**, **FLAC**, **OGG**, **Opus**, **M4A**, **AAC**, **WAV**. **WMA** files are transcoded to MP3 during scan (requires [FFmpeg](https://ffmpeg.org/)).

## Requirements

- **Python 3.11+**
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
python scan_music.py
```

Or use the installed CLI:

```bash
sonus scan
```

Scan specific paths instead of the default:

```bash
python scan_music.py ~/Music
sonus scan --path ~/Music --path /media/music
```

The scanner:

- Walks each path recursively for supported audio files
- Transcodes **WMA** to MP3 alongside the source file when no matching `.mp3` exists (original `.wma` is kept on disk; existing MP3s are reused)
- Fills missing **artist** tags from common filename patterns when embedded metadata is absent
- Computes SHA-1 to skip duplicate files
- Reads metadata with [Mutagen](https://mutagen.readthedocs.io/)
- Saves embedded album art to `data/art/`
- Upserts records into `data/library.db`

Large libraries can take a while. Each track is committed as it is processed, so the web UI updates while a scan is running.

### Fetch album art online

For tracks without embedded art, fetch cover images from MusicBrainz (Cover Art Archive) with an iTunes Search API fallback:

```bash
sonus fetch-album-art --track-id 42
sonus fetch-album-art --all-missing
sonus fetch-album-art --all-missing --force
```

You can also use **Fetch album art** on a track detail page in the web UI.

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
python scan_music.py
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

## User accounts

Browsing and playback do not require an account. **Playlists** are per-user and require sign-in.

Create the first account from the CLI:

```bash
sonus user create yourname
```

Or use **Create account** in the web UI header.

For production, set a stable session secret:

```bash
export SONUS_SESSION_SECRET="a-long-random-string"
```

## Run the web UI

Sonus serves the library through a Python CGI frontend in `web/`.

### Web UI features

- **Search** by title, artist, album, and genre — each word in a field must match (case-insensitive)
- **Pagination** with configurable page size (25, 50, 100, or 200)
- **Sort** by title, artist, album, year, duration, size, last scanned, or random
- **Play** tracks in the browser with a persistent bottom player bar
- **Playlists** — per-user playlists (sign in to create, add tracks, play all)
- **Fetch album art** — download missing cover art from online sources
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

Audio is streamed only from files under configured scan paths (default: `/media/music`).

### Development server (quick test)

```bash
cd web
SONUS_CGI_PREFIX=/cgi-bin/ \
SONUS_STATIC_URL=/static/style.css \
SONUS_DATABASE_PATH="$(pwd)/../data/library.db" \
python3 -m http.server --cgi 8080 --bind 127.0.0.1
```

Open [http://127.0.0.1:8080/cgi-bin/index.py](http://127.0.0.1:8080/cgi-bin/index.py).

### Apache

Sonus mounts on a **URL path** (for example `/sonus/`) on the default Apache site.

```bash
sudo apt install apache2
sudo a2enmod cgi env
sudo systemctl reload apache2
chmod +x web/cgi-bin/*.py
./scripts/setup-data-dir.sh
```

Edit `SONUS_ROOT` in `apache/sonus.conf` to your install path, then:

```bash
sudo cp apache/sonus.conf /etc/apache2/conf-available/sonus.conf
sudo a2enconf sonus
sudo apache2ctl configtest
sudo systemctl reload apache2
```

Open **http://localhost/sonus/**.

The Apache user needs read access to the install tree and `/media/music`, and **write access only on `data/`** (for playlists, album art fetches, and user registration).

## Configuration

`config.yaml` settings:

| Field | Description |
|-------|-------------|
| `scan_paths` | Directories to scan recursively (default: `/media/music`) |
| `database_path` | SQLite database file (default: `data/library.db`) |
| `art_dir` | Album art directory (default: `data/art`) |

Environment variables (prefix `SONUS_`) override config values, for example `SONUS_DATABASE_PATH`.

## How it works

1. **Scanner** (`python scan_music.py` or `sonus scan`) indexes audio files and writes metadata to SQLite. WMA is converted to MP3 for browser playback; only MP3 rows are stored.
2. **Web UI** (`web/cgi-bin/`) reads the database, streams audio, and manages per-user playlists.
3. **Album art** can be fetched online with `sonus fetch-album-art` or from the track detail page.
4. **Artist backfill** with `sonus fix-artists` parses filenames when tags are empty.

Scanning and serving are separate processes, so you can re-index on a schedule without restarting the web server.

See [DEVELOPMENT.md](DEVELOPMENT.md) for implementation history.

## License

Blue Oak Model License 1.0.0 — see [LICENSE.md](LICENSE.md).
