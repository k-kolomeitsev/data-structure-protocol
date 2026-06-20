# DSP Storage Format

## Table of Contents

- [Directory Structure](#directory-structure)
- [Entity Directory](#entity-directory)
- [description File](#description-file)
- [imports File](#imports-file)
- [shared File](#shared-file)
- [exports/ Directory](#exports-directory)
- [TOC Files](#toc-files)
- [Reverse-index cache](#reverse-index-cache)

## Directory Structure

```
.dsp/
├── TOC                     # Table of contents (single root)
├── TOC-<rootUid>           # TOC per root (multi-root projects)
├── obj-a1b2c3d4/           # Object entity
│   ├── description         # source, kind, purpose
│   ├── imports             # list of imported UIDs
│   ├── shared              # list of exported UIDs
│   └── exports/            # reverse index (who imports this)
│       ├── <importer_uid>  # file: why this entity is imported
│       └── <shared_uid>/   # subdirectory per shared entity
│           ├── description # what is exported
│           └── <importer_uid>  # file: why this shared is imported
├── func-7f3a9c12/          # Function entity
│   ├── description
│   ├── imports
│   └── exports/
│       └── <owner_uid>     # file: "owner: method/member of this object"
└── .cache/                 # derived reverse-index cache (see below)
    ├── built               # sentinel: cache has been built
    └── rev/
        └── <imported_uid>  # file: importer UIDs, one per line (sorted)
```

## Entity Directory

Each entity gets `.dsp/<uid>/` where UID format is:

- `obj-<8 hex>` — objects (modules, classes, configs, externals)
- `func-<8 hex>` — functions (methods, handlers, pipelines)

Generated from first 8 chars of `uuid4().hex`.

## description File

```
source: <repo-relative-path>[#<symbol>]
kind: object|function|external
purpose: <1-3 sentences: what and why>
```

Optional extra sections (freeform): `notes:`, `contracts:`, etc.

**Root entrypoint rule:** root's `description` must include a brief project description (what the system is, main workflow, public API boundaries).

**Root-only field `scope:`** — repo-relative directory subtree this root covers (`.` = whole repo). Set via `create-object ... --new-root --scope <dir>` or `update-description <root-uid> --scope <dir>`. Entities created without an explicit `--toc` are appended to every TOC whose root scope covers their source path.

## imports File

One line per dependency:

```
<imported_uid>
```

Extended format (when imported via an exporter):

```
<imported_uid> via=<exporter_obj_uid>
```

Owner references (functions owned by objects) also appear here.

## shared File

One line per exported UID:

```
<shared_uid>
```

## exports/ Directory

Reverse index showing who imports this entity and why.

**Entity without shared** (Function, external, or Object imported wholesale):

```
exports/
└── <importer_uid>    # file content: "why imported" (1-3 sentences)
```

**Object with shared entities:**

```
exports/
├── <importer_uid>           # direct import of the whole object
└── <shared_uid>/            # subdirectory per shared entity
    ├── description          # what is exported (auto-filled from purpose)
    └── <importer_uid>       # why this specific shared is imported
```

This answers three questions:
1. **Who imports this entity** → `exports/<importer_uid>`
2. **What can be imported from it** → `shared` file
3. **Why a specific shared is imported** → `exports/<shared_uid>/<importer_uid>`

If the same shared-UID is re-exported from multiple objects (barrel exports), each exporter maintains its own exports index.

## TOC Files

**Naming:**
- `.dsp/TOC` — single root project
- `.dsp/TOC-<rootUid>` — multi-root project (one per root)

**Format:**

```
<uid_root>
<uid_2>
<uid_3>
...
```

**Rules:**
- TOC[0] is always the root entrypoint for this TOC
- Contains all entities of this root's zone (covered by its `scope`, reachable from it, or assigned explicitly), in documentation order
- Each UID appears exactly once per TOC
- Same entity may appear in multiple TOCs (overlapping scopes, externals shared between roots)
- New entities are appended at the end

**Lifecycle:**
- `TOC-<rootUid>` is created by registering the root with `create-object ... --new-root [--scope <dir>]` (the root's UID becomes its first line)
- Entities land in TOCs automatically (root scopes matching their path) or explicitly via repeatable `--toc <TOC>` on `create-object`/`create-function`, where `<TOC>` is a root UID or `default`
- Membership is reshaped with `add-to-toc` (add to more TOCs, idempotent) and `move-to-toc` (transfer between TOCs, batch, all-or-nothing; a root cannot leave its own TOC)
- When a root entity is removed (`remove-entity`), its `TOC-<uid>` file is deleted

## Reverse-index cache

`.dsp/.cache/` is a persistent index that answers reverse queries — "who imports X" — without scanning the whole graph on every call.

```
.cache/
├── built                  # sentinel: present once the cache has been built
└── rev/
    └── <imported_uid>     # importer UIDs of <imported_uid>, one per line (sorted)
```

- **Stores only the reverse adjacency** (`imported → importers`). The `why` text and recipient names are NOT cached — they are cheap live reads from `exports/` and the importer's own `imports` line, so they never go stale on their own.
- **The `built` sentinel** distinguishes "X has no importers" (rev file absent, sentinel present) from "cache not built yet" (sentinel absent).
- **Used by** the reverse/traversal commands: `get-recipients`, `get-parents`, `get-path`, and `get-entity`'s "exported to". Forward/local commands (`get-children`, `get-shared`, `read-toc`, `find-by-source`, `search`, diagnostics) read live files and never touch it.
- **Stays fresh automatically.** Because the CLI is the sole writer of `.dsp/`, every mutating command updates the affected reverse entries incrementally. A missing cache is rebuilt automatically on the next reverse/traversal command or reverse-affecting mutation — no manual step in normal use.
- **Committed with the graph** (not git-ignored), so a plain `git checkout`/`pull` carries it along. Changes made **outside** the CLI are not detected: after hand-editing `.dsp/`, or after a `merge`/`rebase` that touched `.dsp/` (where `.cache/` files may merge incorrectly or conflict), run `dsp-cli rebuild-cache` to regenerate it.
