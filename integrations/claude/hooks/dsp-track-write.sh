#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d ".dsp" ]]; then
  exit 0
fi

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" &>/dev/null || PYTHON="python"
command -v "$PYTHON" &>/dev/null || exit 0

input=$(cat)
file_path=$(echo "$input" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null) || exit 0

if [[ -z "$file_path" ]]; then
  exit 0
fi

TOUCHED_FILE=".dsp-touched"

if [[ -f "$TOUCHED_FILE" ]]; then
  if grep -qxF "$file_path" "$TOUCHED_FILE" 2>/dev/null; then
    exit 0
  fi
fi

echo "$file_path" >> "$TOUCHED_FILE"

exit 0
