#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' 'uv gerekli: https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
fi
cd "$project"
uv sync --locked --python 3.15.1
exec uv run --locked python tools/install_desktop.py "$@"
