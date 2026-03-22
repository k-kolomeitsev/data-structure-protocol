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

This installs the skill (SKILL.md + dsp-cli.py + references) into the appropriate directory for your agent.

## 2. Initialize DSP

```bash
dsp-cli init
# initialized .dsp/
```

This creates the `.dsp/` directory in your project root. Add it to version control — DSP is designed to be git-tracked.

## 3. Identify root entrypoints

Before bootstrapping, identify the root entrypoints of your project. Common patterns:

| Project type | Typical roots |
|---|---|
| Backend API | `src/main.ts`, `src/app.module.ts`, `cmd/server/main.go` |
| Frontend SPA | `src/main.tsx`, `src/App.tsx`, `pages/_app.tsx` |
| Fullstack monorepo | One root per package: `backend/src/main.ts`, `frontend/src/main.tsx` |
| CLI tool | `src/cli.ts`, `cmd/root.go`, `__main__.py` |
| Library | `src/index.ts`, `lib/mod.rs`, `__init__.py` |

For multi-root projects, each root gets its own TOC file using the `--toc` flag.

## 4. Bootstrap via DFS traversal

This is the most important step. The agent traverses the project from root entrypoints downward, registering every entity and its relationships.

### Step 4.1: Register the root

```bash
dsp-cli create-object "src/app.module.ts" \
  "Application root module — bootstraps NestJS app, registers all feature modules and global middleware"
# obj-82e23068
```

### Step 4.2: Open the root file, identify its imports

The agent reads `src/app.module.ts` and identifies all imports. For each import, it registers the target entity and the relationship.

```bash
# Register an imported module
dsp-cli create-object "src/users/users.module.ts" \
  "Users feature module — user CRUD, authentication, profile management"
# obj-a1b2c3d4

# Register the import with a reason
dsp-cli add-import obj-82e23068 obj-a1b2c3d4 \
  "app module imports users module to enable user management endpoints"

# Register another imported module
dsp-cli create-object "src/products/products.module.ts" \
  "Products feature module — product catalog, search, and inventory"
# obj-e5f6a7b8

dsp-cli add-import obj-82e23068 obj-e5f6a7b8 \
  "app module imports products module to enable catalog endpoints"
```

### Step 4.3: Register external dependencies

External libraries are registered as `--kind external`. You don't go inside them, but you track who uses them and why.

```bash
dsp-cli create-object "@nestjs/core" \
  "NestJS core framework — dependency injection, module system, lifecycle hooks" \
  --kind external
# obj-ext-01

dsp-cli add-import obj-82e23068 obj-ext-01 \
  "app module uses NestJS core for module bootstrapping and DI container"
```

### Step 4.4: Traverse depth-first

For each registered module, the agent opens its source, identifies its imports, and repeats the process. This is a DFS (depth-first search) traversal:

```
app.module.ts (root)
├── users/users.module.ts
│   ├── users/users.controller.ts
│   ├── users/users.service.ts
│   │   ├── users/users.repository.ts
│   │   │   └── database/database.service.ts (shared)
│   │   └── auth/auth.service.ts
│   └── users/dto/create-user.dto.ts
├── products/products.module.ts
│   ├── products/products.controller.ts
│   ├── products/products.service.ts
│   └── ...
└── database/database.module.ts (shared across features)
```

At each node:
1. **Register the entity** (`create-object` or `create-function`)
2. **Register its imports** (`add-import` with `why`)
3. **Register its exports** (`create-shared` for public API)
4. **Recurse into imports** (DFS)

### Step 4.5: Register shared/exported entities

When a module exports functions or entities used by other modules, register them:

```bash
# The users service has public methods used by other modules
dsp-cli create-function "src/users/users.service.ts#findById" \
  "Finds a user by ID — returns full user entity or throws NotFoundException" \
  --owner obj-a1b2c3d4
# func-c9d0e1f2

dsp-cli create-function "src/users/users.service.ts#validateCredentials" \
  "Validates email/password pair — returns user entity or null" \
  --owner obj-a1b2c3d4
# func-d3e4f5a6

# Register these as shared exports of the users module
dsp-cli create-shared obj-a1b2c3d4 func-c9d0e1f2 func-d3e4f5a6
```

### Step 4.6: Wire shared imports with exporters

When module A imports a specific function from module B, the import tracks both the function and the exporter:

```bash
# Auth service imports validateCredentials from users service
dsp-cli add-import obj-AUTH_SVC func-d3e4f5a6 \
  "auth service uses validateCredentials to verify login attempts" \
  --exporter obj-a1b2c3d4
```

### Bootstrap tips

- **Don't try to map everything in one session.** Start with the critical path (root → main modules → core services) and expand incrementally.
- **Focus on modules/files first, functions second.** Register all `create-object` entities for the key files, wire their imports, then add `create-function` for important public APIs.
- **External dependencies can be batched.** Register commonly used externals (framework, ORM, HTTP client) once and reference them across modules.
- **The agent should do this, not you.** Give the agent the DSP skill instructions and ask it to "bootstrap DSP for this project starting from `src/main.ts`".

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

### Pattern: Incremental bootstrap

Don't try to map the entire project at once. Start with:

1. **Core modules** — the main entrypoints and critical services
2. **Active development area** — whatever you're working on right now
3. **Shared infrastructure** — database, config, logging, auth
4. **Expand as needed** — when you touch a new area, bootstrap it then

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
