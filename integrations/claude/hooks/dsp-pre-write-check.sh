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

# Hook stdin is JSON with the tool call under "tool_input"; file_path there is
# absolute, while DSP stores repo-relative sources — convert before lookup.
# Single-line -c: multi-line scripts break under .bat python shims (pyenv-win);
# malformed JSON / foreign-drive paths make python exit non-zero -> silent skip.
input=$(cat)
file_path=$(printf '%s' "$input" | "$PYTHON" -c 'import json,os,sys; d=json.load(sys.stdin); fp=(d.get("tool_input") or {}).get("file_path") or d.get("file_path") or ""; rel=os.path.relpath(fp) if fp else ""; print("" if (not rel or rel.startswith("..")) else rel.replace(os.sep,"/"))' 2>/dev/null) || exit 0

if [[ -z "$file_path" ]]; then
  exit 0
fi

# find-by-source prints "not found" to stdout (exit 1) on a miss.
result=$("$PYTHON" "$DSP_CLI" --root . find-by-source "$file_path" 2>/dev/null) || true

if [[ -z "$result" || "$result" == *"not found"* ]]; then
  echo "[DSP] Warning: '$file_path' is not tracked in DSP."
  echo "[DSP] Consider registering it with create-object or create-function after writing."
fi

exit 0
