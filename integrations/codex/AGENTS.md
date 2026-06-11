# Data Structure Protocol (DSP) — Agent Guidance

This project uses **DSP** — a graph-based structural memory stored in `.dsp/`. It tracks entities (objects, functions), their dependencies (imports), and public interfaces (shared/exports).

DSP lets you understand the codebase structure without reading every file.

## Running the CLI

`dsp-cli` below is shorthand for the bundled script:

```bash
python <skill-path>/scripts/dsp-cli.py --root . <command> [args]
```

The script lives in the installed skill directory (`.claude/skills/data-structure-protocol/`, `.cursor/skills/...`, or `.codex/skills/...`). All `source` paths are repo-relative. Arguments are **positional** (no `--source`/`--purpose`/`--why` flags); quote multi-word values.

## Core Rules

1. **Before modifying code** — look up affected entities via `search`, `find-by-source`, or `read-toc`
2. **When creating files** — register with `create-object` or `create-function`, then `add-import` for dependencies and `create-shared` for public APIs
3. **When deleting/moving** — use `remove-entity` or `move-entity`, clean up with `remove-import` / `remove-shared`
4. **Skip DSP updates** for internal-only changes: formatting, comments, private function body edits, dependency bumps

## Command Reference

| Command | Purpose | Example |
|---|---|---|
| `init` | Initialize `.dsp/` in project root | `dsp-cli init` |
| `read-toc` | List all entities of a TOC (first line = root) | `dsp-cli read-toc` |
| `search <query>` | Full-text search across entity descriptions | `dsp-cli search "auth"` |
| `find-by-source <path>` | Find entity by source file path | `dsp-cli find-by-source src/auth/login.ts` |
| `get-entity <uid>` | Get full entity details | `dsp-cli get-entity obj-a1b2c3d4` |
| `get-children <uid>` | Dependency tree downward (what it imports) | `dsp-cli get-children obj-a1b2c3d4` |
| `get-parents <uid>` | Dependency tree upward (who imports it) | `dsp-cli get-parents func-e5f6a7b8` |
| `get-recipients <uid>` | All importers of this entity, with reasons | `dsp-cli get-recipients obj-a1b2c3d4` |
| `get-stats` | Project-wide DSP statistics | `dsp-cli get-stats` |
| `get-orphans` | Find unused entities (nothing imports them) | `dsp-cli get-orphans` |
| `detect-cycles` | Find circular dependencies | `dsp-cli detect-cycles` |
| `create-object` | Register a module/class/config/external dep | `dsp-cli create-object src/auth/login.ts "Login page"` |
| `create-function` | Register a function entity | `dsp-cli create-function "src/utils/hash.ts#hashPassword" "Password hashing" --owner obj-a1b2c3d4` |
| `create-shared` | Mark existing entities (by UID) as public API | `dsp-cli create-shared obj-a1b2c3d4 func-e5f6a7b8` |
| `add-import` | Record a dependency between entities | `dsp-cli add-import obj-aaaa1111 obj-bbbb2222 "uses auth service for login flow"` |
| `add-to-toc` | Add existing entities to TOC(s) — batch, idempotent | `dsp-cli add-to-toc obj-a1b2c3d4 --toc obj-r1o2o3t4` |
| `move-to-toc` | Transfer entities between TOCs — batch, all-or-nothing | `dsp-cli move-to-toc obj-a1b2c3d4 func-e5f6a7b8 --from default --to obj-r1o2o3t4` |
| `move-entity` | Update source path after file move | `dsp-cli move-entity obj-a1b2c3d4 new/path.ts` |
| `remove-entity` | Delete an entity from the graph (cascading) | `dsp-cli remove-entity obj-a1b2c3d4` |
| `remove-import` | Remove a dependency link | `dsp-cli remove-import obj-aaaa1111 obj-bbbb2222` |
| `remove-shared` | Unregister a shared entity (by UID) | `dsp-cli remove-shared obj-a1b2c3d4 func-e5f6a7b8` |
| `update-description` | Update entity source/purpose/kind/scope | `dsp-cli update-description obj-a1b2c3d4 --purpose "Updated purpose"` |
| `update-import-why` | Update the reason for a dependency | `dsp-cli update-import-why obj-aaaa1111 obj-bbbb2222 "new reason"` |

**Shared entities are UIDs, not names.** To expose `WishlistService` as public API: first `create-function` (or `create-object`) for it, then pass the returned UID to `create-shared`. The CLI rejects anything that is not an existing `obj-`/`func-` UID.

**Imports via an exporter.** When importing a specific shared symbol from a module, pass `--exporter <module-uid>` to both `add-import` and the matching `remove-import` — the reverse index lives under the exporter.

**TOC membership is automatic.** A root created with `--new-root --scope <dir>` covers a directory subtree (`.` = whole repo). New entities land in every TOC whose root scope covers their path; override with repeatable `--toc <TOC>` (`<TOC>` = root UID or `default`). Reshape later with `add-to-toc` / `move-to-toc` (a root cannot leave its own TOC).

**Re-indexing keeps UIDs.** If source code already carries `@dsp <uid>` markers (e.g. `.dsp/` is being rebuilt), pass `--uid <uid>` to `create-object`/`create-function` so entities keep their identity. The CLI fails on collisions and `obj-`/`func-` prefix mismatches.

## Typical Workflow

```
1. read-toc                                   → understand project structure
2. search "feature-area"                      → find relevant entities
3. get-entity <uid>                           → read details + imports + shared
4. get-parents <uid>                          → impact analysis before changes
5. ... make code changes ...
6. create-object / create-function            → register new entities
7. add-import <uid> <target-uid> "reason"     → record new dependencies
8. create-shared <uid> <shared-uid>           → expose public APIs
9. get-orphans                                → verify graph consistency
```

## What NOT to Update in DSP

- Formatting or whitespace changes
- Comment-only edits
- Private function body refactors (no signature change)
- Dependency version bumps in package.json/requirements.txt
- Config file tweaks (.env, .gitignore, CI config)
- Test file internals (unless test architecture changes)
