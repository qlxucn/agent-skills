#!/usr/bin/env bash
# One-time: create the isolated Python env (~1.2 GB) and verify pyannote model access.
# Idempotent; prints PYTHON=<interpreter> on success.
set -euo pipefail
VENV="${TRANSCRIPT_VENV:-$HOME/.local/share/transcript-skill/venv}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ ! -x "$VENV/bin/python" ]; then
  command -v uv >/dev/null || { echo "uv not found. Install it with: brew install uv" >&2; exit 1; }
  uv venv --python 3.11 "$VENV" >&2
  uv pip install --python "$VENV/bin/python" "faster-whisper>=1.1" "pyannote.audio>=4.0" psutil >&2
fi

"$VENV/bin/python" "$HERE/transcribe.py" check
echo "PYTHON=$VENV/bin/python"
