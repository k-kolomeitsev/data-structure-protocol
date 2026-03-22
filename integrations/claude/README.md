# Claude Code Integration Pack for DSP

Integration pack that connects [Data Structure Protocol](https://github.com/k-kolomeitsev/data-structure-protocol) with Claude Code via hooks and agent guidance.

## What's Included

| File | Purpose |
|---|---|
| `.claude/settings.json` | Hook configuration for SessionStart, PreToolUse, PostToolUse, SessionEnd |
| `hooks/dsp-session-start.sh` | Loads DSP summary at session start |
| `hooks/dsp-pre-write-check.sh` | Warns if a file being written isn't tracked in DSP |
| `hooks/dsp-track-write.sh` | Records written files for later sync |
| `hooks/dsp-session-end-check.sh` | Reminds to sync DSP before session ends |
| `AGENTS.md` | Standalone agent guidance (works without hooks) |
| `examples/` | Brownfield and greenfield workflow walkthroughs |

## Installation

### Full install (recommended)

Copy the `.claude/` directory and hooks to your project root:

```bash
# From the DSP repository
cp -r integrations/claude/.claude /path/to/your-project/
cp -r integrations/claude/hooks /path/to/your-project/.claude/

# Make hooks executable
chmod +x /path/to/your-project/.claude/hooks/dsp-*.sh
```

### Selective install

Pick only the hooks you need:

```bash
# Just session start/end (minimal awareness)
cp integrations/claude/hooks/dsp-session-start.sh /path/to/your-project/.claude/hooks/
cp integrations/claude/hooks/dsp-session-end-check.sh /path/to/your-project/.claude/hooks/
chmod +x /path/to/your-project/.claude/hooks/dsp-*.sh
```

Then add the corresponding entries to your `.claude/settings.json` — see the included `settings.json` for the full configuration.

### AGENTS.md only (zero config)

If you don't want hooks, copy `AGENTS.md` to your project root. Claude Code reads it automatically:

```bash
cp integrations/claude/AGENTS.md /path/to/your-project/AGENTS.md
```

## How Hooks Work

Claude Code hooks fire at specific lifecycle events. All DSP hooks are **non-blocking** (exit 0) and produce only stdout/stderr guidance for the agent.

```
Session Start ──→ dsp-session-start.sh ──→ prints DSP stats summary
       │
       ▼
  Agent works...
       │
  PreToolUse(Write/Edit) ──→ dsp-pre-write-check.sh ──→ warns if file untracked
       │
  PostToolUse(Write/Edit) ──→ dsp-track-write.sh ──→ records file to .dsp-touched
       │
       ▼
Session End ──→ dsp-session-end-check.sh ──→ reminds to sync, cleans up
```

## Requirements

- DSP skill installed (`.dsp/` directory initialized in your project)
- `python3` available in PATH
- `dsp-cli.py` discoverable (auto-detected from common locations)

## Hook Design Principles

- **Fast**: No network calls, no LLM invocations, pure filesystem operations
- **Deterministic**: Same input always produces the same output
- **Non-blocking**: Always exit 0 — hooks advise, never block
- **Auto-detect CLI**: Hooks search common paths for `dsp-cli.py` automatically
