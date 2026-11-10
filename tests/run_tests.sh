#!/usr/bin/env sh
set -eu

REPO="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BLENDER="${BLENDER_EXE:-}"

if [ -z "$BLENDER" ]; then
    if command -v blender >/dev/null 2>&1; then
        BLENDER="$(command -v blender)"
    fi
fi

if [ -z "$BLENDER" ] || [ ! -x "$BLENDER" ]; then
    echo "Blender not found. Set BLENDER_EXE to blender." >&2
    exit 2
fi

export BTS_REPO="$REPO"
"$BLENDER" -b --factory-startup --python "$REPO/tests/smoke_blender.py"
