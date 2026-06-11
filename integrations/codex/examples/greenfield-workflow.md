# Greenfield Workflow — Starting a New Project with DSP (Codex)

A walkthrough of building a new project from scratch with DSP and OpenAI Codex.

`dsp-cli` is shorthand for `python <skill-path>/scripts/dsp-cli.py --root .`.

## Scenario

You're starting a new REST API for a task management app. You want DSP from day one so Codex always has structural awareness.

## Prerequisites

- DSP skill installed in `.codex/skills/data-structure-protocol/`

## Step 1: Initialize DSP

```bash
dsp-cli init
```

This creates the `.dsp/` directory in your project root.

## Step 2: Plan the Architecture

You prompt Codex:

> Build a task management API with users, projects, and tasks. Use Express + TypeScript.

Codex uses the DSP skill to plan the module structure and register entities as it creates files.

## Step 3: Create and Register the Database Layer

Codex creates `src/database/connection.ts` and registers it:

```bash
dsp-cli create-object src/database/ \
  "Database connection and query layer (PostgreSQL)"
# → obj-dddd0001
```

## Step 4: Create Core Modules

For each module, Codex writes code and registers the DSP entity:

```bash
# Users module
dsp-cli create-object src/users/ \
  "User management — registration, authentication, profiles"
# → obj-aaaa0002

# Projects module
dsp-cli create-object src/projects/ \
  "Project management — CRUD operations for projects"
# → obj-bbbb0003

# Tasks module
dsp-cli create-object src/tasks/ \
  "Task management — create, assign, update, complete tasks"
# → obj-cccc0004
```

## Step 5: Register Functions Within Modules

```bash
dsp-cli create-function src/users/users.service.ts \
  "User business logic — signup, login, profile updates" \
  --owner obj-aaaa0002
# → func-aaaa0005

dsp-cli create-function src/tasks/tasks.service.ts \
  "Task business logic — CRUD, assignment, status transitions" \
  --owner obj-cccc0004
# → func-cccc0006
```

## Step 6: Declare Dependencies

```bash
# Users → Database
dsp-cli add-import obj-aaaa0002 obj-dddd0001 \
  "persists user records"

# Projects → Database + Users
dsp-cli add-import obj-bbbb0003 obj-dddd0001 \
  "persists project records"
dsp-cli add-import obj-bbbb0003 obj-aaaa0002 \
  "validates project owner exists"

# Tasks → Database + Projects + Users
dsp-cli add-import obj-cccc0004 obj-dddd0001 \
  "persists task records"
dsp-cli add-import obj-cccc0004 obj-bbbb0003 \
  "tasks belong to projects"
dsp-cli add-import obj-cccc0004 obj-aaaa0002 \
  "tasks are assigned to users"
```

## Step 7: Declare Public APIs

Shared entries are UIDs of existing entities. The service functions from Step 5 are shared directly; for projects and database the exported entities are registered first:

```bash
dsp-cli create-shared obj-aaaa0002 func-aaaa0005
dsp-cli create-shared obj-cccc0004 func-cccc0006

dsp-cli create-function src/projects/projects.service.ts \
  "Project business logic — CRUD, membership checks" \
  --owner obj-bbbb0003
# → func-bbbb0007
dsp-cli create-shared obj-bbbb0003 func-bbbb0007

dsp-cli create-function src/database/pool.ts \
  "Connection pool accessor for repositories" \
  --owner obj-dddd0001
# → func-dddd0008
dsp-cli create-shared obj-dddd0001 func-dddd0008
```

## Step 8: Verify the Graph

```bash
dsp-cli get-stats
```

```
entities:  8
  objects:   4
  functions: 4
  external:  0
imports:   10
shared:    4
cycles:    0
orphans:   0
```

(`imports` counts cross-module edges plus owner links — an object "sees" its functions.)

```bash
dsp-cli read-toc
```

```
obj-dddd0001 [root]
obj-aaaa0002
obj-bbbb0003
obj-cccc0004
func-aaaa0005
func-cccc0006
func-bbbb0007
func-dddd0008
```

## Result

From the first commit, the project has a complete structural memory. Codex will never need to re-read the entire codebase to understand the architecture. As the project grows, DSP grows with it — each new module and dependency is tracked in the graph.
