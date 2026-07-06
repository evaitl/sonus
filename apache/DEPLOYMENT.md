# Deploying Sonus with Apache

Sonus runs as **CGI scripts** under a URL path on an existing Apache site (for example `http://your-server/sonus/`). You do not need a separate virtual host unless you want one.

This guide targets **Debian/Ubuntu** with `apache2`. Adapt package names and paths for other distributions.

---

## Overview

```text
Browser  →  Apache (/sonus/...)
              ├─ /sonus/cgi-bin/*.py   CGI (Python, reads data/library.db)
              ├─ /sonus/static/        CSS and JavaScript
              └─ stream.py             reads audio from SONUS_SCAN_PATHS only

Cron (your user)  →  sonus scan  →  updates data/library.db
```

Scanning is **not** done by Apache. Run `sonus scan` as your own user (manually or from cron). The web UI reads the database Apache serves.

---

## Prerequisites

On the server:

1. **Clone or copy** Sonus to a fixed path (example: `/opt/sonus` or `/home/you/sonus`).
2. **Python 3.11+** and a virtual environment with Sonus installed:

   ```bash
   cd /path/to/sonus
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

3. **Music library** on disk (default: `/media/music`). Keep audio **outside** the git tree.
4. **Initial scan** so `data/library.db` exists:

   ```bash
   source .venv/bin/activate
   ./scripts/setup-data-dir.sh
   sonus scan
   sonus user create yourname
   ```

5. **Apache** with CGI enabled:

   ```bash
   sudo apt install apache2
   sudo a2enmod cgi env
   sudo systemctl reload apache2
   ```

6. **FFmpeg** (only if your library contains WMA files):

   ```bash
   sudo apt install ffmpeg
   ```

7. **Chromaprint** (only if you want the admin **Identify** button):

   ```bash
   sudo apt install libchromaprint-tools
   fpcalc -version
   ```

   Register an AcoustID application at [acoustid.org/new-application](https://acoustid.org/new-application) and set `SONUS_ACOUSTID_CLIENT` in the CGI `<Directory>` block (see below).

---

## Install the Apache configuration

### 1. Edit paths in `apache/sonus.conf`

Open `apache/sonus.conf` in your clone and set:

| Directive | Meaning | Example |
|-----------|---------|---------|
| `SONUS_ROOT` | Absolute path to the Sonus install | `/home/you/sonus` |
| `SONUS_PATH` | URL path prefix (no trailing slash) | `/sonus` |

The library will be available at `http://<host>${SONUS_PATH}/` (e.g. `http://localhost/sonus/`).

### 2. Set CGI environment variables

Inside the `<Directory …/web/cgi-bin>` block, Apache passes settings to every CGI script via `SetEnv`. **Required:**

| Variable | Purpose |
|----------|---------|
| `SONUS_DATABASE_PATH` | Path to `data/library.db` |
| `SONUS_CGI_PREFIX` | URL prefix for generated links, must end with `/` (e.g. `/sonus/cgi-bin/`) |
| `SONUS_STATIC_URL` | Full URL path to CSS (e.g. `/sonus/static/style.css`) |

**Strongly recommended for production:**

| Variable | Purpose |
|----------|---------|
| `SONUS_SCAN_PATHS` | Colon-separated music directories (`/media/music` or `/media/music:/mnt/nas/music`). Required for **streaming** — without it, playback returns 404. |
| `SONUS_SESSION_SECRET` | Long random string for signing login cookies. Generate once and keep stable across restarts. |

Example additions (adjust paths):

```apache
SetEnv SONUS_SCAN_PATHS /media/music
SetEnv SONUS_SESSION_SECRET "replace-with-a-long-random-string"
```

Optional:

| Variable | Purpose |
|----------|---------|
| `SONUS_ART_DIR` | Override album art directory (default: `${SONUS_ROOT}/data/art`) |
| `SONUS_ACOUSTID_CLIENT` | AcoustID API key for the admin **Identify** button ([register here](https://acoustid.org/new-application)) |

`config.yaml` is used by the **CLI** (`sonus scan`). CGI scripts read **`SONUS_*` environment variables** set in Apache, not `config.yaml`. Keep scan paths in sync: the same directories in `config.yaml` / `sonus scan` and in `SONUS_SCAN_PATHS`.

### 3. Install and enable the config

```bash
sudo cp /path/to/sonus/apache/sonus.conf /etc/apache2/conf-available/sonus.conf
sudo a2enconf sonus
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### 4. Make CGI scripts executable

```bash
chmod +x /path/to/sonus/web/cgi-bin/*.py
```

`scripts/setup-data-dir.sh` does this automatically.

---

## File permissions

Apache runs CGI as **`www-data`**. It needs:

| Path | Access |
|------|--------|
| Sonus install (`SONUS_ROOT`, `web/`, `sonus/` package) | **Read** (execute on directories) |
| Music library (`/media/music`, etc.) | **Read** |
| `data/` and `data/art/` | **Read + write** (playlists, registration, album-art fetch, SQLite WAL) |

### Recommended: group write on `data/` only

Run as the user who owns the Sonus clone (replace paths and group as needed):

```bash
SONUS=/path/to/sonus
sudo usermod -aG "$(id -gn)" www-data
sudo chgrp "$(id -gn)" "$SONUS/data" "$SONUS/data/art"
chmod 2775 "$SONUS/data" "$SONUS/data/art"
chmod g+rX "$SONUS" "$SONUS/web" "$SONUS/sonus"
chmod g+rX /media/music
```

- Your user can run `sonus scan` and write the database.
- `www-data` can create accounts, playlists, and fetch art.
- Music files stay read-only for the web server.

After changing group membership, reload Apache:

```bash
sudo systemctl reload apache2
```

---

## Python interpreter for CGI

CGI scripts start with `#!/usr/bin/env python3`. Apache uses the **system** `python3`, not your `.venv`.

Ensure system Python can import Sonus:

```bash
# Option A: install into the venv and symlink (simple for one host)
sudo ln -sf /path/to/sonus/.venv/bin/python3 /usr/local/bin/sonus-python3
# Then change shebangs to #!/usr/local/bin/sonus-python3 — or:

# Option B: pip install -e . for system python (less isolated)
sudo pip install -e /path/to/sonus

# Option C: use mod_cgi with SetEnv PYTHONPATH (add to sonus.conf Directory block)
SetEnv PYTHONPATH /path/to/sonus
```

**Option C** is usually enough: Sonus lives under `SONUS_ROOT` and each script adds that path to `sys.path` before importing. No extra install is required if system Python is 3.11+ and dependencies are available. For a self-contained setup, install with `pip install -e .` into the venv and point Apache at that interpreter by editing the shebang line in `web/cgi-bin/*.py` to `#!/path/to/sonus/.venv/bin/python3`.

Verify:

```bash
cd /path/to/sonus/web/cgi-bin
SONUS_DATABASE_PATH=/path/to/sonus/data/library.db \
SONUS_CGI_PREFIX=/sonus/cgi-bin/ \
SONUS_STATIC_URL=/sonus/static/style.css \
SONUS_SCAN_PATHS=/media/music \
./index.py | head -5
```

You should see `Content-Type: text/html` and HTML output.

---

## Post-install checklist

1. Open **`http://<host>/sonus/`** — should redirect to the library index.
2. Confirm **search and pagination** work.
3. **Play a track** — if streaming fails, check `SONUS_SCAN_PATHS` and that `www-data` can read the audio file.
4. **Log in** and create a test playlist.
5. Add your username to **`admins.txt`**, sign in, check **admin** in the header, and test fetch album art / metadata edit on a track page.
6. If using **Identify**, confirm `fpcalc` works for `www-data` and `SONUS_ACOUSTID_CLIENT` is set; open a track and click **Identify**.
7. Run **`sonus scan`** again and confirm new files appear without restarting Apache.

---

## Scheduled scans

Scan as **your user**, not `www-data`:

```bash
chmod +x /path/to/sonus/scripts/scan-library.sh
crontab -e
```

```cron
0 4 * * * /path/to/sonus/scripts/scan-library.sh
```

Logs append to `data/scan.log`.

---

## HTTPS

For TLS termination (reverse proxy or `mod_ssl`):

1. Set a stable **`SONUS_SESSION_SECRET`** before going live.
2. Serve the site over HTTPS so session cookies are not sent in cleartext.
3. If you later add a `Secure` flag to session cookies in code, HTTPS is required for login to persist.

Path-based config (`/sonus/`) works behind a reverse proxy as long as the browser sees the same path prefix you configured in `SONUS_CGI_PREFIX`.

---

## Troubleshooting

### 403 Forbidden on CGI scripts

- `chmod +x web/cgi-bin/*.py`
- Apache `Options +ExecCGI` and `SetHandler cgi-script` on the cgi-bin directory
- `a2enmod cgi`
- SELinux/AppArmor (if enabled): allow httpd to execute the install path

### 500 Internal Server Error

- Check Apache error log: `sudo journalctl -u apache2 -n 50` or `/var/log/apache2/error.log`
- Run a script manually from the shell (see verify command above)
- System Python version must be **3.11+**

### “Database unavailable” or read-only errors

- `SONUS_DATABASE_PATH` must match the file created by `sonus scan`
- `www-data` needs write on `data/` (see permissions above)
- SQLite WAL files (`library.db-wal`, `library.db-shm`) need write access in the same directory

### Playback 404 / “Track not found”

- Set **`SONUS_SCAN_PATHS`** to every directory that contains indexed audio
- Paths must match where files actually live; use absolute paths
- `stream.py` only serves files under those directories (path allowlisting)

### Identify fails (“requires fpcalc” or “requires an AcoustID client key”)

- Install Chromaprint: `sudo apt install libchromaprint-tools`
- Register an API key at [acoustid.org/new-application](https://acoustid.org/new-application)
- Set `SONUS_ACOUSTID_CLIENT` in the CGI `<Directory>` block and reload Apache
- Confirm `www-data` can run `fpcalc` and read the audio file under `SONUS_SCAN_PATHS`

### Styles or scripts missing

- Confirm `SONUS_STATIC_URL` matches the URL path (e.g. `/sonus/static/style.css`)
- `Alias ${SONUS_PATH}/` must point at `web/` so `/sonus/static/` is served

### Wrong links (point at `/cgi-bin/` instead of `/sonus/cgi-bin/`)

- `SONUS_CGI_PREFIX` must include the full path prefix and trailing slash: `/sonus/cgi-bin/`

---

## Changing the URL path

To serve at `/music/` instead of `/sonus/`:

1. Set `Define SONUS_PATH /music` in `sonus.conf`
2. Update `SONUS_CGI_PREFIX` to `/music/cgi-bin/`
3. Update `SONUS_STATIC_URL` to `/music/static/style.css`
4. Update the `RedirectMatch` line to use `/music`
5. `sudo systemctl reload apache2`

---

## Related files

| File | Role |
|------|------|
| `apache/sonus.conf` | Apache snippet copied to `conf-available` |
| `scripts/setup-data-dir.sh` | Creates `data/`, chmods CGI scripts |
| `scripts/scan-library.sh` | Cron-friendly scan wrapper |
| `config.yaml` | CLI scan paths and database location |
| [README.md](../README.md) | General install and usage |
| [DEVELOPMENT.md](../DEVELOPMENT.md) | Implementation history |
