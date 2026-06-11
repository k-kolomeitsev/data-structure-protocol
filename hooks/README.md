# DSP Git Hooks

Git hooks and standalone scripts for **Data Structure Protocol** consistency checking.

## Overview

DSP hooks provide two complementary modes:

| Mode | Speed | LLM Required | Use Case |
|------|-------|-------------|----------|
| **Deterministic** | Fast (< 1s) | No | Pre-commit / pre-push — checks file presence in DSP graph, orphans, cycles |
| **Agent-assisted** | Slower (10-30s) | Yes | Deep review — semantic analysis of changes against DSP entities, dependency impact |

Deterministic checks run automatically on every commit/push. Agent-assisted review is invoked manually for important commits.

## Installation

### Bash (Linux / macOS / Git Bash on Windows)

```bash
./hooks/install-hooks.sh
```

### PowerShell (Windows)

```powershell
.\hooks\install-hooks.ps1
```

Both installers copy `pre-commit` and `pre-push` into your `.git/hooks/` directory.

## Configuration

All configuration is done via environment variables:

| Variable | Values | Default | Description |
|----------|--------|---------|-------------|
| `DSP_PRECOMMIT_MODE` | `warn` \| `block` | `warn` | `warn` — print issues but allow commit; `block` — reject commit if DSP errors exist |
| `DSP_CLI` | command / path | *(auto-detected)* | Bash hooks: full command, e.g. `python /path/to/dsp-cli.py`. PowerShell scripts: path to `dsp-cli.py` (also accepted via the `-DspCli` parameter). When set, it takes precedence over auto-detection; otherwise the hooks search `.cursor/`, `.claude/`, `.codex/`, and `skills/` directories |
| `DSP_SKIP_PATTERNS` | glob list | `*.md,*.txt,*.json,*.yml,*.yaml,*.lock,*.log` | Comma-separated glob patterns for files to skip during checks (bash hooks) |

### Examples

```bash
# Block commits with DSP errors
export DSP_PRECOMMIT_MODE=block

# Use a custom CLI path
export DSP_CLI="python /path/to/dsp-cli.py"

# Skip additional patterns
export DSP_SKIP_PATTERNS="*.md,*.txt,*.json,*.yml,*.yaml,*.lock,*.log,*.css"
```

## Hooks

### pre-commit

Runs on every `git commit`. Performs deterministic checks:

- **New/modified files not in DSP** — trackable source files (`.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.go`, `.rs`, `.java`, `.rb`, `.vue`, `.svelte`) that are staged but have no corresponding DSP entity
- **Deleted files still in DSP** — files removed from the repo but still referenced by DSP entities
- **Orphaned entities** — DSP entities with no valid connections to the graph

In `warn` mode (default), issues are printed but the commit proceeds. In `block` mode, the commit is rejected if any errors are found.

### pre-push

Runs on every `git push`. Performs a full graph integrity check:

- **Orphan detection** — entities not connected to any parent
- **Cycle detection** — circular dependency chains in the DSP graph
- **Graph statistics** — summary of entities, relations, and coverage

Pre-push always runs in warning mode and never blocks the push.

## Standalone Scripts

### dsp-check-staged

Deterministic checker that can be run independently (same logic as pre-commit):

```bash
./hooks/dsp-check-staged.sh          # Bash
.\hooks\dsp-check-staged.ps1         # PowerShell
```

### dsp-agent-review

Agent-assisted deep review. Collects git diff, DSP state for affected files, graph stats, and orphans into a review document:

```bash
./hooks/dsp-agent-review.sh          # Bash
.\hooks\dsp-agent-review.ps1         # PowerShell
```

The review document can be sent to an LLM agent (Claude Code, Cursor, Codex) for semantic analysis. The agent checks:

- Whether DSP entities accurately reflect the code changes
- Whether dependencies and relations need updating
- Whether new entities should be created for new abstractions
- Impact analysis on dependent entities

## File Overview

```
hooks/
├── README.md                 # This file
├── pre-commit                # Git pre-commit hook (bash)
├── pre-push                  # Git pre-push hook (bash)
├── install-hooks.sh          # Installer (bash)
├── install-hooks.ps1         # Installer (PowerShell)
├── dsp-agent-review.sh       # Agent-assisted review (bash)
├── dsp-agent-review.ps1      # Agent-assisted review (PowerShell)
├── dsp-check-staged.sh       # Standalone staged check (bash)
└── dsp-check-staged.ps1      # Standalone staged check (PowerShell)
```
