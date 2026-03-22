# Greenfield Workflow: Starting a New Project with DSP

A guide for building a new project with DSP from day one — growing the structural graph incrementally alongside your code.

## The fastest path: dsp-boilerplate

If you want to skip all manual setup, use [**dsp-boilerplate**](https://github.com/k-kolomeitsev/dsp-boilerplate) — a production-ready fullstack starter (NestJS 11 + React 19 + Vite 7 + Docker Compose) with DSP fully pre-initialized:

```bash
git clone https://github.com/k-kolomeitsev/dsp-boilerplate.git my-project
cd my-project
docker-compose up -d
```

It comes with a complete `.dsp/` graph (two roots: backend + frontend), `@dsp` markers in all source files, DSP skills for all agents, Cursor rules, Claude Code hooks, git hooks, and CI. Your agent has structural memory from the first session.

If you prefer to start from scratch or use a different stack, follow the manual steps below.

## Prerequisites

- Python 3.10+
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

## 2. Initialize DSP

Right after creating your project scaffold:

```bash
# Create project
mkdir my-project && cd my-project
git init

# Initialize DSP
dsp-cli init
# initialized .dsp/
```

## 3. Create the first module and register

As you write your first file, immediately register it in DSP.

### Example: NestJS backend

```bash
# Create and register the app module (root)
dsp-cli create-object "src/app.module.ts" \
  "Application root module — bootstraps NestJS app, registers feature modules and global config"
# obj-82e23068

# Create and register the first feature module
dsp-cli create-object "src/health/health.module.ts" \
  "Health check module — exposes /health endpoint for load balancer probes"
# obj-a1b2c3d4

# Wire the dependency
dsp-cli add-import obj-82e23068 obj-a1b2c3d4 \
  "app module registers health module for uptime monitoring"

# Register external framework dependency
dsp-cli create-object "@nestjs/core" \
  "NestJS framework — dependency injection, module system, lifecycle management" \
  --kind external
# obj-ext-nest

dsp-cli add-import obj-82e23068 obj-ext-nest \
  "app module uses NestJS core for module bootstrapping and DI container"
```

### Example: Next.js frontend

```bash
# Register the app layout (root)
dsp-cli create-object "src/app/layout.tsx" \
  "Root layout — defines HTML structure, global providers, and shared UI shell"
# obj-layout01

# Register the home page
dsp-cli create-object "src/app/page.tsx" \
  "Home page — landing page with hero section and feature highlights"
# obj-home-pg

dsp-cli add-import obj-layout01 obj-home-pg \
  "layout renders home page as default route"
```

### Example: Python CLI

```bash
# Register the CLI entry point (root)
dsp-cli create-object "src/cli.py" \
  "CLI entry point — argument parsing, command dispatch, global error handling"
# obj-cli-main

# Register the first command module
dsp-cli create-object "src/commands/init.py" \
  "Init command — scaffolds project directory structure and config files"
# obj-cmd-init

dsp-cli add-import obj-cli-main obj-cmd-init \
  "CLI dispatches 'init' subcommand to this handler"
```

## 4. Growing the graph incrementally

The key principle: **register entities as you create them, not after**. This keeps the graph accurate and avoids catch-up work.

### When you create a new file

```bash
# 1. Write the file
# 2. Register it immediately
dsp-cli create-object "src/users/users.service.ts" \
  "Users service — CRUD operations, validation, password hashing"
# obj-usr-svc

# 3. Wire its imports
dsp-cli add-import obj-usr-svc obj-DB_SERVICE \
  "users service uses database for persistence"
dsp-cli add-import obj-usr-svc obj-ext-bcrypt \
  "uses bcrypt for password hashing"
```

### When you create a public function

```bash
# Register the function under its owner
dsp-cli create-function "src/users/users.service.ts#createUser" \
  "Creates a new user — validates input, hashes password, persists to database" \
  --owner obj-usr-svc
# func-create-usr

# Share it (make it part of the module's public API)
dsp-cli create-shared obj-usr-svc func-create-usr
```

### When another module imports it

```bash
# Auth controller imports createUser from users service
dsp-cli add-import obj-auth-ctrl func-create-usr \
  "registration endpoint delegates user creation to users service" \
  --exporter obj-usr-svc
```

### The growth pattern

As your project grows, the graph grows with it naturally:

```
Week 1:  3 entities, 4 imports     (app root, health, one feature)
Week 2:  12 entities, 25 imports   (auth, users, basic CRUD)
Week 3:  28 entities, 67 imports   (payments, notifications, admin)
Week 4:  45 entities, 110 imports  (full MVP)
```

Each entity takes seconds to register. The cumulative investment is small; the cumulative value (instant context for every future session) is large.

## 5. Setting up hooks from day one

On greenfield projects, set up hooks early — it's easier to maintain consistency from the start than to fix it later.

### Git hooks

```bash
# macOS / Linux
./hooks/install-hooks.sh

# Windows
.\hooks\install-hooks.ps1
```

Start with warning mode:

```bash
export DSP_PRECOMMIT_MODE=warn
```

This warns you (or the agent) when a commit includes new files not registered in DSP. Switch to `block` mode once the team is comfortable with the workflow.

### CI (GitHub Actions)

Add the DSP consistency workflow to your repo from day one. Copy `.github/workflows/dsp-consistency.yml` from the DSP repository. This provides:

- Graph stats in PR summaries
- Orphan detection
- Cycle detection
- Coverage check for changed files

### Agent hooks

If using Claude Code, set up the session hooks from the integration pack:

- **Session start** — prints DSP stats summary
- **Pre-write check** — warns if a file being edited isn't in DSP
- **Session end** — reminds about unregistered changes

## 6. Best practices for new projects

### Register modules before functions

Start with `create-object` for each file/module. Add `create-function` for public APIs once the module is stable. Internal helper functions don't need DSP entries.

### Write meaningful `purpose` fields

The `purpose` field is the most valuable part of a DSP entity. Write it as if explaining to a new team member:

```bash
# Weak
dsp-cli create-object "src/auth.ts" "Authentication"

# Strong
dsp-cli create-object "src/auth/auth.service.ts" \
  "Authentication service — JWT token generation/validation, session management, OAuth2 provider integration"
```

### Write meaningful `why` on imports

The `why` field on imports explains *the reason for the dependency*, not just its existence:

```bash
# Weak
dsp-cli add-import obj-A obj-B "imports B"

# Strong
dsp-cli add-import obj-ORDER_SVC obj-PAYMENT_SVC \
  "order service delegates payment processing to payment service during checkout flow"
```

### Use `--toc` for multi-root projects

If your project has multiple entry points (e.g., monorepo), use the `--toc` flag to group entities by root:

```bash
# Backend root
dsp-cli create-object "backend/src/main.ts" "Backend entry point" --toc obj-backend-root
# obj-backend-root

# Frontend root
dsp-cli create-object "frontend/src/main.tsx" "Frontend entry point" --toc obj-frontend-root
# obj-frontend-root

# Read a specific TOC
dsp-cli read-toc --toc obj-backend-root
```

### Don't over-register

Not everything needs a DSP entry. Skip:

- Internal helper functions that aren't exported
- Type definition files (unless they define shared contracts)
- Test files (unless they define test utilities used across modules)
- Configuration files (unless they're shared across features)
- Static assets (unless they're imported by code)

DSP tracks *structure and contracts*. Internal implementation details don't belong in the graph.

### Commit `.dsp/` with your code

Every commit that changes code structure should include the corresponding `.dsp/` changes. This keeps the graph in sync with the codebase at every point in git history.

```bash
git add src/users/users.service.ts .dsp/
git commit -m "feat: add users service with CRUD operations"
```

### Run health checks periodically

```bash
# Quick graph overview
dsp-cli get-stats
# entities: 28, objects: 22, functions: 6, imports: 67, cycles: 0, orphans: 0

# Find disconnected entities
dsp-cli get-orphans
# no orphans

# Check for circular dependencies
dsp-cli detect-cycles
# no cycles detected
```

Make this part of your regular development rhythm — weekly or before each release.
