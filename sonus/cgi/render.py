from __future__ import annotations

import html
import json

from urllib.parse import urlencode

from sonus.admins import admin_mode_enabled, user_is_admin_listed
from sonus.cgi.common import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_SORT_DIR,
    PAGE_SIZE_OPTIONS,
    FilterOptions,
    LibraryContext,
    PlaylistRow,
    TrackRow,
    UserRow,
    admin_mode_action,
    art_cache_version,
    art_href,
    cgi_script,
    esc,
    fetch_art_action,
    format_duration,
    format_size,
    has_search_filters,
    identify_action,
    library_context_params,
    LIBRARY_CONTEXT_FORM_PREFIX,
    login_action,
    logout_action,
    normalize_page_size,
    normalize_sort_dir,
    parse_library_context,
    playlist_edit_action,
    playlist_href,
    register_action,
    static_asset,
    static_href,
    stream_href,
    track_edit_action,
    track_href,
    upload_art_action,
)


def _header_auth(current_user: UserRow | None) -> str:
    if current_user is None:
        return f"""      <nav class="auth-nav">
        <a href="{esc(login_action())}">Log in</a>
        <a href="{esc(register_action())}">Create account</a>
      </nav>"""
    admin_toggle = ""
    if user_is_admin_listed(current_user):
        checked = " checked" if admin_mode_enabled() else ""
        admin_toggle = f"""        <form class="auth-nav__admin" method="post" action="{esc(admin_mode_action())}">
          <label class="auth-nav__admin-label">
            <input type="checkbox" name="enable" value="1"{checked} onchange="this.form.submit()">
            admin
          </label>
        </form>
"""
    return f"""      <nav class="auth-nav">
        <span class="auth-nav__user">Signed in as {esc(current_user.username)}</span>
{admin_toggle}        <form class="auth-nav__logout" method="post" action="{esc(logout_action())}">
          <button type="submit">Log out</button>
        </form>
      </nav>"""


def page_shell(
    title: str,
    body: str,
    *,
    current_user: UserRow | None = None,
    extra_scripts: list[str] | None = None,
) -> str:
    scripts = [
        f'<script src="{esc(static_asset("library.js"))}" defer></script>',
        f'<script src="{esc(static_asset("player.js"))}" defer></script>',
    ]
    if extra_scripts:
        scripts.extend(extra_scripts)
    script_tags = "\n  ".join(scripts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} · Sonus</title>
  <link rel="stylesheet" href="{esc(static_href())}">
</head>
<body>
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="{esc(cgi_script('index.py'))}">Sonus</a>
      <span class="tagline">Your personal music library</span>
      <nav class="main-nav">
        <a href="{esc(cgi_script('index.py'))}">Library</a>
        <a href="{esc(cgi_script('playlists.py'))}">Playlists</a>
      </nav>
{_header_auth(current_user)}
    </div>
  </header>
  <main class="container main-content">
{body}
  </main>
  <footer class="player-bar" id="player-bar" hidden>
    <div class="container player-bar__inner">
      <img class="player-bar__art" id="player-art" alt="" width="48" height="48">
      <div class="player-bar__meta">
        <div class="player-bar__title" id="player-title"></div>
        <div class="player-bar__artist" id="player-artist"></div>
      </div>
      <audio id="global-player" controls preload="none"></audio>
    </div>
  </footer>
  {script_tags}
</body>
</html>
"""


def render_error(message: str, *, status_hint: str = "Error") -> str:
    body = f"""    <section class="error-panel">
      <h1>{esc(status_hint)}</h1>
      <p>{esc(message)}</p>
      <p><a href="{esc(cgi_script('index.py'))}">Back to library</a></p>
    </section>"""
    return page_shell(status_hint, body)


def render_login(*, next_url: str = "", error: str = "") -> str:
    flash = ""
    if error:
        flash = f"""      <p class="flash-message flash-message--error">{esc(error)}</p>
"""
    next_input = ""
    register_href = register_action()
    if next_url:
        next_input = f'        <input type="hidden" name="next" value="{esc(next_url)}">\n'
        register_href = f"{register_action()}?{urlencode({'next': next_url})}"
    body = f"""    <section class="auth-panel">
      <h1>Log in</h1>
{flash}      <form class="auth-form" method="post" action="{esc(login_action())}">
{next_input}        <label>
          Username
          <input type="text" name="username" autocomplete="username" required>
        </label>
        <label>
          Password
          <input type="password" name="password" autocomplete="current-password" required>
        </label>
        <button type="submit">Log in</button>
      </form>
      <p class="auth-panel__hint">No account yet? <a href="{esc(register_href)}">Create one</a> · <a href="{esc(cgi_script('index.py'))}">← Back to library</a></p>
    </section>
"""
    return page_shell("Log in", body)


def render_register(*, next_url: str = "", error: str = "", username: str = "") -> str:
    flash = ""
    if error:
        flash = f"""      <p class="flash-message flash-message--error">{esc(error)}</p>
"""
    next_input = ""
    login_href = login_action()
    if next_url:
        next_input = f'        <input type="hidden" name="next" value="{esc(next_url)}">\n'
        login_href = f"{login_action()}?{urlencode({'next': next_url})}"
    body = f"""    <section class="auth-panel">
      <h1>Create account</h1>
      <p class="auth-panel__intro">Accounts are only needed for playlists. Browsing and playback do not require an account.</p>
{flash}      <form class="auth-form" method="post" action="{esc(register_action())}">
{next_input}        <label>
          Username
          <input type="text" name="username" value="{esc(username)}" autocomplete="username" required maxlength="64">
        </label>
        <label>
          Password
          <input type="password" name="password" autocomplete="new-password" required>
        </label>
        <label>
          Confirm password
          <input type="password" name="password_confirm" autocomplete="new-password" required>
        </label>
        <button type="submit">Create account</button>
      </form>
      <p class="auth-panel__hint">Already have an account? <a href="{esc(login_href)}">Log in</a> · <a href="{esc(cgi_script('index.py'))}">← Back to library</a></p>
    </section>
"""
    return page_shell("Create account", body)


def render_playlists_login_prompt() -> str:
    next_url = "playlists.py"
    login_href = f"{login_action()}?{urlencode({'next': next_url})}"
    register_href = f"{register_action()}?{urlencode({'next': next_url})}"
    body = f"""    <section class="auth-panel">
      <h1>Playlists</h1>
      <p>Sign in to create and manage your playlists.</p>
      <p><a href="{esc(login_href)}">Log in</a> or <a href="{esc(register_href)}">create an account</a>.</p>
      <p><a href="{esc(cgi_script('index.py'))}">← Back to library</a></p>
    </section>
"""
    return page_shell("Playlists", body)


def _art_img(track: TrackRow, *, css_class: str = "track-art") -> str:
    title = track.title or track.file_name
    if track.art_path:
        version = art_cache_version(track)
        return (
            f'<img class="{css_class}" src="{esc(art_href(track.id, version=version))}" '
            f'alt="Art: {esc(title)}" loading="lazy">'
        )
    initial = esc(title[0].upper() if title else "?")
    return f'<div class="{css_class} track-art--placeholder" aria-hidden="true">{initial}</div>'


def _select_options(
    options: list[str],
    selected: str,
    empty_label: str,
    *,
    max_label: int | None = None,
) -> str:
    lines = [f'          <option value="">{esc(empty_label)}</option>']
    for option in options:
        is_selected = " selected" if option == selected else ""
        label = option
        if max_label is not None and len(option) > max_label:
            label = f"{option[: max_label - 1]}…"
        lines.append(
            f'          <option value="{esc(option)}"{is_selected} title="{esc(option)}">{esc(label)}</option>'
        )
    return "\n".join(lines)


def _filter_query(
    *,
    title: str,
    artist: str,
    album: str,
    genre: str,
    sort: str,
    sort_dir: str,
    page_size: int,
    page: int | None = None,
) -> str:
    params = library_context_params(
        parse_library_context(
            title=title,
            artist=artist,
            album=album,
            genre=genre,
            sort=sort,
            sort_dir=sort_dir,
        )
    )
    if page_size != DEFAULT_PAGE_SIZE:
        params["page_size"] = str(page_size)
    if page is not None and page > 1:
        params["page"] = str(page)
    query = urlencode(params)
    return f"?{query}" if query else ""


def _library_context_hidden_inputs(library: LibraryContext | None) -> str:
    if library is None:
        return ""
    return "\n".join(
        f'          <input type="hidden" name="{esc(LIBRARY_CONTEXT_FORM_PREFIX + key)}" value="{esc(value)}">'
        for key, value in library_context_params(library).items()
    )


def _playlist_queue(tracks: list[TrackRow]) -> list[dict[str, str]]:
    return [
        {
            "streamUrl": stream_href(t.id),
            "title": t.title or t.file_name,
            "artist": t.artist or t.album_artist or "",
            "artUrl": art_href(t.id, version=art_cache_version(t)) if t.art_path else "",
        }
        for t in tracks
    ]


def _playlist_queue_json(tracks: list[TrackRow]) -> str:
    return html.escape(json.dumps(_playlist_queue(tracks)), quote=True)


def _play_button(track: TrackRow) -> str:
    title = track.title or track.file_name
    artist = track.artist or track.album_artist or ""
    art = art_href(track.id, version=art_cache_version(track)) if track.art_path else ""
    return (
        f'<button type="button" class="btn-play" data-play-track '
        f'data-track-id="{track.id}" '
        f'data-stream-url="{esc(stream_href(track.id))}" '
        f'data-title="{esc(title)}" '
        f'data-artist="{esc(artist)}" '
        f'data-art-url="{esc(art)}" '
        f'aria-label="Play {esc(title)}">▶</button>'
    )


def _track_row(track: TrackRow, *, show_album: bool = True, library: LibraryContext | None = None) -> str:
    title = track.title or track.file_name
    artist = track.artist or track.album_artist or "—"
    album_cell = (
        f'<td class="col-album">{esc(track.album or "—")}</td>' if show_album else ""
    )
    return f"""        <tr>
          <td class="col-play">{_play_button(track)}</td>
          <td class="col-art">{_art_img(track, css_class="track-art track-art--sm")}</td>
          <td class="col-title"><a href="{esc(track_href(track.id, library=library))}">{esc(title)}</a></td>
          <td class="col-artist">{esc(artist)}</td>
          {album_cell}
          <td class="col-duration">{esc(format_duration(track.duration_seconds))}</td>
          <td class="col-format"><span class="format-badge format-badge--{esc(track.format)}">{esc(track.format.upper())}</span></td>
        </tr>"""


def render_library(
    tracks: list[TrackRow],
    filtered_count: int,
    library_total: int,
    page: int,
    options: FilterOptions,
    *,
    selected_title: str,
    selected_artist: str,
    selected_album: str,
    selected_genre: str,
    sort: str,
    sort_dir: str,
    page_size: str | int,
    current_user: UserRow | None = None,
) -> str:
    page_size_int = normalize_page_size(page_size)
    sort_dir = normalize_sort_dir(sort, sort_dir)
    max_page = max(1, (filtered_count + page_size_int - 1) // page_size_int) if sort != "random" else 1
    filters_active = has_search_filters(
        title=selected_title,
        artist=selected_artist,
        album=selected_album,
        genre=selected_genre,
    )

    clear_url = cgi_script("index.py")
    base_query = _filter_query(
        title=selected_title,
        artist=selected_artist,
        album=selected_album,
        genre=selected_genre,
        sort=sort,
        sort_dir=sort_dir,
        page_size=page_size_int,
    )
    prev_url = ""
    next_url = ""
    if sort != "random" and page > 1:
        prev_url = cgi_script("index.py") + _filter_query(
            title=selected_title,
            artist=selected_artist,
            album=selected_album,
            genre=selected_genre,
            sort=sort,
            sort_dir=sort_dir,
            page_size=page_size_int,
            page=page - 1,
        )
    if sort != "random" and page < max_page:
        next_url = cgi_script("index.py") + _filter_query(
            title=selected_title,
            artist=selected_artist,
            album=selected_album,
            genre=selected_genre,
            sort=sort,
            sort_dir=sort_dir,
            page_size=page_size_int,
            page=page + 1,
        )

    count_label = (
        f"{filtered_count:,} of {library_total:,} tracks"
        if filters_active
        else f"{library_total:,} tracks"
    )

    rows = "\n".join(
        _track_row(
            track,
            library=parse_library_context(
                title=selected_title,
                artist=selected_artist,
                album=selected_album,
                genre=selected_genre,
                sort=sort,
                sort_dir=sort_dir,
            ),
        )
        for track in tracks
    ) if tracks else (
        '        <tr><td colspan="7" class="empty-state">No tracks match your filters.</td></tr>'
    )

    sort_options = [
        ("title", "Title"),
        ("artist", "Artist"),
        ("album", "Album"),
        ("year", "Year"),
        ("duration", "Duration"),
        ("size", "Size"),
        ("scanned", "Last scanned"),
        ("random", "Random"),
    ]
    sort_select = "\n".join(
        f'          <option value="{key}"{" selected" if sort == key else ""}>{label}</option>'
        for key, label in sort_options
    )

    page_size_select = "\n".join(
        f'          <option value="{size}"{" selected" if page_size_int == size else ""}>{size}</option>'
        for size in PAGE_SIZE_OPTIONS
    )

    body = f"""    <section class="library-header">
      <div class="library-header__top">
        <h1>Library</h1>
        <p class="library-count">{esc(count_label)}</p>
      </div>
      <form id="library-filter-form" class="filter-form" method="get" action="{esc(cgi_script('index.py'))}" data-clear-url="{esc(clear_url)}">
        <div class="filter-grid">
          <label class="filter-field">
            <span>Title</span>
            <input id="search-title" type="search" name="title" value="{esc(selected_title)}" placeholder="Search title…" data-filter-search>
          </label>
          <label class="filter-field">
            <span>Artist</span>
            <input type="search" name="artist" value="{esc(selected_artist)}" placeholder="Search artist…" data-filter-search>
          </label>
          <label class="filter-field">
            <span>Album</span>
            <input type="search" name="album" value="{esc(selected_album)}" placeholder="Search album…" data-filter-search>
          </label>
          <label class="filter-field">
            <span>Genre</span>
            <select name="genre" data-filter-auto>
{_select_options(options.genres, selected_genre, "Any genre", max_label=40)}
            </select>
          </label>
        </div>
        <div class="filter-toolbar">
          <label class="filter-field filter-field--inline">
            <span>Sort</span>
            <select name="sort" data-filter-auto>
{sort_select}
            </select>
          </label>
          <input type="hidden" name="sort_dir" value="{esc(sort_dir)}">
          <button type="button" class="btn-sort-dir" data-sort-dir="asc" title="Ascending" aria-label="Sort ascending">↑</button>
          <button type="button" class="btn-sort-dir" data-sort-dir="desc" title="Descending" aria-label="Sort descending">↓</button>
          <label class="filter-field filter-field--inline">
            <span>Per page</span>
            <select name="page_size" data-filter-auto>
{page_size_select}
            </select>
          </label>
          <button type="button" class="btn-help" data-keyboard-help-open title="Keyboard shortcuts">?</button>
        </div>
      </form>
    </section>

    <div class="table-wrap">
      <table class="track-table">
        <thead>
          <tr>
            <th class="col-play"></th>
            <th class="col-art"></th>
            <th class="col-title">Title</th>
            <th class="col-artist">Artist</th>
            <th class="col-album">Album</th>
            <th class="col-duration">Time</th>
            <th class="col-format">Format</th>
          </tr>
        </thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </div>
"""

    if sort != "random":
        body += f"""    <nav class="pagination" data-page-nav data-prev-url="{esc(prev_url)}" data-next-url="{esc(next_url)}">
      <span>Page {page} of {max_page}</span>
      {"<a href='" + esc(prev_url) + "'>← Previous</a>" if prev_url else "<span class='pagination__disabled'>← Previous</span>"}
      {"<a href='" + esc(next_url) + "'>Next →</a>" if next_url else "<span class='pagination__disabled'>Next →</span>"}
    </nav>
"""

    body += """    <dialog id="keyboard-help" class="help-dialog">
      <h2>Keyboard shortcuts</h2>
      <dl>
        <dt><kbd>/</kbd></dt><dd>Focus title search</dd>
        <dt><kbd>Esc</kbd></dt><dd>Clear filters</dd>
        <dt><kbd>←</kbd> <kbd>→</kbd></dt><dd>Previous / next page (swipe left / right on touch screens)</dd>
        <dt><kbd>?</kbd></dt><dd>Show this help</dd>
      </dl>
      <button type="button" data-keyboard-help-close>Close</button>
    </dialog>
"""

    return page_shell("Library", body, current_user=current_user)


def render_track(
    track: TrackRow,
    playlists: list[PlaylistRow],
    track_playlists: list[PlaylistRow],
    *,
    current_user: UserRow | None = None,
    is_admin: bool = False,
    can_fetch_art: bool = False,
    notice: str = "",
    error: str = "",
    library: LibraryContext | None = None,
    prev_url: str = "",
    next_url: str = "",
) -> str:
    title = track.title or track.file_name
    artist = track.artist or track.album_artist or "—"
    in_playlist_ids = {p.id for p in track_playlists}

    playlist_options = "\n".join(
        f'            <option value="{p.id}">{esc(p.name)}</option>'
        for p in playlists
        if p.id not in in_playlist_ids
    )

    track_playlist_links = (
        ", ".join(
            f'<a href="{esc(playlist_href(p.id))}">{esc(p.name)}</a>'
            for p in track_playlists
        )
        if track_playlists
        else "None"
    )

    meta_rows = [
        ("Artist", esc(artist)),
        ("Album", esc(track.album or "—")),
        ("Album artist", esc(track.album_artist or "—")),
        ("Year", esc(track.year or "—")),
        ("Genre", esc(track.genre or "—")),
        ("Track", esc(str(track.track_number) if track.track_number else "—")),
        ("Disc", esc(str(track.disc_number) if track.disc_number else "—")),
        ("Duration", esc(format_duration(track.duration_seconds))),
        ("Format", esc(track.format.upper())),
        ("File size", esc(format_size(track.file_size))),
        ("File", f"<code>{esc(track.file_name)}</code>"),
    ]

    meta_html = "\n".join(
        f"          <tr><th>{label}</th><td>{value}</td></tr>"
        for label, value in meta_rows
    )

    flash_html = ""
    if notice:
        flash_html += f'<p class="flash-message">{esc(notice)}</p>\n'
    if error:
        flash_html += f'<p class="flash-message flash-message--error">{esc(error)}</p>\n'

    library_hidden = _library_context_hidden_inputs(library)

    fetch_art_form = ""
    if can_fetch_art:
        fetch_art_form = f"""            <form class="inline-form" method="post" action="{esc(fetch_art_action())}">
              <input type="hidden" name="id" value="{track.id}">
{library_hidden}
              <button type="submit">Fetch album art</button>
            </form>
"""

    upload_art_form = ""
    if is_admin:
        upload_art_form = f"""            <form class="inline-form" method="post" action="{esc(upload_art_action())}" enctype="multipart/form-data">
              <input type="hidden" name="id" value="{track.id}">
{library_hidden}
              <label>
                Upload album art
                <input type="file" name="art" accept="image/png,image/jpeg,image/gif" required>
              </label>
              <button type="submit">Upload album art</button>
            </form>
"""

    identify_form = ""
    if is_admin:
        identify_form = f"""            <form class="inline-form" method="post" action="{esc(identify_action())}">
              <input type="hidden" name="id" value="{track.id}">
{library_hidden}
              <button type="submit">Identify</button>
            </form>
"""

    metadata_edit_section = ""
    if is_admin:
        metadata_edit_section = f"""      <section class="track-detail__edit">
        <h2>Edit metadata</h2>
        <form class="track-edit-form" method="post" action="{esc(track_edit_action())}">
          <input type="hidden" name="id" value="{track.id}">
{library_hidden}
          <label>
            Title
            <input type="text" name="title" value="{esc(track.title or '')}" autocomplete="off">
          </label>
          <label>
            Artist
            <input type="text" name="artist" value="{esc(track.artist or '')}" autocomplete="off">
          </label>
          <label>
            Album
            <input type="text" name="album" value="{esc(track.album or '')}" autocomplete="off">
          </label>
          <label>
            Genre
            <input type="text" name="genre" value="{esc(track.genre or '')}" autocomplete="off">
          </label>
          <button type="submit">Save metadata</button>
        </form>
      </section>
"""

    if current_user is not None:
        playlist_section = f"""      <section class="track-detail__playlists">
        <h2>Playlists</h2>
        <p>In: {track_playlist_links}</p>
        <form class="inline-form" method="post" action="{esc(playlist_edit_action())}">
          <input type="hidden" name="action" value="add">
          <input type="hidden" name="track_id" value="{track.id}">
          <label>
            Add to playlist
            <select name="playlist_id" required>
              <option value="">Choose…</option>
{playlist_options}
            </select>
          </label>
          <button type="submit">Add</button>
        </form>
        <form class="inline-form" method="post" action="{esc(playlist_edit_action())}">
          <input type="hidden" name="action" value="create_and_add">
          <input type="hidden" name="track_id" value="{track.id}">
          <label>
            Or create new
            <input type="text" name="name" placeholder="Playlist name" required>
          </label>
          <button type="submit">Create &amp; add</button>
        </form>
      </section>
"""
    else:
        login_params: dict[str, str] = {"id": str(track.id)}
        if library is not None:
            login_params.update(library_context_params(library))
        login_href = f"{login_action()}?{urlencode({'next': f'track.py?{urlencode(login_params)}'})}"
        playlist_section = f"""      <section class="track-detail__playlists">
        <h2>Playlists</h2>
        <p><a href="{esc(login_href)}">Log in</a> to add this track to a playlist.</p>
      </section>
"""

    track_nav = ""
    if prev_url or next_url:
        track_nav = f"""    <nav class="pagination track-pagination" data-page-nav data-prev-url="{esc(prev_url)}" data-next-url="{esc(next_url)}">
      {"<a href='" + esc(prev_url) + "'>← Previous track</a>" if prev_url else "<span class='pagination__disabled'>← Previous track</span>"}
      {"<a href='" + esc(next_url) + "'>Next track →</a>" if next_url else "<span class='pagination__disabled'>Next track →</span>"}
    </nav>
"""

    body = f"""    <article class="track-detail">
      {flash_html}      <div class="track-detail__hero">
        {_art_img(track, css_class="track-art track-art--lg")}
        <div class="track-detail__info">
          <h1>{esc(title)}</h1>
          <p class="track-detail__artist">{esc(artist)}</p>
          <p class="track-detail__album">{esc(track.album or "")}</p>
          <div class="track-detail__actions">
            {_play_button(track)}
            <a class="btn-secondary" href="{esc(stream_href(track.id))}" download>Download</a>
{fetch_art_form}
{upload_art_form}
{identify_form}          </div>
          <audio class="track-player" controls preload="metadata" src="{esc(stream_href(track.id))}"></audio>
        </div>
      </div>

{playlist_section}

{metadata_edit_section}      <section class="track-detail__meta">
        <h2>Details</h2>
        <table class="meta-table">
          <tbody>
{meta_html}
          </tbody>
        </table>
      </section>
    </article>
{track_nav}    <dialog id="keyboard-help" class="help-dialog">
      <h2>Keyboard shortcuts</h2>
      <dl>
        <dt><kbd>←</kbd> <kbd>→</kbd></dt><dd>Previous / next track (swipe left / right on touch screens)</dd>
      </dl>
      <button type="button" data-keyboard-help-close>Close</button>
    </dialog>
"""
    return page_shell(title, body, current_user=current_user)


def render_playlists(
    playlists: list[PlaylistRow],
    *,
    message: str = "",
    current_user: UserRow | None = None,
) -> str:
    rows = ""
    if playlists:
        for playlist in playlists:
            rows += f"""        <tr>
          <td><a href="{esc(playlist_href(playlist.id))}">{esc(playlist.name)}</a></td>
          <td>{playlist.track_count}</td>
          <td>{esc(playlist.updated_at[:10] if playlist.updated_at else "")}</td>
          <td>
            <form class="inline-form" method="post" action="{esc(playlist_edit_action())}" onsubmit="return confirm('Delete this playlist?');">
              <input type="hidden" name="action" value="delete">
              <input type="hidden" name="playlist_id" value="{playlist.id}">
              <button type="submit" class="btn-danger">Delete</button>
            </form>
          </td>
        </tr>
"""
    else:
        rows = '        <tr><td colspan="4" class="empty-state">No playlists yet. Create one below.</td></tr>\n'

    message_html = f'<p class="flash-message">{esc(message)}</p>\n' if message else ""

    body = f"""    <section class="playlists-page">
      <h1>Playlists</h1>
      {message_html}
      <form class="inline-form create-playlist-form" method="post" action="{esc(playlist_edit_action())}">
        <input type="hidden" name="action" value="create">
        <label>
          New playlist
          <input type="text" name="name" placeholder="Playlist name" required>
        </label>
        <button type="submit">Create</button>
      </form>

      <div class="table-wrap">
        <table class="playlist-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Tracks</th>
              <th>Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
{rows}
          </tbody>
        </table>
      </div>
    </section>
"""
    return page_shell("Playlists", body, current_user=current_user)


def render_playlist_detail(
    playlist: PlaylistRow,
    tracks: list[TrackRow],
    *,
    message: str = "",
    current_user: UserRow | None = None,
) -> str:
    message_html = f'<p class="flash-message">{esc(message)}</p>\n' if message else ""

    if tracks:
        queue_json = _playlist_queue_json(tracks)
        play_all_btn = (
            f'<button type="button" class="btn-play-all" data-play-queue="{queue_json}">Play all</button>'
        )
        play_shuffle_btn = (
            f'<button type="button" class="btn-play-all btn-play-shuffle" '
            f'data-play-queue="{queue_json}" data-shuffle>Play shuffle</button>'
        )
        play_btns = f"{play_all_btn}\n          {play_shuffle_btn}"
    else:
        play_btns = ""

    rows = "\n".join(
        f"""        <tr>
          <td class="col-play">{_play_button(track)}</td>
          <td class="col-art">{_art_img(track, css_class="track-art track-art--sm")}</td>
          <td class="col-title"><a href="{esc(track_href(track.id))}">{esc(track.title or track.file_name)}</a></td>
          <td class="col-artist">{esc(track.artist or track.album_artist or "—")}</td>
          <td class="col-duration">{esc(format_duration(track.duration_seconds))}</td>
          <td>
            <form class="inline-form" method="post" action="{esc(playlist_edit_action())}">
              <input type="hidden" name="action" value="remove">
              <input type="hidden" name="playlist_id" value="{playlist.id}">
              <input type="hidden" name="track_id" value="{track.id}">
              <button type="submit" class="btn-danger">Remove</button>
            </form>
          </td>
        </tr>"""
        for track in tracks
    ) if tracks else '        <tr><td colspan="6" class="empty-state">This playlist is empty. Add tracks from the library.</td></tr>\n'

    body = f"""    <section class="playlist-detail">
      <div class="playlist-detail__header">
        <p class="breadcrumb"><a href="{esc(cgi_script('playlists.py'))}">Playlists</a> / {esc(playlist.name)}</p>
        <h1>{esc(playlist.name)}</h1>
        <p class="playlist-count">{playlist.track_count} track{"s" if playlist.track_count != 1 else ""}</p>
        {message_html}
        <div class="playlist-detail__actions">
          {play_btns}
          <form class="inline-form" method="post" action="{esc(playlist_edit_action())}">
            <input type="hidden" name="action" value="rename">
            <input type="hidden" name="playlist_id" value="{playlist.id}">
            <label>
              Rename
              <input type="text" name="name" value="{esc(playlist.name)}" required>
            </label>
            <button type="submit">Save</button>
          </form>
        </div>
      </div>

      <div class="table-wrap">
        <table class="track-table">
          <thead>
            <tr>
              <th class="col-play"></th>
              <th class="col-art"></th>
              <th class="col-title">Title</th>
              <th class="col-artist">Artist</th>
              <th class="col-duration">Time</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
{rows}
          </tbody>
        </table>
      </div>
    </section>
"""
    return page_shell(playlist.name, body, current_user=current_user)
