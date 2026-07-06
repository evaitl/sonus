"""Load administrator usernames from admins.txt."""

from __future__ import annotations

import os
from pathlib import Path

from sonus.auth import ADMIN_MODE_COOKIE, parse_cookie_header
from sonus.cgi.common import TrackRow, UserRow, project_root, track_has_placeholder_art


def admins_file_path() -> Path:
    env = os.environ.get("SONUS_ADMINS_FILE")
    if env:
        return Path(env).expanduser().resolve()
    data_file = project_root() / "data" / "admins.txt"
    if data_file.is_file():
        return data_file
    return project_root() / "admins.txt"


def parse_admins_text(text: str) -> frozenset[str]:
    usernames: set[str] = set()
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned or cleaned.startswith("#"):
            continue
        usernames.add(cleaned.casefold())
    return frozenset(usernames)


def load_admin_usernames() -> frozenset[str]:
    path = admins_file_path()
    if not path.is_file():
        return frozenset()
    return parse_admins_text(path.read_text(encoding="utf-8"))


def is_admin_username(username: str) -> bool:
    return username.strip().casefold() in load_admin_usernames()


def admin_mode_enabled() -> bool:
    cookie_header = os.environ.get("HTTP_COOKIE", "")
    return parse_cookie_header(cookie_header, ADMIN_MODE_COOKIE) == "1"


def user_is_admin_listed(user: UserRow | None) -> bool:
    return user is not None and is_admin_username(user.username)


def user_is_admin(user: UserRow | None) -> bool:
    return user_is_admin_listed(user) and admin_mode_enabled()


def user_can_fetch_art(user: UserRow | None, track: TrackRow) -> bool:
    if user_is_admin(user):
        return True
    return track_has_placeholder_art(track)
