# DSP Operations Reference

## Table of Contents

- [Create Operations](#create-operations)
- [TOC Membership Operations](#toc-membership-operations)
- [Update Operations](#update-operations)
- [Delete Operations](#delete-operations)
- [Read Operations](#read-operations)
- [Graph Traversal](#graph-traversal)
- [Search and Discovery](#search-and-discovery)
- [Diagnostics](#diagnostics)
- [Maintenance](#maintenance)
- [Import Patterns](#import-patterns)

Wherever a `TOC` argument is accepted (`--toc`, `--from`, `--to`), it is either a **root UID** (targets that root's `.dsp/TOC-<uid>`) or the literal **`default`** (targets the plain `.dsp/TOC`).

## Create Operations

### createObject (§5.1)

```
dsp-cli create-object <source> <purpose> [--kind external] [--uid UID] [--toc TOC ...] [--new-root [--scope DIR]]
```

Creates an Object entity (module, class, config, external dep).

Actions:
1. Generate `obj-<8hex>` UID — or use `--uid` (re-indexing; fails on collision or prefix mismatch)
2. Resolve target TOCs (see below) — before any write, so a failure leaves no trace
3. Create `.dsp/<uid>/` with `description`, empty `imports`, empty `shared`
4. Append UID to every target TOC

TOC targets:
- `--new-root` — the object becomes a new root: `.dsp/TOC-<uid>` is created with this UID as its first line. Use this for every root of a multi-root project (the root's UID does not exist before this call, so it cannot be passed via `--toc`). Optional `--scope <dir>` declares the directory subtree this root covers (`.` = whole repo) — it drives automatic TOC assignment for all later entities
- `--toc TOC` (repeatable) — append to exactly these TOCs; each named TOC must already exist
- neither flag — **automatic resolution**:
  1. every TOC whose root `scope` covers the source path → all of them;
  2. otherwise the default `.dsp/TOC`, if it exists;
  3. otherwise, if no TOC files exist at all (fresh project) → the default `.dsp/TOC` is created;
  4. otherwise the command fails with a hint to pass `--toc`

stdout has two lines: first `toc: ...` (the TOC list), then the created UID on the **last** line. stderr is reserved for errors. Read the UID as the **last** line of stdout (e.g. `... | tail -n1`). The status goes to stdout, not stderr, to avoid PowerShell `NativeCommandError` noise on every call.

### createFunction (§5.2)

```
dsp-cli create-function <source> <purpose> [--owner UID] [--uid UID] [--toc TOC ...]
```

Creates a Function entity. `--uid` and `--toc` behave exactly as in `create-object` (automatic TOC resolution matches the file part of `<source>`, without `#symbol`).

Actions:
1. Generate `func-<8hex>` UID — or use `--uid`
2. Validate `--owner` and resolve target TOCs — before any write
3. Create `.dsp/<uid>/` with `description`, empty `imports`
4. If `--owner` specified:
   - Add funcUid to owner's `imports` (object "sees" its methods)
   - Create `.dsp/<funcUid>/exports/<ownerUid>` with "owner: method/member"
5. Append UID to every target TOC

### createShared (§5.3)

```
dsp-cli create-shared <exporter_uid> <shared_uid> [<shared_uid> ...]
```

Register entities as exported/public from an object.

**Every `shared_uid` must be an existing entity** — create it first with `create-function`/`create-object`, then share the returned UID. Export *names* (e.g. `UserService`) are rejected: shared entries are graph edges and must point at real nodes.

Actions:
1. Append each shared_uid to `.dsp/<exporter>/shared`
2. Create `.dsp/<exporter>/exports/<shared_uid>/description` (auto-filled from entity's purpose)

### addImport (§5.4)

```
dsp-cli add-import <importer_uid> <imported_uid> <why> [--exporter UID]
```

Record an import relationship.

**Pre-condition — Verify before calling:**

Before registering ANY import, you MUST confirm the imported symbol is **actually used** in the importer's file body (outside the `import` statement):

1. Search for the imported symbol in the file body (excluding the import line itself).
2. **If NOT found** → dead import. Do NOT call `addImport`. Remove the import from source code instead.
3. **If found** → proceed, but write `why` based on the **actual usage site**, not by restating the imported entity's purpose/description.

The `why` parameter answers: **"what would break in THIS file if this import were removed?"** It must describe the concrete role the import plays in the importing file.

```
BAD:  "Animation library"                          ← restates entity description
GOOD: "motion.div wraps each stat card for staggered fade-in on viewport entry"

BAD:  "Quick action suggestion buttons"            ← restates entity description
GOOD: "Rendered as horizontal pill row below chat messages for one-tap AI queries"

BAD:  "React namespace for component typing"       ← generic, says nothing specific
GOOD: "useState manages sidebar collapsed state, useEffect syncs with localStorage"
```

Actions:
1. Validate that importer, imported, and exporter (if given) all exist in `.dsp` — for a new external dependency, `create-object --kind external` first
2. Append `imported_uid [via=exporter]` to importer's `imports`
3. Write reverse link:
   - With `--exporter`: `.dsp/<exporter>/exports/<imported_uid>/<importer_uid>` = why
   - Without: `.dsp/<imported_uid>/exports/<importer_uid>` = why

## TOC Membership Operations

### addToToc (§5.23)

```
dsp-cli add-to-toc <uid> [<uid> ...] --toc <TOC> [--toc <TOC> ...]
```

Add **existing** entities to one or more TOCs — single or batch. Typical uses: an external dependency registered under root A is also used by root B; an entity should appear in an additional root's map.

Actions:
1. Validate every uid exists and every target TOC file exists
2. Append each uid to each TOC — idempotent: a uid already present is reported (`already in ...`) and never duplicated

### moveToToc (§5.24)

```
dsp-cli move-to-toc <uid> [<uid> ...] --from <TOC> --to <TOC>
```

Transfer entities from one TOC to another — single or batch. Typical uses: a module migrated between monorepo subprojects; an entity was indexed into the wrong root's map.

The whole batch is validated **before** anything is written (all-or-nothing):
- `--from` ≠ `--to`; both TOC files exist; every uid exists
- every uid is present in the source TOC
- no uid is the source TOC's **root** (TOC[0] defines the TOC and cannot leave it)

Actions:
1. Remove each uid from the source TOC
2. Append each uid to the target TOC; if already there, only the removal happens (reported as `already in target`)

Only TOC membership changes — the entity, its imports/shared/exports edges, and its membership in other TOCs are untouched.

## Update Operations

### updateDescription (§5.5)

```
dsp-cli update-description <uid> [--source S] [--purpose P] [--kind K] [--scope DIR]
```

Update specific fields in entity's description. Unspecified fields (including freeform `notes:` sections) remain unchanged.

Validation:
- `--kind` must be `object` / `function` / `external` and stay consistent with the UID prefix (`func-*` is always `function`; `obj-*` is never `function`)
- `--scope` is accepted only for **root entities** (TOC[0] of some TOC); the value is normalized (`\` → `/`, trailing slashes stripped, `.` = whole repo)

### updateImportWhy (§5.6)

```
dsp-cli update-import-why <importer> <imported> <new_why> [--exporter UID]
```

Update the reason text for an existing import.

### moveEntity (§5.7)

```
dsp-cli move-entity <uid> <new_source>
```

Update source path after file rename/move. UID stays the same.

## Delete Operations

### removeImport (§5.8)

```
dsp-cli remove-import <importer> <imported> [--exporter UID]
```

Remove an import relationship. Deletes the line from `imports` and the reverse link from `exports/`.

Matching is **exact on the exporter** — mirror the original `add-import` call:
- registered without `--exporter` → remove without `--exporter` (only a plain line matches)
- registered with `--exporter X` → remove with `--exporter X` (only the `via=X` line matches)

If neither the import line nor the reverse link is found, the command fails with a hint to add/drop `--exporter`.

### removeShared (§5.9)

```
dsp-cli remove-shared <exporter> <shared_uid>
```

Unregister a shared entity. Cascading:
1. Remove from `shared` file
2. Delete `exports/<shared_uid>/` directory with all recipients
3. Remove `shared_uid` from each recipient's `imports`

### removeEntity (§5.10)

```
dsp-cli remove-entity <uid>
```

Full entity removal with cascading cleanup:
1. Scan all entities' `imports` — remove lines referencing this uid (as imported or via=)
2. Sweep every other entity's `exports/` for any trace of this uid: the `exports/<uid>` file (uid as importer), the `exports/<uid>/` directory (uid as a shared entity — removed even if shared registration was skipped), and `exports/<shared>/<uid>` recipient files
3. Remove uid from any exporter's `shared` list
4. Remove uid from all TOC files; a root's own `TOC-<uid>` file is deleted entirely
5. Delete `.dsp/<uid>/` directory

A file usually holds several entities (the module Object + its functions). When deleting a file, run `find-by-source <path>` and `remove-entity` **each** returned UID.

## Read Operations

### getEntity (§5.11)

```
dsp-cli get-entity <uid>
```

Full snapshot: description, imports, shared, exported_to.

### getShared (§5.12)

```
dsp-cli get-shared <uid>
```

Public API of entity — what it exports and who uses each export.

### getRecipients (§5.13)

```
dsp-cli get-recipients <uid>
```

All importers of this entity (direct, via shared exporters, and owner/plain-imports edges). The importer set is served by the persistent reverse-index cache (see Storage Format → Reverse-index cache); each edge's `why` is read live from `exports/`.

## Graph Traversal

### getChildren (§5.14)

```
dsp-cli get-children <uid> [--depth N]
```

Dependency tree downward (what this entity imports). Default depth=1, use `inf` for full tree.

### getParents (§5.15)

```
dsp-cli get-parents <uid> [--depth N]
```

Dependency tree upward (who imports this entity). Default depth=1, use `inf` for full tree.

### getPath (§5.16)

```
dsp-cli get-path <from_uid> <to_uid>
```

Shortest path between entities (BFS, bidirectional on imports/exports edges).

## Search and Discovery

### search (§5.17)

```
dsp-cli search <query>
```

Full-text search across `.dsp/` descriptions and export file names. Case-insensitive.

### findBySource (§5.18)

```
dsp-cli find-by-source <source_path>
```

Find entities by source file path. Returns multiple UIDs (one file may contain Object + shared Functions).

### readTOC (§5.19)

```
dsp-cli read-toc [--toc ROOT_UID]
```

Read table of contents. TOC[0] = root. Entry point for project overview.

## Diagnostics

### detectCycles (§5.20)

```
dsp-cli detect-cycles
```

Find circular dependencies in the import graph.

### getOrphans (§5.21)

```
dsp-cli get-orphans
```

Find entities not imported by anyone (except roots). Candidates for dead code.

### getStats (§5.22)

```
dsp-cli get-stats
```

Overview: entity counts (objects/functions/externals), imports, shared, cycles, orphans.

## Maintenance

### rebuildCache (§5.25)

```
dsp-cli rebuild-cache
```

Rebuild the persistent reverse-index cache (`.dsp/.cache/`) from scratch by scanning every entity's forward `imports`. Idempotent; prints the number of imported entities indexed.

Run it only when `.dsp/` was changed **outside** this CLI — hand-edited files, or a `merge`/`rebase` that touched `.dsp/` (the incremental cache cannot see those). Normal CLI mutations keep the cache current, so this is rarely needed. See Storage Format → Reverse-index cache for what the cache holds and how it stays fresh.

## Import Patterns

When to use one `addImport` vs two:

```js
// 1 call: named import only
import { UserService } from './services';
// → addImport(thisUid, userServiceUid, servicesObjUid, why="user management")

// 1 call: side-effect / default import
import './polyfills';
// → addImport(thisUid, polyfillsObjUid, why="browser polyfills")

import express from 'express';
// → addImport(thisUid, expressObjUid, why="HTTP framework")

// 2 calls: namespace + named from same module
import * as utils from './utils';
// → addImport(thisUid, utilsObjUid, why="formatting utilities")
import { calc } from './utils';
// → addImport(thisUid, calcUid, utilsObjUid, why="total calculation")
```

**Rule:** two calls when importing BOTH the module as a whole AND a specific symbol from it. One call otherwise.

### Dead Import Detection

An `import` statement in source code is NOT proof of a dependency. Code may contain unused imports (leftover from refactoring, copy-paste, or auto-imports).

**Before every `addImport` call:**
1. Find the imported symbol name (e.g., `Foo` from `import { Foo } from '...'`).
2. Search for `Foo` in the file body **excluding the import line**.
3. If zero matches → **dead import**. Do not register. Remove from source code.

This applies equally during bootstrap and during incremental updates. A phantom edge in the dependency graph is worse than a missing edge — it creates false coupling and misleads impact analysis.
