# Data Structure Protocol (DSP) — Agent Guidance

This project uses **DSP** — a graph-based structural memory stored in `.dsp/`. It tracks entities (objects, functions), their dependencies (imports), and public interfaces (shared/exports).

DSP lets you understand the codebase structure without reading every file.

## Core Rules

1. **Before modifying code** — look up affected entities via `search`, `find-by-source`, or `read-toc`
2. **When creating files** — register with `create-object` or `create-function`, then `add-import` for dependencies and `create-shared` for public APIs
3. **When deleting/moving** — use `remove-entity` or `move-entity`, clean up with `remove-import` / `remove-shared`
4. **Skip DSP updates** for internal-only changes: formatting, comments, private function body edits, dependency bumps

## Command Reference

| Command | Purpose | Example |
|---|---|---|
| `init` | Initialize `.dsp/` in project root | `dsp-cli init` |
| `read-toc` | List all root entities (table of contents) | `dsp-cli read-toc` |
| `search <query>` | Full-text search across entity descriptions | `dsp-cli search "auth"` |
| `find-by-source <path>` | Find entity by source file path | `dsp-cli find-by-source src/auth/login.ts` |
| `get-entity <uid>` | Get full entity details | `dsp-cli get-entity obj-a1b2c3d4` |
| `get-children <uid>` | List child entities | `dsp-cli get-children obj-a1b2c3d4` |
| `get-parents <uid>` | Find who imports this entity | `dsp-cli get-parents func-e5f6g7h8` |
| `get-recipients <uid>` | Find who consumes shared exports | `dsp-cli get-recipients obj-a1b2c3d4` |
| `get-stats` | Project-wide DSP statistics | `dsp-cli get-stats` |
| `get-orphans` | Find entities with broken references | `dsp-cli get-orphans` |
| `detect-cycles` | Find circular dependencies | `dsp-cli detect-cycles` |
| `create-object` | Register a module/class/component | `dsp-cli create-object --source src/auth/login.ts --purpose "Login page"` |
| `create-function` | Register a function entity | `dsp-cli create-function --source src/utils/hash.ts --purpose "Password hashing" --owner obj-a1b2c3d4` |
| `create-shared` | Declare a public API export | `dsp-cli create-shared <uid> <name>` |
| `add-import` | Record a dependency between entities | `dsp-cli add-import <uid> <target-uid> --why "uses auth service"` |
| `move-entity` | Update source path after file move | `dsp-cli move-entity <uid> --source new/path.ts` |
| `remove-entity` | Delete an entity from the graph | `dsp-cli remove-entity <uid>` |
| `remove-import` | Remove a dependency link | `dsp-cli remove-import <uid> <target-uid>` |
| `remove-shared` | Remove a public API export | `dsp-cli remove-shared <uid> <name>` |
| `update-description` | Update entity purpose/kind | `dsp-cli update-description <uid> --purpose "Updated purpose"` |
| `update-import-why` | Update the reason for a dependency | `dsp-cli update-import-why <uid> <target-uid> --why "new reason"` |

## Typical Workflow

```
1. read-toc                          → understand project structure
2. search "feature-area"             → find relevant entities
3. get-entity <uid>                  → read details + imports + shared
4. get-parents <uid>                 → impact analysis before changes
5. ... make code changes ...
6. create-object / create-function   → register new entities
7. add-import --why "..."            → record new dependencies
8. create-shared                     → expose public APIs
9. get-orphans                       → verify graph consistency
```

## What NOT to Update in DSP

- Formatting or whitespace changes
- Comment-only edits
- Private function body refactors (no signature change)
- Dependency version bumps in package.json/requirements.txt
- Config file tweaks (.env, .gitignore, CI config)
- Test file internals (unless test architecture changes)
