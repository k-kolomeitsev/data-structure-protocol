#!/usr/bin/env bash
set -euo pipefail

DSP_ROOT="${DSP_ROOT:-$(git rev-parse --show-toplevel)}"

# DSP_CLI env var (full command, e.g. "python /path/to/dsp-cli.py") overrides
# auto-detection. Otherwise the script searches the standard skill locations.
DSP_CLI="${DSP_CLI:-}"
DSP_CLI_PATH=""
if [[ -z "$DSP_CLI" ]]; then
  for candidate in \
    "$DSP_ROOT/.cursor/skills/data-structure-protocol/scripts/dsp-cli.py" \
    "$DSP_ROOT/.claude/skills/data-structure-protocol/scripts/dsp-cli.py" \
    "$DSP_ROOT/.codex/skills/data-structure-protocol/scripts/dsp-cli.py" \
    "$DSP_ROOT/skills/data-structure-protocol/scripts/dsp-cli.py"; do
    if [[ -f "$candidate" ]]; then
      DSP_CLI_PATH="$candidate"
      break
    fi
  done
fi

if [[ -z "$DSP_CLI" && -z "$DSP_CLI_PATH" ]]; then
  echo "[DSP] CLI not found."
  exit 1
fi

run_dsp() {
  if [[ -n "$DSP_CLI" ]]; then
    $DSP_CLI "$@"
  else
    python "$DSP_CLI_PATH" "$@"
  fi
}

if [[ ! -d "$DSP_ROOT/.dsp" ]]; then
  echo "[DSP] No .dsp/ directory found."
  exit 1
fi

SKIP_PATTERNS="${DSP_SKIP_PATTERNS:-*.md,*.txt,*.json,*.yml,*.yaml,*.lock,*.log}"
ISSUES=0

echo "[DSP] Checking staged files against DSP graph..."
echo ""

should_track() {
  local file="$1"
  local patterns pattern
  # read does not glob-expand patterns like *.md against the filesystem
  IFS=',' read -r -a patterns <<< "$SKIP_PATTERNS"
  for pattern in "${patterns[@]}"; do
    case "$file" in $pattern) return 1 ;; esac
  done
  [[ "$file" == *.ts || "$file" == *.tsx || "$file" == *.js || "$file" == *.jsx || \
     "$file" == *.py || "$file" == *.go || "$file" == *.rs || "$file" == *.java || \
     "$file" == *.rb || "$file" == *.vue || "$file" == *.svelte ]]
}

# find-by-source prints matching uids; on a miss it prints "not found" to
# stdout and exits 1, so both the output marker and emptiness must be checked.
is_tracked() {
  local result
  result=$(run_dsp --root "$DSP_ROOT" find-by-source "$1" 2>/dev/null) || true
  [[ -n "$result" && "$result" != *"not found"* ]]
}

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  if should_track "$file"; then
    if is_tracked "$file"; then
      echo "✓ $file"
    else
      echo "⚠ NEW/MODIFIED file not in DSP: $file"
      ((ISSUES++)) || true
    fi
  fi
done < <(git diff --cached --name-only --diff-filter=ACMR)

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  if is_tracked "$file"; then
    echo "✗ DELETED file still in DSP: $file"
    ((ISSUES++)) || true
  fi
done < <(git diff --cached --name-only --diff-filter=D)

orphans=$(run_dsp --root "$DSP_ROOT" get-orphans 2>/dev/null || true)
if [[ -n "$orphans" && "$orphans" != *"No orphans"* && "$orphans" != *"no orphans"* && "$orphans" != *"0 orphan"* ]]; then
  echo ""
  echo "⚠ Orphaned DSP entities detected"
  ((ISSUES++)) || true
fi

echo ""
if [[ $ISSUES -gt 0 ]]; then
  echo "[DSP] Found $ISSUES issue(s). Consider updating DSP before committing."
  exit 1
else
  echo "[DSP] All staged files are consistent with DSP graph."
fi
