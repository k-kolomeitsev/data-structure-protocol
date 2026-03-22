#!/usr/bin/env bash
set -euo pipefail

DSP_ROOT="${DSP_ROOT:-$(git rev-parse --show-toplevel)}"

for candidate in \
  "$DSP_ROOT/.cursor/skills/data-structure-protocol/scripts/dsp-cli.py" \
  "$DSP_ROOT/.claude/skills/data-structure-protocol/scripts/dsp-cli.py" \
  "$DSP_ROOT/.codex/skills/data-structure-protocol/scripts/dsp-cli.py" \
  "$DSP_ROOT/skills/data-structure-protocol/scripts/dsp-cli.py"; do
  if [[ -f "$candidate" ]]; then
    DSP_CLI="python $candidate"
    break
  fi
done

DSP_CLI="${DSP_CLI:-}"
if [[ -z "$DSP_CLI" ]]; then
  echo "[DSP] CLI not found."
  exit 1
fi

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
  for pattern in ${SKIP_PATTERNS//,/ }; do
    case "$file" in $pattern) return 1 ;; esac
  done
  [[ "$file" == *.ts || "$file" == *.tsx || "$file" == *.js || "$file" == *.jsx || \
     "$file" == *.py || "$file" == *.go || "$file" == *.rs || "$file" == *.java || \
     "$file" == *.rb || "$file" == *.vue || "$file" == *.svelte ]]
}

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  if should_track "$file"; then
    result=$($DSP_CLI --root "$DSP_ROOT" find-by-source "$file" 2>/dev/null || true)
    if [[ -z "$result" ]]; then
      echo "⚠ NEW/MODIFIED file not in DSP: $file"
      ((ISSUES++)) || true
    else
      echo "✓ $file"
    fi
  fi
done < <(git diff --cached --name-only --diff-filter=ACMR)

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  result=$($DSP_CLI --root "$DSP_ROOT" find-by-source "$file" 2>/dev/null || true)
  if [[ -n "$result" ]]; then
    echo "✗ DELETED file still in DSP: $file"
    ((ISSUES++)) || true
  fi
done < <(git diff --cached --name-only --diff-filter=D)

orphans=$($DSP_CLI --root "$DSP_ROOT" get-orphans 2>/dev/null || true)
if [[ -n "$orphans" && "$orphans" != *"No orphans"* && "$orphans" != *"0 orphan"* ]]; then
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
