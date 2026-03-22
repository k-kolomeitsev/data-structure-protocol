# Greenfield Workflow — Starting a New Project with DSP (Claude Code)

A walkthrough of building a new project from scratch with DSP and Claude Code.

## Scenario

You're starting a new REST API for a task management app. You want DSP from day one so the agent always has structural awareness.

## Step 1: Initialize DSP

```bash
dsp-cli init
```

This creates the `.dsp/` directory in your project root.

## Step 2: Plan the Architecture

The user prompts Claude:

> Build a task management API with users, projects, and tasks. Use Express + TypeScript.

Claude plans the module structure first, then registers each module in DSP as it creates files.

## Step 3: Create and Register the Database Layer

Claude creates `src/database/connection.ts` and immediately registers it:

```bash
dsp-cli create-object \
  --source src/database/ \
  --purpose "Database connection and query layer (PostgreSQL)"

# Output: obj-db000001
```

## Step 4: Create Core Modules

For each module, Claude writes code and registers the DSP entity:

```bash
# Users module
dsp-cli create-object \
  --source src/users/ \
  --purpose "User management — registration, authentication, profiles"
# Output: obj-us000002

# Projects module
dsp-cli create-object \
  --source src/projects/ \
  --purpose "Project management — CRUD operations for projects"
# Output: obj-pj000003

# Tasks module
dsp-cli create-object \
  --source src/tasks/ \
  --purpose "Task management — create, assign, update, complete tasks"
# Output: obj-tk000004
```

## Step 5: Register Functions Within Modules

```bash
dsp-cli create-function \
  --source src/users/users.service.ts \
  --purpose "User business logic — signup, login, profile updates" \
  --owner obj-us000002
# Output: func-us000005

dsp-cli create-function \
  --source src/tasks/tasks.service.ts \
  --purpose "Task business logic — CRUD, assignment, status transitions" \
  --owner obj-tk000004
# Output: func-tk000006
```

## Step 6: Declare Dependencies

```bash
# Users → Database
dsp-cli add-import obj-us000002 obj-db000001 \
  --why "persists user records"

# Projects → Database + Users
dsp-cli add-import obj-pj000003 obj-db000001 \
  --why "persists project records"
dsp-cli add-import obj-pj000003 obj-us000002 \
  --why "validates project owner exists"

# Tasks → Database + Projects + Users
dsp-cli add-import obj-tk000004 obj-db000001 \
  --why "persists task records"
dsp-cli add-import obj-tk000004 obj-pj000003 \
  --why "tasks belong to projects"
dsp-cli add-import obj-tk000004 obj-us000002 \
  --why "tasks are assigned to users"
```

## Step 7: Declare Public APIs

```bash
dsp-cli create-shared obj-us000002 UserService
dsp-cli create-shared obj-pj000003 ProjectService
dsp-cli create-shared obj-tk000004 TaskService
dsp-cli create-shared obj-db000001 DatabasePool
```

## Step 8: Verify the Graph

```bash
dsp-cli get-stats
```

```
entities: 6
objects: 4
functions: 2
imports: 6
shared: 4
orphans: 0
cycles: 0
```

```bash
dsp-cli read-toc
```

```
obj-db000001  src/database/    Database connection and query layer (PostgreSQL)
obj-us000002  src/users/       User management — registration, authentication, profiles
obj-pj000003  src/projects/    Project management — CRUD operations for projects
obj-tk000004  src/tasks/       Task management — create, assign, update, complete tasks
```

## Result

From the very first commit, the project has a complete structural memory. Any agent that opens this project will immediately understand:

- What modules exist and their purpose
- How they depend on each other and why
- What public APIs are available
- The project is clean — no orphans, no cycles

As the project grows, DSP grows with it. The agent never has to re-discover the architecture from scratch.
