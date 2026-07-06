#!/usr/bin/env python3
"""Scan configured music directories and update the library database."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_VENV_PYTHON = _ROOT / ".venv" / "bin" / "python3"


def _reexec_in_venv() -> None:
    if not _VENV_PYTHON.is_file():
        return
    venv_root = (_ROOT / ".venv").resolve()
    if Path(sys.prefix).resolve() == venv_root:
        return
    os.execv(_VENV_PYTHON.as_posix(), [_VENV_PYTHON.as_posix(), *sys.argv])


_reexec_in_venv()

import typer

from sonus.cli import app

_COMMANDS = frozenset({"scan", "fetch-album-art", "fix-artists", "fix-titles", "user"})


def _ensure_scan_command(argv: list[str] | None = None) -> None:
    argv = sys.argv if argv is None else argv
    if len(argv) > 1 and argv[1] in _COMMANDS:
        return
    argv.insert(1, "scan")


if __name__ == "__main__":
    _ensure_scan_command()
    app()
