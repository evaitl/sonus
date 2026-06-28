#!/usr/bin/env bash
# Create the Sonus data directory.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$ROOT/data"

mkdir -p "$DATA/art"
chmod +x "$ROOT/web/cgi-bin/"*.py 2>/dev/null || true

echo ""
echo "Data directory: $DATA"
echo ""
echo "For Apache (www-data), grant group write on data/ only:"
echo "  sudo usermod -aG \"$(id -gn)\" www-data"
echo "  sudo chgrp \"$(id -gn)\" \"$DATA\" \"$DATA/art\""
echo "  chmod 2775 \"$DATA\" \"$DATA/art\""
echo "  chmod g+rX \"$ROOT\" \"$ROOT/web\" \"$ROOT/sonus\" /media/music"
echo ""
echo "Reload Apache after updating /etc/apache2/conf-available/sonus.conf"
echo "so SONUS_DATABASE_PATH points at: $DATA/library.db"
