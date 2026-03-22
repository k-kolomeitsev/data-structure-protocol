#!/usr/bin/env bash
set -euo pipefail

DSP_CLI="${DSP_CLI:-python .cursor/skills/data-structure-protocol/scripts/dsp-cli.py}"
DSP_ROOT="${DSP_ROOT:-.}"

if [[ ! -d "$DSP_ROOT/.dsp" ]]; then
  echo "No .dsp/ directory found. Skipping agent review."
  exit 0
fi

DIFF=$(git diff --staged 2>/dev/null || git diff HEAD~1)
if [[ -z "$DIFF" ]]; then
  echo "No changes to review."
  exit 0
fi

STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACMRD 2>/dev/null || git diff HEAD~1 --name-only --diff-filter=ACMRD)

DSP_CONTEXT=""
for file in $STAGED_FILES; do
  entity=$($DSP_CLI --root "$DSP_ROOT" find-by-source "$file" 2>/dev/null || true)
  if [[ -n "$entity" ]]; then
    uid=$(echo "$entity" | grep -oP '(obj|func)-[a-f0-9]{8}' | head -1)
    if [[ -n "$uid" ]]; then
      entity_info=$($DSP_CLI --root "$DSP_ROOT" get-entity "$uid" 2>/dev/null || true)
      DSP_CONTEXT+="=== DSP entity for $file ($uid) ===\n$entity_info\n\n"
    fi
  else
    DSP_CONTEXT+="=== $file — NOT in DSP ===\n\n"
  fi
done

STATS=$($DSP_CLI --root "$DSP_ROOT" get-stats 2>/dev/null || echo "stats unavailable")
ORPHANS=$($DSP_CLI --root "$DSP_ROOT" get-orphans 2>/dev/null || echo "none")

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
