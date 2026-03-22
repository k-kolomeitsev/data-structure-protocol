#!/usr/bin/env bash
set -euo pipefail

HOOKS_DIR="$(git rev-parse --git-dir)/hooks"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing DSP git hooks..."

cp "$SCRIPT_DIR/pre-commit" "$HOOKS_DIR/pre-commit"
chmod +x "$HOOKS_DIR/pre-commit"

cp "$SCRIPT_DIR/pre-push" "$HOOKS_DIR/pre-push"
chmod +x "$HOOKS_DIR/pre-push"

echo "✓ DSP git hooks installed"
echo ""
echo "Configuration (environment variables):"
echo "  DSP_PRECOMMIT_MODE=warn|block  (default: warn)"
echo "  DSP_CLI=<path-to-dsp-cli.py>   (auto-detected)"
echo "  DSP_SKIP_PATTERNS=<glob,...>    (files to skip, e.g. '*.md,*.txt')"
