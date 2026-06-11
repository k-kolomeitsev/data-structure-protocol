#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d ".dsp" ]]; then
  exit 0
fi

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" &>/dev/null || PYTHON="python"
command -v "$PYTHON" &>/dev/null || exit 0

# Hook stdin is JSON with the tool call under "tool_input"; file_path there is
# absolute, while DSP stores repo-relative sources — record the relative form.
# Single-line -c: multi-line scripts break under .bat python shims (pyenv-win);
# malformed JSON / foreign-drive paths make python exit non-zero -> silent skip.
input=$(cat)
file_path=$(printf '%s' "$input" | "$PYTHON" -c 'import json,os,sys; d=json.load(sys.stdin); fp=(d.get("tool_input") or {}).get("file_path") or d.get("file_path") or ""; rel=os.path.relpath(fp) if fp else ""; print("" if (not rel or rel.startswith("..")) else rel.replace(os.sep,"/"))' 2>/dev/null) || exit 0

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
