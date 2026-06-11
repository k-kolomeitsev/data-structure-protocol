# Brownfield Workflow: Adding DSP to an Existing Project

A step-by-step guide for bootstrapping DSP on an existing codebase — the use case where DSP provides the most value.

## Prerequisites

- Python 3.10+
- An existing project with source code
- An AI coding agent (Claude Code, Cursor, or Codex)

## 1. Install the DSP skill

Choose your agent and run the one-liner:

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.sh | bash -s -- cursor
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/k-kolomeitsev/data-structure-protocol/main/install.ps1 | iex
```

**Codex (via skill-installer):**
```
$skill-installer install https://github.com/k-kolomeitsev/data-structure-protocol/tree/main/skills/data-structure-protocol
```
> `$skill-installer` is a Codex skill invocation — type it inside a Codex CLI session, not in your shell.

This installs the skill (SKILL.md + dsp-cli.py + references) into the appropriate directory for your agent.

## 2. Initialize DSP

```bash
dsp-cli init
# initialized .dsp/
```

This creates the `.dsp/` directory in your project root. Add it to version control — DSP is designed to be git-tracked.

## 3. Identify root entrypoints and their scopes

Before bootstrapping, identify the root entrypoints of your project and the directory zone (**scope**) each one covers. Common patterns:

| Project type | Typical roots | Typical scopes |
|---|---|---|
| Backend API | `src/main.ts`, `src/app.module.ts`, `cmd/server/main.go` | `.` |
| Frontend SPA | `src/main.tsx`, `src/App.tsx`, `pages/_app.tsx` | `.` |
| Fullstack monorepo | One root per package: `backend/src/main.ts`, `frontend/src/main.tsx` | `backend`, `frontend` |
| CLI tool | `src/cli.ts`, `cmd/root.go`, `__main__.py` | `.` |
| Library | `src/index.ts`, `lib/mod.rs`, `__init__.py` | `.` |

Create each root with `--new-root --scope <dir>` — it gets its own `TOC-<uid>` file, and the scope makes TOC assignment automatic for everything indexed afterwards: each new entity lands in every TOC whose root scope covers its path.

## 4. Bootstrap in three waves

This is the most important step. Bootstrap is **three flat passes over the project's file list, executed by parallel subagents over fixed file batches** — not a graph traversal. The core economy rule: **each file is read exactly once, by exactly one subagent**; all three waves run on top of that single read, so the token cost is roughly one pass over the codebase.

```
Phase 0:    discover roots                 →  one TOC per root (--new-root --scope)
Inventory:  list all files + sizes         →  batches per TOC, balanced by volume;
                                              1 batch = 1 subagent
Wave 1:     subagent reads its batch ONCE  →  create-object / create-function
Wave 2:     same subagent, same read       →  create-shared
─────────── barrier: ALL batches done; register externals once ───────────
Wave 3:     same subagent, same read       →  add-import (usage-based why)
```

### Step 4.1: Phase 0 — register the roots

```bash
dsp-cli create-object "src/app.module.ts" \
  "Application root module — bootstraps NestJS app, registers all feature modules and global middleware" \
  --new-root --scope .
# obj-82e23068
```

For a monorepo — one root per package (`--scope backend`, `--scope frontend`, ...). The root's `description` must include a brief project overview.

### Step 4.2: Inventory and batching

Before reading any file content, build the work plan:

```bash
git ls-files | xargs wc -c    # every project file with its size (any equivalent works)
```

Skip vendored code, build output, and lock files. Then:

1. **Group files by TOC** (match paths against the root scopes) — a batch never mixes TOCs.
2. **Split each group into batches of roughly equal total volume** — by content size, not file count, so subagents finish at about the same time. A batch must fit comfortably in one subagent's context.
3. **Dispatch one subagent per batch, in parallel.** Each subagent runs Waves 1–3 below over its own files.

### Step 4.3: Wave 1 — index all files

Each subagent reads each file of its batch **once** — the only read in the entire bootstrap — capturing purpose, inner entities, exports, and imports with their usage sites. Then it registers what it read; TOC membership is resolved automatically from the scopes:

```bash
dsp-cli create-object "src/users/users.module.ts" \
  "Users feature module — user CRUD, authentication, profile management"
# obj-a1b2c3d4

dsp-cli create-object "src/products/products.module.ts" \
  "Products feature module — product catalog, search, and inventory"
# obj-e5f6a7b8
```

Functions and classes worth their own entity are registered in the same pass, with `@dsp` markers placed in source:

```bash
dsp-cli create-function "src/users/users.service.ts#findById" \
  "Finds a user by ID — returns full user entity or throws NotFoundException" \
  --owner obj-a1b2c3d4
# func-c9d0e1f2

dsp-cli create-function "src/users/users.service.ts#validateCredentials" \
  "Validates email/password pair — returns user entity or null" \
  --owner obj-a1b2c3d4
# func-d3e4f5a6
```

Batch interrupted? Re-dispatch it: `dsp-cli find-by-source <path>` — skip files that already have entities.

### Step 4.4: Wave 2 — index all exports

The same subagent continues over the files it already read — **no re-reading**. All UIDs exist after its Wave 1, so this is pure wiring:

```bash
dsp-cli create-shared obj-a1b2c3d4 func-c9d0e1f2 func-d3e4f5a6
```

Exports are batch-local — no waiting on other batches.

### Step 4.5: Barrier — then Wave 3, index all imports

Imports cross batch boundaries, so Wave 3 starts **only after every batch finished Waves 1–2**. At the barrier each subagent reports the external packages its batch imports (known from the Wave 1 read), and the orchestrator registers each external once:

```bash
dsp-cli create-object "@nestjs/core" \
  "NestJS core framework — dependency injection, module system, lifecycle hooks" \
  --kind external --toc obj-82e23068
# obj-aaaa1111

# Another root also uses it? Attach the same entity to that root's TOC:
dsp-cli add-to-toc obj-aaaa1111 --toc obj-f5e6a7b8
```

Then the same subagents record the edges — still without re-reading sources. Imports were verified at the Wave 1 read (dead imports → removed from code, never registered); local targets resolve via `find-by-source`:

```bash
dsp-cli add-import obj-82e23068 obj-a1b2c3d4 \
  "app module imports users module to enable user management endpoints"

# Import of a specific shared function tracks the exporter too
dsp-cli add-import obj-AUTH_SVC func-d3e4f5a6 \
  "auth service uses validateCredentials to verify login attempts" \
  --exporter obj-a1b2c3d4

dsp-cli add-import obj-82e23068 obj-aaaa1111 \
  "app module uses NestJS core for module bootstrapping and DI container"
```

### Step 4.6: Verify

```bash
dsp-cli get-stats        # totals: entities, imports, shared, cycles, orphans
dsp-cli get-orphans      # unreferenced files — expected for scripts/configs; review the rest
dsp-cli detect-cycles    # circular dependencies
```

Every file from the inventory must resolve via `find-by-source`.

### Bootstrap tips

- **One read per file.** Everything the waves need (purpose, entities, exports, import usage) is captured at the Wave 1 read; Waves 2–3 never re-open sources.
- **Waves, not traversal.** Don't follow imports recursively — `add-import` never fails on a missing UID because all entities exist before Wave 3.
- **Balance batches by volume, not file count** — equal-sized batches mean no subagent idles at the barrier.
- **Re-indexing a previously mapped project?** If source files still carry `@dsp <uid>` markers, collect them with grep and pass `--uid <old-uid>` at every create step — identities survive the rebuild.
- **The agent should do this, not you.** Give the agent the DSP skill instructions and ask it to "bootstrap DSP for this project".

## 5. Daily workflow: navigate → code → update DSP

Once bootstrapped, the daily cycle is:

### Before making changes — navigate

```bash
# Find the entity you need to modify
dsp-cli search "payment"
# obj-p1a2y3m4  [purpose] Payment processing service

dsp-cli find-by-source "src/services/payment.service.ts"
# obj-p1a2y3m4

# Understand its context
dsp-cli get-entity obj-p1a2y3m4
# Shows: source, purpose, imports, shared exports, who depends on it

# See its dependency tree
dsp-cli get-children obj-p1a2y3m4 --depth 2
# Payment service → [Stripe SDK, DB service, Config service]
```

### While coding — work normally

Write code as usual. DSP doesn't interfere with your coding flow.

### After changes — update DSP

```bash
# New file created? Register it.
dsp-cli create-object "src/services/refund.service.ts" \
  "Refund processing — handles partial and full refunds via Stripe"
# obj-r1e2f3u4

# New import added? Track it.
dsp-cli add-import obj-r1e2f3u4 obj-p1a2y3m4 \
  "refund service uses payment service to look up original charges"

# New public function? Register and share.
dsp-cli create-function "src/services/refund.service.ts#processRefund" \
  "Processes a refund request — validates amount, calls Stripe, updates order" \
  --owner obj-r1e2f3u4
# func-n5e6w7f8
dsp-cli create-shared obj-r1e2f3u4 func-n5e6w7f8

# File moved/renamed? Update the source.
dsp-cli move-entity obj-p1a2y3m4 "src/payments/payment.service.ts"

# Import removed? Clean up.
dsp-cli remove-import obj-r1e2f3u4 obj-OLD_DEP

# File deleted? Remove the entity.
dsp-cli remove-entity obj-DELETED_UID
```

## 6. Impact analysis before refactoring

This is where DSP truly shines on brownfield projects.

### "What breaks if I change this?"

```bash
# Get everything that depends on the payment service
dsp-cli get-parents obj-p1a2y3m4 --depth inf
# obj-p1a2y3m4: Payment processing service
# ├── obj-c8d9e0f1: Webhook handler processes payment events
# ├── obj-b3c4d5e6: Order service triggers charges on checkout
# │   ├── obj-f7a8b9c0: Checkout controller
# │   └── obj-d1e2f3a4: Admin order management
# └── obj-r1e2f3u4: Refund service processes refunds

# Get direct consumers
dsp-cli get-recipients obj-p1a2y3m4
# obj-c8d9e0f1: webhook handler processes payment events
# obj-b3c4d5e6: order service triggers charges on checkout
# obj-r1e2f3u4: refund service uses payment service to look up original charges
```

### "What does this module actually depend on?"

```bash
dsp-cli get-children obj-b3c4d5e6 --depth 3
# Order service
# ├── obj-p1a2y3m4: Payment service
# │   ├── obj-ext-stripe: Stripe SDK
# │   └── obj-db-svc: Database service
# ├── obj-inv-svc: Inventory service
# │   └── obj-db-svc: Database service
# └── obj-email-svc: Email notification service
```

### "Are there circular dependencies?"

```bash
dsp-cli detect-cycles
# no cycles detected

# Or:
# cycle 1: obj-a1b2 -> obj-c3d4 -> obj-e5f6 -> obj-a1b2
```

### "What's the connection between these two modules?"

```bash
dsp-cli get-path obj-CHECKOUT_CTRL obj-DB_SERVICE
# obj-CHECKOUT_CTRL -> obj-ORDER_SVC -> obj-PAYMENT_SVC -> obj-DB_SERVICE
```

## 7. Setting up hooks

### Git hooks (pre-commit)

Install DSP consistency checks as pre-commit hooks:

**macOS / Linux:**
```bash
./hooks/install-hooks.sh
```

**Windows:**
```powershell
.\hooks\install-hooks.ps1
```

This installs a pre-commit hook that checks:
- New files are registered in DSP
- Deleted files are removed from DSP
- No orphaned entities
- No broken references

Configure the behavior:

```bash
# Warning mode (default) — warns but doesn't block commits
export DSP_PRECOMMIT_MODE=warn

# Block mode — blocks commits with DSP errors
export DSP_PRECOMMIT_MODE=block
```

### CI (GitHub Actions)

Add `.github/workflows/dsp-consistency.yml` to run DSP checks on every PR. See the [CI workflow template](../../.github/workflows/dsp-consistency.yml).

### Agent hooks (Claude Code / Cursor)

See the integration packs in `integrations/claude/` and `integrations/cursor/` for agent-specific hooks that check DSP consistency during coding sessions.

## 8. Common patterns and tips

### Pattern: Incremental bootstrap (fallback)

The three-wave bootstrap is the preferred path — flat passes are fast and resumable. But if a full pass over a huge repo is not an option right now, scope the waves down instead of abandoning them:

1. **Pick a zone** — the active development area or a critical subsystem
2. **Run all three waves inside that zone** — files, exports, imports (imports pointing outside the zone are added when their targets get indexed)
3. **Expand zone by zone** — when you touch a new area, run the waves over it
4. **`get-orphans` shows the frontier** — entities nothing references yet often mark unindexed boundaries

### Pattern: External dependency grouping

Group related external deps under a single entity rather than creating one per import:

```bash
# Good: one entity for the framework
dsp-cli create-object "@nestjs/core + @nestjs/common" \
  "NestJS framework — DI, module system, decorators, HTTP abstractions" \
  --kind external

# Rather than separate entities for @nestjs/core, @nestjs/common, @nestjs/platform-express
```

### Pattern: Regular health checks

Periodically check the graph health:

```bash
dsp-cli get-stats
# Quick overview: entity count, imports, shared, cycles, orphans

dsp-cli get-orphans
# Find disconnected entities that might need cleanup

dsp-cli detect-cycles
# Find circular dependencies to investigate
```

### Tip: Let the agent do the work

The agent already knows the DSP skill instructions. Instead of running CLI commands manually, ask the agent:

- *"Bootstrap DSP for this project starting from `src/main.ts`"*
- *"Update DSP after the changes I just made"*
- *"Run DSP health check and fix any issues"*
- *"Check impact before I refactor the payment module"*

### Tip: Commit `.dsp/` changes with your code

DSP changes should be part of the same commit as the code changes they describe. This keeps the graph and the code in sync at every point in git history.

### Tip: Don't update DSP for internal-only changes

If you change implementation details inside a module without affecting its purpose, imports, or public API, there's no need to update DSP. The protocol tracks *structure and contracts*, not implementation details.

### Tip: Study the boilerplate as a reference

[**dsp-boilerplate**](https://github.com/k-kolomeitsev/dsp-boilerplate) is a fully bootstrapped real-world example — NestJS + React with a complete DSP graph, `@dsp` markers in every source file, multi-root TOCs, import edges with `why`, and integration configs for all agents. It's the best reference for how a finished bootstrap should look.
