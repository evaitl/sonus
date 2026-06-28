#!/usr/bin/env python3
"""Scan configured music directories and update the library database."""

from pathlib import Path

import typer

from sonus.cli import app

if __name__ == "__main__":
    app()
