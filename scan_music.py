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

if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("scan")
    app()
