# DSP Bootstrap Procedure

## Table of Contents

- [Overview](#overview)
- [Phase 0: Discover Roots (TOCs)](#phase-0-discover-roots-tocs)
- [Wave 1: Index All Files](#wave-1-index-all-files)
- [Wave 2: Index All Exports](#wave-2-index-all-exports)
- [Wave 3: Index All Imports](#wave-3-index-all-imports)
- [Verification](#verification)
- [Re-indexing an Already-Marked Project](#re-indexing-an-already-marked-project)
- [Why Flat Waves](#why-flat-waves)
- [Key Rules](#key-rules)

## Overview

Bootstrap is the initial indexing of an existing project into `.dsp/`. It runs as **three flat waves after root discovery**:

```
Phase 0: discover roots  →  create TOCs (--new-root --scope)
Wave 1:  ALL files       →  create-object / create-function (+ @dsp markers)
Wave 2:  ALL exports     →  create-shared
Wave 3:  ALL imports     →  add-import (+ externals)
```

Each wave is a **linear pass over the file list** — no recursion, no graph traversal, no backtracking. Files within a wave are independent, so work can be batched, checkpointed, and resumed. By the time imports are registered (Wave 3), every entity already exists, so `add-import` can never hit a missing UID.

## Phase 0: Discover Roots (TOCs)

1. **Identify entrypoints**: `package.json` main, framework entry, `main.py`, `cmd/main.go`, etc. Multiple entrypoints (monorepo, backend+frontend) → multiple roots.
2. **Decide each root's scope** — the directory subtree it covers, repo-relative:
   - single root → scope `.` (whole repo),
   - monorepo → e.g. `backend`, `frontend`, `packages/shared`.
3. **Create each root** (its `description` must include a brief project overview):

```
dsp-cli create-object <root-file> "<purpose + project overview>" --new-root --scope <dir>
# → rootUid; creates .dsp/TOC-<rootUid> with rootUid as its first line
```

The scope drives **automatic TOC assignment**: every later `create-object`/`create-function` without an explicit `--toc` is appended to **all** TOCs whose root scope covers the file's path. With scopes set in Phase 0, Waves 1–3 never need to mention TOCs at all.

> Single-root alternative: a plain `create-object <root-file> "<purpose>"` (no flags) starts the default `.dsp/TOC` — everything later falls into it automatically.

## Wave 1: Index All Files

Goal: **every project file becomes an Object** — code, configs, styles, images, data files. Not just files reachable from the entrypoint.

1. **List all project files.** Respect `.gitignore`; exclude vendored/external code (`node_modules`, `site-packages`, `vendor`), build output, lock files, and `.dsp/` itself.
2. **For each file** (read it to write an accurate purpose):
   - `dsp-cli create-object <path> "<purpose>"` — TOC membership is resolved automatically from root scopes;
   - for each significant inner entity (exported function/class/handler):
     `dsp-cli create-function "<path>#<symbol>" "<purpose>" --owner <objUid>`;
   - place `@dsp <uid>` comment markers before inner-entity declarations.
3. **Checkpoint/resume:** before creating, `dsp-cli find-by-source <path>` — if it returns a UID, the file is already indexed; skip it. `read-toc` / `get-stats` show progress.

Files can be processed in any order and in parallel batches (e.g. by directory).

## Wave 2: Index All Exports

Goal: register the public API of every file. For each file from Wave 1:

1. Determine what it exports (`export` statements, `__all__`, public methods).
2. `dsp-cli create-shared <objUid> <memberUid> [<memberUid> ...]`

All member UIDs already exist after Wave 1, so this wave is pure wiring — one command per file with exports.

## Wave 3: Index All Imports

Goal: register every dependency edge. For each file:

1. **Verify each import is alive** (see [Import Verification](#import-verification-required-for-every-import) below). Dead imports are not registered — remove them from source instead.
2. Resolve the import target to a UID: `dsp-cli find-by-source <target-path>` (everything local already exists after Wave 1).
3. `dsp-cli add-import <thisUid> <importedUid> "<why>" [--exporter <moduleUid>]`
4. **External packages** (npm, stdlib, SDK):
   - first occurrence: `dsp-cli create-object <pkg> "<purpose>" --kind external` — with per-root scopes the external usually needs an explicit TOC: `--toc <rootUid>` of the file being processed (scope `.` roots pick it up automatically);
   - already registered, but this file belongs to a different root: `dsp-cli add-to-toc <extUid> --toc <rootUid>`;
   - never descend into external internals.

### Import Verification (REQUIRED for every import)

Before calling `add-import`, you MUST verify that the imported symbol is **actually used** in the file body (outside the `import` statement itself):

1. For each imported symbol (`import { Foo, Bar } from '...'`), search for `Foo` and `Bar` in the rest of the file (excluding the import line).
2. **If a symbol is NOT found in the file body** → it is a dead import. Do NOT register it in DSP. Remove it from the source code.
3. **If a symbol IS found** → write the `why` based on the **actual usage site in this specific file**, not by restating the imported entity's description/purpose.

The `why` must answer: **"what would break in THIS file if this import were removed?"**

```
BAD why:  "Quick action suggestion buttons"       ← copied from entity description
GOOD why: "Rendered below chat input as quick-reply options when AI responds"
                                                   ← describes actual usage in this file

BAD why:  "Animation library for React"            ← generic package description
GOOD why: "motion.div wraps stat cards for fade-in entry on scroll"
                                                   ← describes what specifically is animated
```

This step prevents phantom dependencies in the graph — imports that exist in code but serve no purpose.

## Verification

After Wave 3:

```
dsp-cli get-stats        # totals: entities, imports, shared, cycles, orphans
dsp-cli get-orphans      # files nothing imports — expected for scripts/configs; review the rest
dsp-cli detect-cycles    # circular dependencies (diagnostic, not fatal)
dsp-cli read-toc --toc <rootUid>   # spot-check each root's TOC
```

## Re-indexing an Already-Marked Project

If `.dsp/` was lost or is being rebuilt while the code still carries `@dsp` markers:

1. Collect the existing markers: `grep -rn "@dsp " --include="*" .` → a map of `path#symbol → uid`.
2. Run the same waves, passing the old UID at creation:

```
dsp-cli create-object <path> "<purpose>" --uid obj-<8hex>
dsp-cli create-function "<path>#<symbol>" "<purpose>" --owner <objUid> --uid func-<8hex>
```

The graph is rebuilt with stable UIDs — markers in source stay valid, and external references (docs, commits) keep pointing at the same entities. `--uid` fails on a collision or a prefix/type mismatch.

## Why Flat Waves

- **No missing-UID failures.** Every entity exists before the first `add-import` — no creating targets mid-pass.
- **Linear, not recursive.** Each wave is a flat checklist over files: trivial to batch, parallelize (e.g. one batch per directory), checkpoint, and resume after interruption.
- **Complete coverage.** Wave 1 indexes every project file, including scripts, configs, and assets not wired into the import graph.
- **Predictable cost.** Three passes over N files — no unbounded traversal, no backtracking.

## Key Rules

- **Phase 0 first**: roots and scopes must exist before Wave 1, or files have no TOC to land in.
- External dependencies: `create-object ... --kind external` + TOC membership per root that uses them, but **never analyze their internals** (no `node_modules`, no `site-packages`, no `vendor`).
- One file may contain multiple entities (Object + shared Functions) — all get separate UIDs in Wave 1.
- Place `@dsp <uid>` comment markers in source code before each inner-entity declaration.
- **Never register an import without verifying the symbol is used in the file body.** See [Import Verification](#import-verification-required-for-every-import) in Wave 3.
- Resume safely: `find-by-source` before `create-object` — skip files that already have entities.
