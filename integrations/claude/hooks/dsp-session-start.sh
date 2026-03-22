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

stats=$("$PYTHON" "$DSP_CLI" --root . get-stats 2>/dev/null) || exit 0

echo "[DSP] Structural memory loaded."
echo "$stats"

exit 0
