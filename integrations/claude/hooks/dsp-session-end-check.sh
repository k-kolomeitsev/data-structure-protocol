#!/usr/bin/env bash
set -euo pipefail

TOUCHED_FILE=".dsp-touched"

if [[ ! -d ".dsp" ]]; then
  rm -f "$TOUCHED_FILE"
  exit 0
fi

if [[ ! -f "$TOUCHED_FILE" ]]; then
  exit 0
fi

count=$(wc -l < "$TOUCHED_FILE" | tr -d ' ')

if [[ "$count" -gt 0 ]]; then
  echo "[DSP] $count file(s) were modified during this session:"
  head -20 "$TOUCHED_FILE" | sed 's/^/  /'
  if [[ "$count" -gt 20 ]]; then
    echo "  ... and $((count - 20)) more"
  fi
  echo ""
  echo "[DSP] Reminder: run 'dsp-cli get-orphans' to check for unregistered entities."
  echo "[DSP] Run 'dsp-cli find-by-source <file>' on modified files to verify DSP is up to date."
fi

rm -f "$TOUCHED_FILE"

exit 0
