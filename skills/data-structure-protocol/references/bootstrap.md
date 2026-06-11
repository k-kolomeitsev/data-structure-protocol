# DSP Bootstrap Procedure

## Table of Contents

- [Overview](#overview)
- [Phase 0: Discover Roots (TOCs)](#phase-0-discover-roots-tocs)
- [File Inventory and Batching](#file-inventory-and-batching)
- [Wave 1: Index All Files](#wave-1-index-all-files)
- [Wave 2: Index All Exports](#wave-2-index-all-exports)
- [Barrier: Sync Point Before Imports](#barrier-sync-point-before-imports)
- [Wave 3: Index All Imports](#wave-3-index-all-imports)
- [Verification](#verification)
- [Re-indexing an Already-Marked Project](#re-indexing-an-already-marked-project)
- [Why This Is Fast and Cheap](#why-this-is-fast-and-cheap)
- [Key Rules](#key-rules)

## Overview

Bootstrap is the initial indexing of an existing project into `.dsp/`. It runs as **three flat waves after root discovery**, executed by **parallel subagents over fixed file batches**:

```
Phase 0:    discover roots                 →  create TOCs (--new-root --scope)
Inventory:  list all files + their sizes   →  split into batches per TOC,
                                              balanced by volume; 1 batch = 1 subagent
Wave 1:     subagent reads its batch ONCE  →  create-object / create-function (+ @dsp markers)
Wave 2:     same subagent, same read       →  create-shared
─────────── barrier: ALL batches done; orchestrator registers externals once ───────────
Wave 3:     same subagent, same read       →  add-import (usage-based why)
```

Two rules make this fast and cheap:

1. **Each file is read exactly once, by exactly one subagent.** All three waves run on top of that single read — the subagent keeps its batch in context and never re-opens sources. Token cost ≈ one pass over the codebase, regardless of the number of waves.
2. **Batches are independent within a wave.** All subagents run in parallel; the only global synchronization point is the barrier before Wave 3. Wall-clock time divides by the number of subagents.

## Phase 0: Discover Roots (TOCs)

Done by the orchestrator.

1. **Identify entrypoints**: `package.json` main, framework entry, `main.py`, `cmd/main.go`, etc. Multiple entrypoints (monorepo, backend+frontend) → multiple roots.
2. **Decide each root's scope** — the directory subtree it covers, repo-relative:
   - single root → scope `.` (whole repo),
   - monorepo → e.g. `backend`, `frontend`, `packages/shared`.
3. **Create each root** (its `description` must include a brief project overview):

```
dsp-cli create-object <root-file> "<purpose + project overview>" --new-root --scope <dir>
# → rootUid; creates .dsp/TOC-<rootUid> with rootUid as its first line
```

The scope drives **automatic TOC assignment**: every later `create-object`/`create-function` without an explicit `--toc` is appended to **all** TOCs whose root scope covers the file's path. With scopes set in Phase 0, the waves never need to mention TOCs at all.

> Single-root alternative: a plain `create-object <root-file> "<purpose>"` (no flags) starts the default `.dsp/TOC` — everything later falls into it automatically.

## File Inventory and Batching

Done by the orchestrator, **before any file content is read**.

1. **List all project files with their content volume** (bytes or lines):

   ```
   git ls-files | xargs wc -c     # or any equivalent
   ```

   Respect `.gitignore`; exclude vendored code (`node_modules`, `site-packages`, `vendor`), build output, lock files, and `.dsp/` itself.

2. **Group files by TOC** — match each path against the root scopes from Phase 0. A batch never mixes files of different TOCs. (A file covered by several scopes goes into one batch of either TOC — entity creation will register it into all matching TOCs automatically.)

3. **Split each group into batches of roughly equal total volume** — by content size, **not** by file count. A batch must fit comfortably into one subagent's context together with its tool calls. Equal volume means subagents finish at about the same time, so nobody idles at the barrier.

4. **Dispatch one subagent per batch**, in parallel. Each subagent receives: its file list, its root UID(s), and the Wave 1–3 instructions below.

## Wave 1: Index All Files

Goal: **every project file becomes an Object** — code, configs, styles, images, data files. Each subagent works only on its own batch; all batches run in parallel.

1. **Read each file of the batch — this is the only read of that file in the entire bootstrap.** While reading, capture everything the later waves will need: purpose, inner entities, exports, and each import together with its usage sites in the file body.
2. Register what was read:
   - `dsp-cli create-object <path> "<purpose>"` — TOC membership resolves automatically from root scopes;
   - for each significant inner entity (exported function/class/handler):
     `dsp-cli create-function "<path>#<symbol>" "<purpose>" --owner <objUid>`;
   - place `@dsp <uid>` comment markers before inner-entity declarations.
3. **Checkpoint:** when a batch reports done, the orchestrator can verify it — every file of the batch must resolve via `dsp-cli find-by-source <path>`.

Resume: if a batch is interrupted, re-dispatch it with the instruction to run `find-by-source` first and skip files already indexed.

## Wave 2: Index All Exports

The same subagent continues over the files it has already read — **no re-reading**. For each file with a public API:

```
dsp-cli create-shared <objUid> <memberUid> [<memberUid> ...]
```

Exports are batch-local (a file's exports are entities of that same file, created in Wave 1), so Wave 2 needs no synchronization with other batches — a subagent proceeds as soon as its own Wave 1 is done.

## Barrier: Sync Point Before Imports

Imports cross batch boundaries, so Wave 3 starts **only after every batch has completed Waves 1–2** — at that point every file and every export of the whole project exists in `.dsp/`.

At the barrier the orchestrator also handles **external dependencies**, so parallel subagents never race to create the same package:

1. Each subagent reports the external packages its batch imports (known from the Wave 1 read — no extra reading).
2. The orchestrator dedupes the union and registers each external **once**:

```
dsp-cli create-object <pkg> "<purpose>" --kind external --toc <rootUid>
dsp-cli add-to-toc <extUid> --toc <otherRootUid>     # for every other root that uses it
```

## Wave 3: Index All Imports

The same subagents continue, still without re-reading sources:

1. Each import was already verified against its usage site during the Wave 1 read (see [Import Verification](#import-verification-required-for-every-import)). Dead imports are removed from source code, never registered.
2. Resolve local targets to UIDs: `dsp-cli find-by-source <target-path>` — cheap, reads no file content; every target exists after Wave 1.
3. Register the edge with a usage-based reason:

```
dsp-cli add-import <thisUid> <importedUid> "<why>" [--exporter <moduleUid>]
```

4. External targets already exist (registered at the barrier) — only the `add-import` edges are added.

### Import Verification (REQUIRED for every import)

Before calling `add-import`, you MUST verify that the imported symbol is **actually used** in the file body (outside the `import` statement itself). During wave bootstrap this check happens at the Wave 1 read — record the evidence then:

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

After Wave 3, the orchestrator checks the whole graph:

```
dsp-cli get-stats        # totals: entities, imports, shared, cycles, orphans
dsp-cli get-orphans      # files nothing imports — expected for scripts/configs; review the rest
dsp-cli detect-cycles    # circular dependencies (diagnostic, not fatal)
dsp-cli read-toc --toc <rootUid>   # spot-check each root's TOC
```

Entity count should match the inventory: every file from the inventory resolves via `find-by-source`.

## Re-indexing an Already-Marked Project

If `.dsp/` was lost or is being rebuilt while the code still carries `@dsp` markers:

1. Collect the existing markers: `grep -rn "@dsp " --include="*" .` → a map of `path#symbol → uid`.
2. Run the same waves, passing the old UID at creation:

```
dsp-cli create-object <path> "<purpose>" --uid obj-<8hex>
dsp-cli create-function "<path>#<symbol>" "<purpose>" --owner <objUid> --uid func-<8hex>
```

The graph is rebuilt with stable UIDs — markers in source stay valid, and external references (docs, commits) keep pointing at the same entities. `--uid` fails on a collision or a prefix/type mismatch.

## Why This Is Fast and Cheap

- **One read per file.** The read happens in Wave 1; Waves 2–3 consume what the subagent extracted from that read. Token cost ≈ one pass over the codebase, no matter how many waves run on top.
- **Maximum parallelism.** Batches are independent; all subagents work simultaneously. The only global sync point is the barrier before Wave 3.
- **No missing-UID failures.** Every entity exists before the first `add-import` — no creating targets mid-pass.
- **Resumable.** The inventory fixes the work plan; `find-by-source` shows what is already done; a failed batch is simply re-dispatched.
- **Complete coverage.** Every project file is indexed, including scripts, configs, and assets not wired into the import graph.

## Key Rules

- **Phase 0 first**: roots and scopes must exist before Wave 1, or files have no TOC to land in.
- **One file — one subagent — one read.** All waves run on top of that read. If a subagent cannot be kept alive across the barrier, it must persist a compact per-file digest at the end of Wave 2 (purpose, exports, imports with usage evidence) so Wave 3 works from the digest, not from sources.
- **Batches never mix TOCs** and are balanced by content volume, not file count.
- **Wave 3 starts only after ALL batches finished Waves 1–2** (the barrier).
- **Externals are registered once, by the orchestrator, at the barrier**; never analyze their internals (no `node_modules`, no `site-packages`, no `vendor`).
- One file may contain multiple entities (Object + shared Functions) — all get separate UIDs in Wave 1, with `@dsp <uid>` markers in source.
- **Never register an import without verifying the symbol is used in the file body** — the check happens at the Wave 1 read.
- **No subagents available?** The same plan runs sequentially: keep the per-file digest from each Wave 1 read, process waves from the digest — each file is still read only once.
