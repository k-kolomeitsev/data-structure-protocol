# Data Structure Protocol (DSP)
**Graph-based long-term structural memory for LLM coding agents.**

DSP externalizes your codebase “map” into a small, versionable graph stored in `.dsp/`: entities (modules/functions/external deps), dependencies (imports), public API (shared/exports), and **reasons** for every connection (`why`).

This repository ships:
- **The DSP architecture/spec**: [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- **A long-form introduction article**: [`article.md`](./article.md)
- **A ready-to-use agent skill** (kept in repo root for universal installation): [`skills/data-structure-protocol`](./skills/data-structure-protocol)
  - `SKILL.md` (agent instructions)
  - `scripts/dsp-cli.py` (reference CLI)
  - `references/` (storage format, operations, bootstrap procedure)

---

## Why DSP (the problem it solves)

Anyone who works with agents recognizes the pattern: **the first 5–15 minutes are spent not on the task, but on “getting oriented.”**

- Where is the entry point?
- What depends on what (and *why*)?
- What is actually public API vs internal details?
- Which modules/resources/configs are silently coupled?

On small projects this is annoying. On large ones it becomes a constant tax on tokens and attention.

DSP reduces that tax by letting agents:
- **Navigate structure without loading the whole repo into the context window**
- **Find dependencies, consumers, and “why” quickly**
- **Avoid context loss between tasks** (DSP is external, persistent memory)

> **Honest trade-off:** bootstrapping DSP for a large project is expensive (time, attention, often tokens).  
> It typically pays off over the lifetime of the project through lower token usage, faster dependency discovery, and more reliable agent execution.

---

## What DSP is (and what it is not)

**DSP is NOT human-facing documentation and NOT an AST dump.**  
It captures:
- **Meaning**: why an entity exists (`purpose`)
- **Boundaries**: what it imports / exposes (`imports`, `shared`)
- **Reasons**: why connections exist (`exports/` reverse index)

DSP works with any codebase and artifact system (TS/JS, Python, Go, infra, SQL, assets, configs, etc.).

---

## How it works (mental model)

```
┌──────────────────────┐
│      Codebase        │
│  (files + assets)    │
└──────────┬───────────┘
           │  create/update graph as you work
           ▼
┌──────────────────────┐
│   DSP Builder / CLI   │
│   (dsp-cli.py)        │
└──────────┬───────────┘
           │  writes
           ▼
┌──────────────────────┐
│        .dsp/          │
│ entity graph + whys   │
└──────────┬───────────┘
           │  reads/searches/traverses
           ▼
┌──────────────────────┐
│     LLM Orchestrator  │
│ (your agent + skill)  │
└──────────────────────┘
```

---

## Core concepts (the minimal vocabulary)

- **Entity**: a node in the graph. Two base kinds:
  - **Object**: any “thing” that isn’t a function (module/file/class/config/resource/external dependency).
  - **Function**: function/method/handler/pipeline.
- **UID identity**: entities are identified by stable UIDs (`obj-<8hex>`, `func-<8hex>`). File paths are attributes, not identity.
- **`imports`**: outgoing edges — what this entity uses.
- **`shared`**: public API of an object — what it exposes.
- **`exports/` reverse index**: incoming edges — **who imports this entity and why**.
- **TOC**: a per-entrypoint table of contents listing all reachable entities from that root (`.dsp/TOC` or `.dsp/TOC-<rootUid>`).

### UID markers in source code

For entities *inside* a file (exported functions/classes/etc.), DSP anchors identity with a comment marker:

```ts
// @dsp func-7f3a9c12
export function calculateTotal(items: Item[]): number { /* ... */ }
```

```python
# @dsp func-3c19ab8e
def process_payment(order):
    ...
```

This stays stable across formatting, line shifts, and refactors.

---

## Storage format (`.dsp/`)

DSP is intentionally simple: **plain text files** in a deterministic directory layout.

```text
.dsp/
├── TOC                     # Table of contents (single root)
├── TOC-<rootUid>           # One TOC per root (multi-root projects)
├── obj-a1b2c3d4/           # Object entity
│   ├── description         # source, kind, purpose (+ optional freeform sections)
│   ├── imports             # imported UIDs (one per line)
│   ├── shared              # exported/shared UIDs (one per line)
│   └── exports/            # reverse index: who imports this entity and why
│       ├── <importer_uid>  # why the whole object is imported
│       └── <shared_uid>/   # per shared entity
│           ├── description # what is exported (auto-filled from shared's purpose)
│           └── <importer_uid>  # why this shared is imported
└── func-7f3a9c12/          # Function entity
    ├── description
    ├── imports
    └── exports/
        └── <owner_uid>     # ownership link (function belongs to object)
```

The full specification is in [`ARCHITECTURE.md`](./ARCHITECTURE.md) and summarized in:
- [`skills/data-structure-protocol/references/storage-format.md`](./skills/data-structure-protocol/references/storage-format.md)

---

## Bootstrap (initial mapping) — expensive, but foundational

Bootstrap is a DFS traversal from root entrypoint(s). For each root:
- Create a dedicated TOC file.
- Document the root entity first.
- Walk local (non-external) imports depth-first, documenting every reachable file/artifact.
- Record externals as `kind: external`, but **do not descend** into dependency internals (`node_modules`, `site-packages`, etc.).

See:
- [`skills/data-structure-protocol/references/bootstrap.md`](./skills/data-structure-protocol/references/bootstrap.md)

### Cost vs ROI (no sugar-coating)

Bootstrapping a large repo can be its own mini-project:
- Multiple roots / monorepos
- Many transitive imports
- Discipline needed to write minimal-but-accurate `purpose`
- Discipline needed to write `why` for edges (this is where a lot of value lives)

It typically pays back via:
- Lower token usage per task (less “orientation”)
- Faster discovery of dependencies/consumers
- Less context loss between tasks
- Safer, more predictable refactors (impact analysis is cheap)

---

## The `data-structure-protocol` skill

The skill is a compact package that teaches agents how to:
- Navigate `.dsp` before touching code (search/find-by-source/read-toc)
- Update DSP while writing code (create-object/create-function/create-shared/add-import)
- Keep the graph consistent while deleting/moving code (remove-*/move-entity)
- Avoid busywork (don’t touch DSP for internal-only changes)

Skill location in this repo (universal layout):
- `skills/data-structure-protocol/SKILL.md`
- `skills/data-structure-protocol/scripts/dsp-cli.py`
- `skills/data-structure-protocol/references/*`

---

## Installation

This repository keeps skills in `skills/` so you can install them into whichever assistant you use.

### Cursor (recommended)

Copy the skill into your project’s `.cursor/skills/`:

```powershell
New-Item -ItemType Directory -Force .\.cursor\skills | Out-Null
Copy-Item -Recurse -Force .\skills\data-structure-protocol .\.cursor\skills\data-structure-protocol
```

`skills/` is the universal, repo-friendly location. `.cursor/skills/` is just Cursor’s installation target so the skill can be discovered/activated by Cursor.

### Other assistants (generic)

If your assistant supports “skills” via a folder convention, copy `skills/data-structure-protocol` into the appropriate directory for that tool (for example: `.claude/skills/`, `.continue/skills/`, etc.).

The skill is plain Markdown + supporting files, so installation is typically just “copy the folder”.

---

## Prerequisites

- **Python 3.10+** (the CLI uses modern type syntax like `str | None`)

---

## Quick start

### 0) Point to the CLI

The CLI is shipped with the skill. Pick the path you want to use:

```powershell
# If your repo keeps skills in the universal root location:
$DSP_CLI = ".\skills\data-structure-protocol\scripts\dsp-cli.py"

# If you prefer running the copy installed into Cursor’s skill folder:
# $DSP_CLI = ".\.cursor\skills\data-structure-protocol\scripts\dsp-cli.py"
```

### 1) Initialize `.dsp/`

```powershell
python $DSP_CLI --root . init
```

### 2) Create entities and edges (as you work)

```powershell
# Create a module/file entity
python $DSP_CLI --root . create-object "src/app.ts" "Main application entrypoint"

# Create an exported function entity (owner = module UID)
python $DSP_CLI --root . create-function "src/app.ts#start" "Starts the HTTP server" --owner obj-a1b2c3d4

# Mark exports (public API)
python $DSP_CLI --root . create-shared obj-a1b2c3d4 func-7f3a9c12

# Record imports with a reason (why)
python $DSP_CLI --root . add-import obj-a1b2c3d4 obj-deadbeef "HTTP routing"
```

### 3) Navigate the graph (instead of guessing)

```powershell
# Search by meaning/keywords
python $DSP_CLI --root . search "authentication"

# Find entities by source file path
python $DSP_CLI --root . find-by-source "src/auth/index.ts"

# Inspect one entity
python $DSP_CLI --root . get-entity obj-a1b2c3d4

# Downward dependency tree
python $DSP_CLI --root . get-children obj-a1b2c3d4 --depth 2

# Upward dependency tree / impact analysis
python $DSP_CLI --root . get-parents obj-a1b2c3d4 --depth inf
python $DSP_CLI --root . get-recipients obj-a1b2c3d4
```

---

## Agent prompt (copy/paste)

Use this snippet as a “system/user” preface when you want an agent to respect DSP:

> **This project uses DSP (Data Structure Protocol).**  
> The `.dsp/` directory is the entity graph of this project: modules, functions, dependencies, public API. It is your long-term memory of the code structure.  
>  
> **Rules:**  
> - Before changing code: locate affected entities via `search`, `find-by-source`, or `read-toc`, then read `description`/`imports`.  
> - When creating modules/functions/exports/imports: register them with DSP immediately (`create-object`, `create-function`, `create-shared`, `add-import` with `why`).  
> - When moving/deleting: use `move-entity` / `remove-*` to keep the graph consistent.  
> - Do not update DSP for internal-only changes that don’t affect purpose/dependencies.  

---

## Operations reference

The CLI operations are intentionally aligned with the architecture specification.

- Spec: [`ARCHITECTURE.md` §5](./ARCHITECTURE.md)
- CLI reference: [`skills/data-structure-protocol/references/operations.md`](./skills/data-structure-protocol/references/operations.md)

Key commands (non-exhaustive):
- Create: `init`, `create-object`, `create-function`, `create-shared`, `add-import`
- Update: `update-description`, `update-import-why`, `move-entity`
- Delete: `remove-import`, `remove-shared`, `remove-entity`
- Read/traverse: `get-entity`, `get-children`, `get-parents`, `get-path`, `read-toc`
- Diagnostics: `detect-cycles`, `get-orphans`, `get-stats`

---

## Recommended workflow (to keep DSP healthy)

DSP stays valuable only if it stays:
- **Small** (minimal sufficient context, controlled granularity)
- **Accurate** (imports/shared/whys reflect reality)
- **Maintained as you code** (not as a periodic “documentation sprint”)

Rules of thumb:
- Add UIDs for **file-level Objects** and **public/shared entities**.
- Track every import edge that matters, and always include **`why`**.
- Treat `.dsp/` as a first-class artifact: review diffs, keep it consistent.

---

## Contributing

Contributions that improve:
- The architecture spec (`ARCHITECTURE.md`)
- The skill instructions (`skills/data-structure-protocol/SKILL.md`)
- The CLI behavior (keeping it aligned with the spec)
- Reference docs/examples

…are welcome. Please keep changes minimal, explicit, and consistent with the “minimal sufficient context” philosophy.

---

## License

This project is licensed under the **Apache License 2.0**. See [`LICENSE`](./LICENSE).

