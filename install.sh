#!/usr/bin/env bash
set -euo pipefail

DSP_REPO="k-kolomeitsev/data-structure-protocol"
DSP_BRANCH="main"
DSP_SKILL_PATH="skills/data-structure-protocol"

usage() {
  cat <<EOF
DSP Skill Installer

Usage: $0 [OPTIONS] [AGENT...]

Agents: cursor, claude, codex, all (default: all)

Options:
  --global    Install to user-level directory (~/.cursor/skills/ etc.)
  --branch B  Use specific branch (default: main)
  --help      Show this help

Examples:
  curl -fsSL https://raw.githubusercontent.com/$DSP_REPO/main/install.sh | bash
  curl -fsSL https://raw.githubusercontent.com/$DSP_REPO/main/install.sh | bash -s -- cursor
  curl -fsSL https://raw.githubusercontent.com/$DSP_REPO/main/install.sh | bash -s -- --global all
EOF
  exit 0
}

GLOBAL=false
AGENTS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global) GLOBAL=true; shift ;;
    --branch) DSP_BRANCH="$2"; shift 2 ;;
    --help) usage ;;
    *) AGENTS+=("$1"); shift ;;
  esac
done

[[ ${#AGENTS[@]} -eq 0 ]] && AGENTS=("all")

get_targets() {
  local agent="$1"
  local base
  if [[ "$GLOBAL" == "true" ]]; then
    case "$agent" in
      cursor) base="$HOME/.cursor/skills" ;;
      claude) base="$HOME/.claude/skills" ;;
      codex)  base="$HOME/.codex/skills" ;;
    esac
  else
    case "$agent" in
      cursor) base=".cursor/skills" ;;
      claude) base=".claude/skills" ;;
      codex)  base=".codex/skills" ;;
    esac
  fi
  echo "$base/data-structure-protocol"
}

install_for_agent() {
  local agent="$1"
  local target
  target="$(get_targets "$agent")"

  echo "→ Installing DSP skill for $agent → $target"
  mkdir -p "$target"

  local tmp
  tmp="$(mktemp -d)"
  trap "rm -rf '$tmp'" EXIT

  curl -fsSL "https://github.com/$DSP_REPO/archive/$DSP_BRANCH.tar.gz" \
    | tar -xz -C "$tmp" --strip-components=1

  cp -r "$tmp/$DSP_SKILL_PATH/"* "$target/"
  echo "✓ DSP skill installed for $agent"
}

resolve_agents() {
  for a in "${AGENTS[@]}"; do
    case "$a" in
      all) echo "cursor claude codex" ;;
      cursor|claude|codex) echo "$a" ;;
      *) echo "Unknown agent: $a" >&2; exit 1 ;;
    esac
  done
}

echo ""
echo "DSP Skill Installer"
echo "==================="
echo ""

for agent in $(resolve_agents); do
  install_for_agent "$agent"
done

echo ""
echo "Done! Restart your agent/IDE to pick up the new skill."
echo ""
