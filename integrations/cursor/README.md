# Cursor Integration Pack for DSP

Integration pack that connects [Data Structure Protocol](https://github.com/k-kolomeitsev/data-structure-protocol) with Cursor via rules (.mdc files) and optional hooks.

## What's Included

| File | Type | Purpose |
|---|---|---|
| `.cursor/rules/dsp-core.mdc` | Always active | Core DSP awareness — read before modify, update after changes |
| `.cursor/rules/dsp-brownfield.mdc` | Manual trigger | Brownfield workflow guide for existing projects |
| `.cursor/rules/dsp-new-file.mdc` | Auto on new files | Register new source files in DSP |
| `.cursor/rules/dsp-refactor-safety.mdc` | Manual trigger | Impact analysis before refactoring |
| `.cursor/rules/dsp-public-api-changes.mdc` | Manual trigger | Update shared/exports on public API changes |
| `.cursor/rules/dsp-when-not-to-update.mdc` | Always active | Skip DSP for internal-only changes |
| `AGENTS.md` | Standalone guidance | Works without rules for any agent |
| `examples/` | Walkthroughs | Brownfield and greenfield workflow examples |

## Installation

### Full install (recommended)

Copy the `.cursor/rules/` directory to your project:

```bash
# From the DSP repository
cp -r integrations/cursor/.cursor/rules/ /path/to/your-project/.cursor/rules/
```

Or on Windows (PowerShell):

```powershell
Copy-Item -Recurse integrations\cursor\.cursor\rules\ \path\to\your-project\.cursor\rules\
```

If you already have `.cursor/rules/`, the DSP rule files won't conflict — they use the `dsp-` prefix.

### Selective install

Copy only the rules you need. At minimum, install these two:

- `dsp-core.mdc` — core awareness (always active)
- `dsp-when-not-to-update.mdc` — prevents unnecessary DSP updates

### AGENTS.md only (zero config)

Copy `AGENTS.md` to your project root for lightweight agent guidance:

```bash
cp integrations/cursor/AGENTS.md /path/to/your-project/AGENTS.md
```

## Hooks via Third-Party Hooks

Cursor supports Claude Code hooks through the **Third-party hooks** feature. This means the Claude integration hooks work in Cursor too.

### Enabling Third-Party Hooks

1. Open Cursor Settings
2. Go to **Features**
3. Enable **Third-party hooks**
4. Copy `.claude/settings.json` from the Claude integration pack to your project

```bash
cp -r integrations/claude/.claude /path/to/your-project/
cp -r integrations/claude/hooks /path/to/your-project/.claude/
chmod +x /path/to/your-project/.claude/hooks/dsp-*.sh
```

This gives you the same hook-based DSP awareness as Claude Code — session start summary, write tracking, and session end reminders.

## How Rules Work

Cursor rules provide contextual guidance to the AI agent:

- **Always active** rules are injected into every conversation
- **Auto-trigger** rules activate when matching files are created or edited
- **Manual trigger** rules are available for the agent to reference when relevant

The DSP rules teach the agent to consult `.dsp/` before making changes and to keep the graph up to date after changes.

## Requirements

- DSP skill installed (`.dsp/` directory initialized in your project)
- `python3` available in PATH (or `python` on Windows)
- `dsp-cli.py` discoverable from a standard skill location
