#!/usr/bin/env bash
set -euo pipefail

DSP_ROOT="${DSP_ROOT:-.}"

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
  echo "No dsp-cli.py found. Skipping agent review."
  exit 0
fi

run_dsp() {
  if [[ -n "$DSP_CLI" ]]; then
    $DSP_CLI "$@"
  else
    python "$DSP_CLI_PATH" "$@"
  fi
}

if [[ ! -d "$DSP_ROOT/.dsp" ]]; then
  echo "No .dsp/ directory found. Skipping agent review."
  exit 0
fi

# Prefer the staged diff; fall back to the last commit (post-commit review).
DIFF=$(git diff --staged 2>/dev/null || true)
if [[ -z "$DIFF" ]]; then
  DIFF=$(git diff HEAD~1 2>/dev/null || true)
fi
if [[ -z "$DIFF" ]]; then
  echo "No changes to review."
  exit 0
fi

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMRD 2>/dev/null || true)
if [[ -z "$STAGED_FILES" ]]; then
  STAGED_FILES=$(git diff HEAD~1 --name-only --diff-filter=ACMRD 2>/dev/null || true)
fi

NL=$'\n'
DSP_CONTEXT=""
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  # find-by-source prints "not found" to stdout (exit 1) on a miss.
  entity=$(run_dsp --root "$DSP_ROOT" find-by-source "$file" 2>/dev/null) || true
  if [[ -n "$entity" && "$entity" != *"not found"* ]]; then
    uid=$(printf '%s\n' "$entity" | grep -oE '(obj|func)-[a-f0-9]{8}' | head -1 || true)
    if [[ -n "$uid" ]]; then
      entity_info=$(run_dsp --root "$DSP_ROOT" get-entity "$uid" 2>/dev/null) || true
      DSP_CONTEXT+="=== DSP entity for $file ($uid) ===${NL}${entity_info}${NL}${NL}"
    fi
  else
    DSP_CONTEXT+="=== $file — NOT in DSP ===${NL}${NL}"
  fi
done <<< "$STAGED_FILES"

STATS=$(run_dsp --root "$DSP_ROOT" get-stats 2>/dev/null) || STATS="stats unavailable"
ORPHANS=$(run_dsp --root "$DSP_ROOT" get-orphans 2>/dev/null) || ORPHANS="none"

REVIEW_FILE=$(mktemp /tmp/dsp-review-XXXXXX.md)
cat > "$REVIEW_FILE" <<REVIEW_EOF
# DSP Consistency Review Request

## Git Diff

\`\`\`diff
$DIFF
\`\`\`

## DSP State for Affected Files

$DSP_CONTEXT

## Project Stats

$STATS

## Current Orphans

$ORPHANS

## Review Instructions

Check all items from the DSP consistency review checklist.
For each issue found, provide the exact dsp-cli command to fix it.
REVIEW_EOF

echo "Review context saved to: $REVIEW_FILE"
echo ""
echo "Send this to your agent for review:"
echo "  cat $REVIEW_FILE | pbcopy   # macOS"
echo "  cat $REVIEW_FILE | xclip    # Linux"
echo ""
echo "Or use directly with Claude Code:"
echo "  claude \"Review DSP consistency: \$(cat $REVIEW_FILE)\""
