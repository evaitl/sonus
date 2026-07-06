"""Parse CGI form data without the stdlib :mod:`cgi` module."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs
from email.parser import BytesParser
from email.policy import default


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    content_type: str
    value: bytes


class CgiForm:
    """Minimal replacement for :class:`cgi.FieldStorage` field access."""

    def __init__(
        self,
        fields: dict[str, list[str]],
        files: dict[str, list[UploadedFile]] | None = None,
    ) -> None:
        self._fields = fields
        self._files = files or {}

    def getfirst(self, key: str, default: Any = None) -> Any:
        values = self._fields.get(key)
        if not values:
            return default
        return values[0]

    def getlist(self, key: str) -> list[str]:
        return list(self._fields.get(key, []))

    def getfile(self, key: str) -> UploadedFile | None:
        values = self._files.get(key)
        if not values:
            return None
        return values[0]

    def getfilelist(self, key: str) -> list[UploadedFile]:
        return list(self._files.get(key, []))


def _parse_field_string(raw: str) -> dict[str, list[str]]:
    if not raw:
        return {}
    return parse_qs(raw, keep_blank_values=True, encoding="utf-8", errors="replace")


def _read_post_body() -> bytes:
    content_type = os.environ.get("CONTENT_TYPE", "").partition(";")[0].strip().lower()
    if content_type and content_type not in (
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ):
        raise ValueError(f"unsupported POST content type: {content_type or '(missing)'}")

    try:
        length = int(os.environ.get("CONTENT_LENGTH", "0") or "0")
    except ValueError as exc:
        raise ValueError("invalid CONTENT_LENGTH") from exc
    if length < 0:
        raise ValueError("invalid CONTENT_LENGTH")
    if length == 0:
        return b""
    stdin_buffer = getattr(sys.stdin, "buffer", None)
    if stdin_buffer is not None:
        return stdin_buffer.read(length)
    return sys.stdin.read(length).encode("utf-8", errors="replace")


def _parse_multipart(boundary: str, body: bytes) -> CgiForm:
    parser = BytesParser(policy=default)
    message = parser.parsebytes(
        (
            f"Content-Type: multipart/form-data; boundary={boundary}\r\n"
            "MIME-Version: 1.0\r\n\r\n"
        ).encode("utf-8")
        + body
    )
    fields: dict[str, list[str]] = {}
    files: dict[str, list[UploadedFile]] = {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files.setdefault(name, []).append(
                UploadedFile(
                    filename=filename,
                    content_type=part.get_content_type(),
                    value=payload,
                )
            )
            continue
        charset = part.get_content_charset() or "utf-8"
        fields.setdefault(name, []).append(payload.decode(charset, errors="replace"))
    return CgiForm(fields, files)


def read_cgi_form() -> CgiForm:
    """Read form fields from the current CGI request environment."""
    method = os.environ.get("REQUEST_METHOD", "GET").upper()
    if method == "GET" or method == "HEAD":
        return CgiForm(_parse_field_string(os.environ.get("QUERY_STRING", "")))
    if method == "POST":
        content_type = os.environ.get("CONTENT_TYPE", "")
        body = _read_post_body()
        media_type = content_type.partition(";")[0].strip().lower()
        if media_type == "multipart/form-data":
            boundary = ""
            for part in content_type.split(";")[1:]:
                key, _, value = part.strip().partition("=")
                if key.lower() == "boundary":
                    boundary = value.strip().strip('"')
                    break
            if not boundary:
                raise ValueError("multipart boundary is missing")
            return _parse_multipart(boundary, body)
        return CgiForm(_parse_field_string(body.decode("utf-8", errors="replace")))
    return CgiForm({})
