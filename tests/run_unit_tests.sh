#!/usr/bin/env sh
set -eu

REPO="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$REPO"
exec python -m unittest discover -s tests -p "test_*.py" -v
