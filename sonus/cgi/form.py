"""Parse CGI query strings and urlencoded POST bodies without the stdlib cgi module."""

from __future__ import annotations

import os
import sys
from typing import Any
from urllib.parse import parse_qs


class CgiForm:
    """Minimal replacement for :class:`cgi.FieldStorage` field access."""

    def __init__(self, fields: dict[str, list[str]]) -> None:
        self._fields = fields

    def getfirst(self, key: str, default: Any = None) -> Any:
        values = self._fields.get(key)
        if not values:
            return default
        return values[0]

    def getlist(self, key: str) -> list[str]:
        return list(self._fields.get(key, []))


def _parse_field_string(raw: str) -> dict[str, list[str]]:
    if not raw:
        return {}
    return parse_qs(raw, keep_blank_values=True, encoding="utf-8", errors="replace")


def _read_post_body() -> str:
    content_type = os.environ.get("CONTENT_TYPE", "").partition(";")[0].strip().lower()
    if content_type and content_type != "application/x-www-form-urlencoded":
        if content_type.startswith("multipart/form-data"):
            raise ValueError("multipart form uploads are not supported")
        raise ValueError(f"unsupported POST content type: {content_type or '(missing)'}")

    try:
        length = int(os.environ.get("CONTENT_LENGTH", "0") or "0")
    except ValueError as exc:
        raise ValueError("invalid CONTENT_LENGTH") from exc
    if length < 0:
        raise ValueError("invalid CONTENT_LENGTH")
    if length == 0:
        return ""
    return sys.stdin.read(length)


def read_cgi_form() -> CgiForm:
    """Read form fields from the current CGI request environment."""
    method = os.environ.get("REQUEST_METHOD", "GET").upper()
    if method == "GET" or method == "HEAD":
        return CgiForm(_parse_field_string(os.environ.get("QUERY_STRING", "")))
    if method == "POST":
        return CgiForm(_parse_field_string(_read_post_body()))
    return CgiForm({})
