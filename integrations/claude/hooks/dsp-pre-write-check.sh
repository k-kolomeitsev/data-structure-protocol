#!/usr/bin/env bash
set -euo pipefail

find_dsp_cli() {
  local candidates=(
    ".cursor/skills/data-structure-protocol/scripts/dsp-cli.py"
    ".claude/skills/data-structure-protocol/scripts/dsp-cli.py"
    ".codex/skills/data-structure-protocol/scripts/dsp-cli.py"
    "skills/data-structure-protocol/scripts/dsp-cli.py"
  )
  for c in "${candidates[@]}"; do
    if [[ -f "$c" ]]; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

if [[ ! -d ".dsp" ]]; then
  exit 0
fi

DSP_CLI="${DSP_CLI:-}"
if [[ -z "$DSP_CLI" ]]; then
  DSP_CLI=$(find_dsp_cli) || exit 0
fi

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" &>/dev/null || PYTHON="python"
command -v "$PYTHON" &>/dev/null || exit 0

input=$(cat)
file_path=$(echo "$input" | "$PYTHON" -c "import sys,json; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null) || exit 0

if [[ -z "$file_path" ]]; then
  exit 0
fi

result=$("$PYTHON" "$DSP_CLI" --root . find-by-source "$file_path" 2>/dev/null) || exit 0

if [[ -z "$result" ]]; then
  echo "[DSP] Warning: '$file_path' is not tracked in DSP."
  echo "[DSP] Consider registering it with create-object or create-function after writing."
fi

exit 0
