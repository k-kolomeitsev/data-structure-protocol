# Codex Integration Pack for DSP

Integration pack that connects [Data Structure Protocol](https://github.com/k-kolomeitsev/data-structure-protocol) with OpenAI Codex.

## How Codex Discovers DSP

Codex automatically discovers skills from `.codex/skills/`. When the DSP skill is installed, Codex reads the `SKILL.md` file and gains access to `dsp-cli.py` for structural memory operations.

## Installation

### Via install script (recommended)

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh | bash -s -- codex

# Windows (PowerShell)
irm https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.ps1 | iex
```

### Via Codex skill-installer

If you have the Codex skill-installer available:

```
$skill-installer install https://github.com/k-kolomeitsev/data-structure-protocol/tree/main/skills/data-structure-protocol
```

### Manual installation

```bash
# Clone the repository
git clone https://github.com/k-kolomeitsev/data-structure-protocol.git /tmp/dsp

# Copy the skill
mkdir -p .codex/skills/data-structure-protocol
cp -r /tmp/dsp/skills/data-structure-protocol/* .codex/skills/data-structure-protocol/

# Clean up
rm -rf /tmp/dsp
```

## What's Included

| File | Purpose |
|---|---|
| `AGENTS.md` | Standalone agent guidance — works with any agent, including Codex |
| `examples/brownfield-workflow.md` | Step-by-step workflow for existing projects |
| `examples/greenfield-workflow.md` | Step-by-step workflow for new projects |

## Additional Setup

### AGENTS.md (optional fallback)

Copy `AGENTS.md` to your project root for guidance that works even without the DSP skill installed:

```bash
cp integrations/codex/AGENTS.md /path/to/your-project/AGENTS.md
```

### Initialize DSP

After installing the skill, initialize DSP in your project:

```bash
dsp-cli init
```

## Requirements

- Codex with skill support (`.codex/skills/` discovery)
- `python3` available in PATH
- DSP initialized (`.dsp/` directory) in your project
