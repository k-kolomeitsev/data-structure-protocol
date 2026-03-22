[![GitHub stars](https://img.shields.io/github/stars/k-kolomeitsev/data-structure-protocol?style=social)](https://github.com/k-kolomeitsev/data-structure-protocol)
[![License](https://img.shields.io/github/license/k-kolomeitsev/data-structure-protocol)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-green)]()
[![Cursor](https://img.shields.io/badge/Cursor-supported-green)]()
[![Codex](https://img.shields.io/badge/Codex-supported-green)]()

# Data Structure Protocol (DSP)

**The missing memory layer for AI-assisted development**

---

## The problem

Your agent re-reads the same codebase every session. **DSP fixes that.**

Every time you start a new task, your AI coding agent spends the first 5–15 minutes "getting oriented" — scanning files, tracing imports, figuring out what depends on what. On large projects this becomes a constant tax on tokens and attention. Context is rebuilt from scratch, every single time.

DSP is a graph-based long-term structural memory stored in `.dsp/`. It gives agents a persistent, versionable map of your codebase — entities, dependencies, public APIs, and the *reasons* behind every connection — so they can pick up exactly where they left off.

> **DSP is not another workflow framework.** It's the persistent structural memory layer that's missing from every AI coding workflow.

---

## Install

**macOS / Linux:**

```bash
curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh | bash
```

**Windows:**

```powershell
irm https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.ps1 | iex
```

**Codex:**

```
$skill-installer install https://github.com/k-kolomeitsev/data-structure-protocol/tree/main/skills/data-structure-protocol
```

---

## What you get

- **Agent stops re-learning your project every session** — structural context persists across tasks, sessions, and even team members
- **Dependency discovery in seconds, not minutes** — graph traversal replaces full-repo scanning
- **Impact analysis before refactors** — know what breaks before you touch it
- **Safer changes on brownfield codebases** — hidden couplings become visible edges in the graph
- **Works with Claude Code, Cursor, Codex — no lock-in** — DSP is an agent skill, not a platform
- **Git-native and versionable** — `.dsp/` is plain text, diffs cleanly, reviews like code

> **Honest trade-off:** bootstrapping DSP on a large project takes real effort (time, tokens, discipline). It pays back over the project lifetime through lower per-task token usage, faster discovery, and more predictable agent behavior.

---

## How it works

```
┌──────────────────────┐
│      Codebase        │
│  (files + assets)    │
└──────────┬───────────┘
           │  create/update graph as you work
           ▼
┌──────────────────────┐
│   DSP Builder / CLI  │
│   (dsp-cli.py)       │
└──────────┬───────────┘
           │  writes
           ▼
┌──────────────────────┐
│        .dsp/         │
│ entity graph + whys  │
└──────────┬───────────┘
           │  reads/searches/traverses
           ▼
┌──────────────────────┐
│   LLM Orchestrator   │
│ (your agent + skill) │
└──────────────────────┘
```

As you work, DSP builds a lightweight graph of your codebase: modules, functions, dependencies, and public APIs. Each connection carries a `why` — the reason it exists. Your agent reads this graph instead of re-scanning the repo, navigates structure through graph traversal, and keeps the graph updated as code evolves.

The graph lives in `.dsp/` — plain text files that commit, diff, and merge like any other source artifact.

---

## Quick start

### Option A: Start from the boilerplate (fastest)

[**dsp-boilerplate**](https://github.com/k-kolomeitsev/dsp-boilerplate) is a production-ready fullstack starter — **NestJS 11 + React 19 + Vite 7** in Docker Compose, with a **fully initialized DSP graph**, pre-configured skills for all agents, Cursor rules, git hooks, and CI.

```bash
git clone https://github.com/k-kolomeitsev/dsp-boilerplate.git my-project
cd my-project
docker-compose up -d
```

Everything is wired: `.dsp/` graph with two roots (backend + frontend), `@dsp` markers in all source files, DSP skills for Cursor, Claude Code, and Codex. You can start coding and the agent already knows the entire project structure.

### Option B: Add DSP to any project

#### 1. Initialize

```bash
python dsp-cli.py --root . init
```

#### 2. Create entities

```bash
python dsp-cli.py --root . create-object "src/app.ts" "Main application entrypoint"
# → obj-a1b2c3d4

python dsp-cli.py --root . create-function "src/app.ts#start" "Starts the HTTP server" --owner obj-a1b2c3d4
# → func-7f3a9c12

python dsp-cli.py --root . add-import obj-a1b2c3d4 obj-deadbeef "HTTP routing"
```

#### 3. Navigate

```bash
python dsp-cli.py --root . search "authentication"
python dsp-cli.py --root . find-by-source "src/auth/index.ts"
python dsp-cli.py --root . get-children obj-a1b2c3d4 --depth 2
```

#### 4. Impact analysis

```bash
python dsp-cli.py --root . get-parents obj-a1b2c3d4 --depth inf
python dsp-cli.py --root . get-recipients obj-a1b2c3d4
```

> Before any refactor, run `get-parents` or `get-recipients` to see everything that depends on the entity you're about to change.

---

## Supported agents

DSP installs as a skill for your agent. Pick your agent and scope.

Don't have a coding agent yet? Install one first:

| Agent | Install |
|---|---|
| **Claude Code** | `npm i -g @anthropic-ai/claude-code` — [docs](https://docs.anthropic.com/en/docs/claude-code/setup) |
| **Cursor** | [cursor.com/downloads](https://www.cursor.com/downloads) — [docs](https://docs.cursor.com) |
| **Codex CLI** | `npm i -g @openai/codex` — [docs](https://developers.openai.com/codex/cli) \| [github](https://github.com/openai/codex) |

### macOS / Linux

| Agent | Project Install | Global Install |
|---|---|---|
| **Cursor** | `curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh \| bash -s -- cursor` | `curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh \| bash -s -- --global cursor` |
| **Claude Code** | `curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh \| bash -s -- claude` | `curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh \| bash -s -- --global claude` |
| **Codex** | `curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh \| bash -s -- codex` | `curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh \| bash -s -- --global codex` |

### Windows

```powershell
# Project-level (current directory)
irm https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.ps1 | iex

# With specific agent
powershell -ExecutionPolicy Bypass -File install.ps1 -Agent cursor
powershell -ExecutionPolicy Bypass -File install.ps1 -Agent claude
powershell -ExecutionPolicy Bypass -File install.ps1 -Agent codex

# Global (user-level)
powershell -ExecutionPolicy Bypass -File install.ps1 -Agent cursor -Global
```

### Codex (alternative)

```
$skill-installer install https://github.com/k-kolomeitsev/data-structure-protocol/tree/main/skills/data-structure-protocol
```

> **Project install** puts the skill in your repo (`.cursor/skills/`, `.claude/skills/`, `.codex/skills/`).
> **Global install** puts it in your home directory so it's available across all projects.

---

## DSP vs alternatives

Modern agents already know how to plan, write tests, verify, and ship. They don't need process wrappers. What they lack is **memory**.

| | **DSP** | **GSD** | **Superpowers** |
|---|---|---|---|
| **Core idea** | Persistent structural memory | Process/confidence wrapper | Engineering discipline (TDD) |
| **What it solves** | Agent has no memory of project between sessions | Agent doesn't follow structured workflow | Agent might skip tests/planning |
| **Is the problem real?** | Yes — no model has built-in project memory | Diminishing — modern models plan and verify natively | Diminishing — modern models know TDD when prompted |
| **Persistent memory** | Full graph across sessions | None | None |
| **Impact analysis** | Built-in (graph traversal) | No | No |
| **Brownfield** | First-class | One-time scan | No explicit support |
| **Overhead** | Low | Medium | Medium |

> Modern agents are smarter than most mid-level engineers. They plan, they test, they verify. They just can't remember your project. DSP is the fix. [Detailed comparison with GSD](./docs/comparisons/dsp-vs-gsd.md) | [Detailed comparison with Superpowers](./docs/comparisons/dsp-vs-superpowers.md)

---

## Core concepts

| Concept | What it is |
|---|---|
| **Entity** | A node in the graph. Either an **Object** (module/file/class/config/external dep) or a **Function** (function/method/handler) |
| **UID** | Stable identifier (`obj-<8hex>`, `func-<8hex>`). File paths are attributes, not identity — entities survive renames and moves |
| **imports** | Outgoing edges — what this entity uses, with a `why` for each connection |
| **shared** | Public API of an object — what it exposes to consumers |
| **exports/** | Reverse index — who imports this entity and why (incoming edges) |
| **TOC** | Per-entrypoint table of contents listing all reachable entities from a root |

UID markers anchor identity in source code:

```ts
// @dsp func-7f3a9c12
export function calculateTotal(items: Item[]): number { /* ... */ }
```

```python
# @dsp func-3c19ab8e
def process_payment(order):
    ...
```

---

## Storage format

`.dsp/` is plain text in a deterministic directory layout:

```
.dsp/
├── TOC                        # Table of contents (single root)
├── TOC-<rootUid>              # One TOC per root (multi-root projects)
├── obj-a1b2c3d4/              # Object entity
│   ├── description            # source, kind, purpose
│   ├── imports                # imported UIDs (one per line)
│   ├── shared                 # exported/shared UIDs (one per line)
│   └── exports/               # reverse index
│       ├── <importer_uid>     # why the whole object is imported
│       └── <shared_uid>/      # per shared entity
│           ├── description    # what is exported
│           └── <importer_uid> # why this shared is imported
└── func-7f3a9c12/             # Function entity
    ├── description
    ├── imports
    └── exports/
        └── <owner_uid>        # ownership link
```

Full specification: [`ARCHITECTURE.md`](./ARCHITECTURE.md)

---

## Git hooks & CI

DSP ships with hooks that keep the graph in sync with your code:

| Hook | What it does | LLM required |
|---|---|---|
| **pre-commit** | Checks staged files against DSP graph — flags new files without entities, deleted files still referenced, orphans | No |
| **pre-push** | Full graph integrity — orphan detection, cycle detection, stats summary | No |
| **Agent-assisted review** | Deep semantic analysis of changes against DSP entities, dependency impact | Yes |

Install hooks:

```bash
./hooks/install-hooks.sh          # macOS/Linux
.\hooks\install-hooks.ps1         # Windows
```

See [`hooks/`](./hooks/) for configuration, standalone scripts, and GitHub Actions integration.

---

## Integration packs

Ready-made configurations for each supported agent:

| Agent | Skill location |
|---|---|
| **Cursor** | `.cursor/skills/data-structure-protocol/` |
| **Claude Code** | `.claude/skills/data-structure-protocol/` |
| **Codex** | `.codex/skills/data-structure-protocol/` |

Each integration includes the skill instructions (`SKILL.md`), CLI (`dsp-cli.py`), and reference docs. See [`integrations/`](./integrations/) for agent-specific setup guides.

---

## Documentation

| Document | Description |
|---|---|
| [**dsp-boilerplate**](https://github.com/k-kolomeitsev/dsp-boilerplate) | Fullstack boilerplate (NestJS + React + Docker Compose) with DSP pre-initialized — the fastest way to start |
| [**GETTING_STARTED.md**](./GETTING_STARTED.md) | Step-by-step guide from install to first impact analysis |
| [**ARCHITECTURE.md**](./ARCHITECTURE.md) | Full protocol specification — entity model, storage format, operations |
| [**docs/comparisons/**](./docs/comparisons/) | Detailed comparisons with GSD, Superpowers, and other tools |
| [**docs/workflows/**](./docs/workflows/) | Workflow guides — bootstrap, brownfield adoption, team usage |
| [**integrations/**](./integrations/) | Agent-specific integration guides and configurations |

---

## Contributing

Contributions are welcome. Areas where help is most valuable:

- **Architecture spec** — improving [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- **CLI** — keeping `dsp-cli.py` aligned with the spec
- **Skill instructions** — refining [`SKILL.md`](./skills/data-structure-protocol/SKILL.md) for agent clarity
- **New integrations** — adding support for more agents and editors
- **Documentation** — examples, workflow guides, comparisons

Please keep changes minimal, explicit, and consistent with the "minimal sufficient context" philosophy.

---

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE).
