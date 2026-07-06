from __future__ import annotations

import sys
from pathlib import Path


def safe_console_text(value: str | Path) -> str:
    """Make text safe to print on the current stdout encoding."""
    text = str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def format_scan_error(path: str | Path, message: str) -> str:
    return f"{safe_console_text(path)}: {safe_console_text(message)}"


def has_bad_filename_unicode(path: Path | str) -> bool:
    """True when the path name cannot be encoded as valid UTF-8."""
    target = Path(path)
    for value in (target.name, str(target)):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return True
    return False
