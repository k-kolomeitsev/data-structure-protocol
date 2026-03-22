# Getting Started with DSP

**DSP (Data Structure Protocol)** is graph-based long-term structural memory for AI coding agents. The graph lives under **`.dsp/`** in your repository. The CLI is **`skills/data-structure-protocol/scripts/dsp-cli.py`** (run it from the repo root, or pass a full path to `python`).

This guide takes about **3–5 minutes**. You will install the skill, initialize `.dsp/`, learn how to bootstrap or grow the graph, and use the commands you will rely on every day.

---

## 0. The fastest way: dsp-boilerplate

If you're starting a **new project**, skip manual setup entirely. [**dsp-boilerplate**](https://github.com/k-kolomeitsev/dsp-boilerplate) is a production-ready fullstack starter (NestJS 11 + React 19 + Vite 7 + Docker Compose) with everything pre-configured:

- `.dsp/` graph fully initialized with two roots (backend + frontend)
- `@dsp` UID markers in all source files
- DSP skill installed for Cursor, Claude Code, and Codex
- Cursor rules, Claude Code hooks, AGENTS.md
- Git hooks for DSP consistency
- GitHub Actions CI

```bash
git clone https://github.com/k-kolomeitsev/dsp-boilerplate.git my-project
cd my-project
docker-compose up -d
```

The agent has full structural memory from the first session. You can start building immediately.

If you want to add DSP to an **existing project** or set it up manually, continue below.

---

## 1. Install the DSP Skill

**macOS / Linux (default install):**

```bash
curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh | bash
```

**Windows (PowerShell):**

```powershell
irm https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.ps1 | iex
```

**Specific agent (example: Cursor):**

```bash
curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh | bash -s -- cursor
```

**Codex skill-installer:**

```bash
$skill-installer install https://github.com/k-kolomeitsev/data-structure-protocol/tree/main/skills/data-structure-protocol
```

---

## 2. Initialize DSP

From your **project root** (where you want `.dsp/`):

```bash
python dsp-cli.py --root . init
```

If the CLI is not on `PATH`, use the path to the script, for example:

```bash
python skills/data-structure-protocol/scripts/dsp-cli.py --root . init
```

**What this does:** creates a **`.dsp/`** directory and an **empty graph** ready for entities and import edges. You commit `.dsp/` with your code so the structure is versioned and shareable.

---

## 3. Bootstrap an Existing Project (Brownfield)

For a codebase that already exists, treat bootstrapping as a **depth-first walk** over the import graph:

1. **Identify root entrypoints** — e.g. `src/main.ts`, `src/app.module.ts`, or your framework’s real roots.
2. **Create a root entity** for each entry file:

   ```bash
   python dsp-cli.py --root . create-object "src/main.ts" "Application entrypoint"
   ```

3. **Walk imports depth-first**: for each file you reach, **create an object** (or function) entity so every important node exists in the graph.
4. **Record each import** with a short reason:

   ```bash
   python dsp-cli.py --root . add-import obj-<from-uid> obj-<to-uid> "HTTP routing and request handling"
   ```

5. **Mark public APIs** where one module exports symbols others rely on:

   ```bash
   python dsp-cli.py --root . create-shared obj-<owner-uid> obj-<shared-uid>
   ```

6. **External dependencies** (npm packages, stdlib, generated vendor code): model them as **`kind: external`** and **do not** try to map their full internals:

   ```bash
   python dsp-cli.py --root . create-object "node_modules/some-pkg/index.js" "HTTP client library" --kind external
   ```

**Trade-off (honest):** bootstrapping a large repo is **upfront work**. The payoff is **lower token usage** (agents find structure without re-reading everything), **faster discovery** of relevant files, and **safer refactors** because dependency direction and public surface are explicit.

**Greenfield projects:** you do not need a big-bang bootstrap. **Register entities as you create files and imports**; the graph stays cheap to maintain.

---

## 4. Navigate the Graph

| Goal | Example |
|------|---------|
| Find by keyword in descriptions / metadata | `python dsp-cli.py --root . search "authentication"` |
| Find entity for a file | `python dsp-cli.py --root . find-by-source "src/auth/index.ts"` |
| Inspect one entity | `python dsp-cli.py --root . get-entity obj-a1b2c3d4` |
| Downward dependency tree (what this imports) | `python dsp-cli.py --root . get-children obj-a1b2c3d4 --depth 2` |
| Table of contents from a root | `python dsp-cli.py --root . read-toc --toc obj-<root-uid>` |

Use **`find-by-source`** after you know a path; use **`search`** when you only have a concept or feature name.

---

## 5. Update DSP as You Code

Keep the graph aligned with the repo as you change code:

| Change | DSP action |
|--------|------------|
| **New file** | `create-object` (or `create-function`) and **`add-import`** for each new edge |
| **New public function / exported API** | `create-function`, then **`create-shared`** from the owning module, and add an **`@dsp`** marker in source if your workflow uses it |
| **New import** | `add-import <importer-uid> <imported-uid> "why this dependency exists"` |
| **Delete code** | `remove-entity` / `remove-import` / `remove-shared` as appropriate |
| **Move or rename a file** | `move-entity <uid> "new/path.ts"` |
| **Internal-only edits** (private helpers, same file) | **No DSP update required** |

Example — new import after you already have UIDs from `find-by-source`:

```bash
python dsp-cli.py --root . add-import obj-aaaabbbb obj-ccccdddd "Shared validation schemas for login"
```

---

## 6. Impact Analysis Before Refactoring

Before you change a **public** contract or a widely used module:

- **Who depends on this, transitively?** (walk **up** the import graph)

  ```bash
  python dsp-cli.py --root . get-parents obj-targetuid --depth inf
  ```

- **Who imports this directly?**

  ```bash
  python dsp-cli.py --root . get-recipients obj-targetuid
  ```

Review **all consumers** surfaced by these commands before renaming exports, changing signatures, or deleting shared entities.

---

## 7. Set Up Git Hooks (Optional)

Optional automation around `.dsp/`:

- **Pre-commit:** compares **new / deleted files** in the index against the graph so obvious drift is caught early.
- **Pre-push:** runs **full graph checks** (e.g. orphans, cycles) before the change leaves your machine.
- **Agent-assisted review:** deeper LLM-powered analysis can sit alongside these checks in your workflow (see hook README in-repo).

**Install (Unix-like):**

```bash
./hooks/install-hooks.sh
```

On Windows, use **`hooks/install-hooks.ps1`** if you use the PowerShell installer path, or run the shell script from Git Bash / WSL.

---

## 8. What’s Next

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — full protocol and storage model
- **[docs/workflows/brownfield.md](docs/workflows/brownfield.md)** — detailed brownfield workflow
- **[docs/workflows/greenfield.md](docs/workflows/greenfield.md)** — detailed greenfield workflow
- **[docs/comparisons/](docs/comparisons/)** — DSP vs GSD, DSP vs Superpowers, and related notes
- **[integrations/](integrations/)** — Claude Code, Cursor, Codex integration packs

---

---

## Tip: study the boilerplate

Even if you're adding DSP to an existing project, [**dsp-boilerplate**](https://github.com/k-kolomeitsev/dsp-boilerplate) is a great reference to see how a properly bootstrapped DSP graph looks in practice — entity structure, `@dsp` markers in code, import edges with `why`, multi-root TOCs, and integration configs for all agents.

---

*You now have DSP initialized, a mental model for brownfield vs greenfield, and the commands to navigate, update, and analyze impact. Run `python dsp-cli.py --root . get-stats` anytime to see how your graph is growing.*
