## DSP (Data Structure Protocol) — architecture

---

### Agent Prompt (paste into system/user prompt)

> **This project uses DSP (Data Structure Protocol).**
> The `.dsp/` directory is the project entity graph: modules, functions, dependencies, public API. This is your long-term memory of the code structure.
>
> **Working rules:**
>
> 1. **Before changing code** — find the affected entities via `dsp-cli search`, `find-by-source`, or `read-toc`. Read their `description` and `imports` to understand the context.
> 2. **When creating a file/module** — immediately call `dsp-cli create-object`. For each exported function — `create-function` (with `--owner`). Register exports via `create-shared`.
> 3. **When adding an import** — call `dsp-cli add-import` with a short `why`. For external dependencies — first `create-object --kind external` if the entity does not exist yet.
> 4. **When removing an import / export / file** — call `remove-import`, `remove-shared`, `remove-entity` respectively. Cascading cleanup is performed automatically.
> 5. **When renaming/moving a file** — call `move-entity`. The UID does not change.
> 6. **Don’t touch DSP** if only internal implementation changed, without changing purpose and dependencies.
> 7. **TOC membership** — new entities land in every TOC whose root scope covers their path (or pass `--toc` explicitly, repeatable). Re-shape membership later with `add-to-toc` / `move-to-toc`.
> 8. **Bootstrap** — if `.dsp/` is empty: discover roots (`--new-root --scope`), split files into per-TOC batches balanced by volume, then three waves over the batches in parallel — index all files, then all exports, then all imports. Each file is read exactly once (in Wave 1); later waves reuse that read.
>
> **Key commands:**
> ```
> dsp-cli init
> dsp-cli create-object <source> <purpose> [--kind external] [--uid UID] [--toc TOC ...] [--new-root [--scope DIR]]
> dsp-cli create-function <source> <purpose> [--owner UID] [--uid UID] [--toc TOC ...]
> dsp-cli create-shared <exporter_uid> <shared_uid> [<shared_uid> ...]
> dsp-cli add-import <importer_uid> <imported_uid> <why> [--exporter UID]
> dsp-cli add-to-toc <uid> [<uid> ...] --toc TOC [--toc TOC ...]
> dsp-cli move-to-toc <uid> [<uid> ...] --from TOC --to TOC
> dsp-cli remove-import <importer_uid> <imported_uid> [--exporter UID]
> dsp-cli remove-shared <exporter_uid> <shared_uid>
> dsp-cli remove-entity <uid>
> dsp-cli move-entity <uid> <new_source>
> dsp-cli update-description <uid> [--source S] [--purpose P] [--kind K] [--scope DIR]
> dsp-cli get-entity <uid>
> dsp-cli get-children <uid> [--depth N]
> dsp-cli get-parents <uid> [--depth N]
> dsp-cli search <query>
> dsp-cli find-by-source <path>
> dsp-cli read-toc [--toc ROOT_UID]
> dsp-cli get-stats
> ```
>
> `TOC` above is a root UID or the literal `default` (the plain `.dsp/TOC` file).

---

### 1) Goal and scope

**The goal of DSP** is to store _minimal, but sufficient_ context about a repository/artifact system as a graph “entities → dependencies/public API”, so that an LLM can:

- quickly find the required fragments by UID,
- understand _why_ entities exist and _how_ they are connected,
- avoid having to load the entire source tree into the context window.

**DSP is long-term memory and an index of the project for an LLM.** At any time, an agent can run project-wide search (grep), find the required entities by descriptions/keywords, and from a found UID expand the whole relationship graph: incoming dependencies, outgoing imports, and recipients via `exports`. This replaces the need to “remember” the project structure or load it in full — the whole project map is always available through `.dsp`.

**DSP is not documentation for humans and not an AST dump.** DSP records:

- the _meaning_ of entities (purpose),
- _boundaries_ (what it imports / what it shares outward),
- _reasons for relationships_ (why something is imported), in a volume sufficient for code generation and refactoring.

**DSP works with any data and codebases** (Node.js, Python, Go, frontend, backend, infrastructure, etc.).

### 2) Model principles

- **Code = graph.** Graph nodes are _objects_ and _functions_. Edges are `imports`, `shared/exports`.
- **Identity by UID, not by file.** A file path is an attribute, not an identifier. Renames/moves must not change the UID.
- **“Shared” creates an entity.** If part of an object becomes available externally (export/public), it must have its own UID (and its own directory in `.dsp`).
- **Import tracks both “from where” and “what”.** For one actual import in code, two links may be recorded:
  - to the **Object module/provider** (where we import from),
  - to the **specific shared entity** (what exactly we use).
- **Import completeness (coverage).** **Any file/artifact that is imported/connected somewhere must be represented in `.dsp` as an Object with UID and `source:`.** This includes not only code, but also assets/resources: images (`.png/.svg/.webp`), styles (`.css/.scss`), data (`.json`), wasm, sql, templates, etc.
- **`why` is always written next to the imported entity.** The feedback is stored in `exports` of the imported entity (see §4.3 and `addImport`).
- **Start from roots.** Each root is a separate entrypoint with its own TOC file. By default, roots are auto-detected via the LLM; if needed, they are specified manually. A root may declare a `scope` — the directory subtree it covers — and every new entity is then assigned to the TOCs whose root scope covers its path (or to explicitly listed TOCs).
- **External dependencies are recorded only.** If an entity imports an external library/tool (npm packages, stdlib, SDK, etc.), DSP records the _fact of the import_ and a brief purpose, but **does not dive inside** the dependency (in Node.js do not go into `node_modules`; in Python — into `site-packages`; in Go — into `vendor`/module cache; etc.). At the same time, external dependencies still have an **`exports index`** — you can see who imports them and why, so the relationship graph remains complete.

### 3) Terms

- **Entity**: a graph node. Two base kinds: `Object` and `Function`.
- **Object**: _any “thing” with a UID that is not a function_ (module/ES module, class, namespace, config, resource file, external dependency, etc.). Variables are considered part of a global or local Object; when shared/exported they become separate entities with their own UID.
- **Function**: a function/method/handler/pipeline that performs work.
- **imports**: a list of UIDs of any entities outside the local scope that the current entity **uses** (imports of modules, libraries, objects, functions; dependencies via constructor/DI in classes). For an Object, this also includes its own methods/functions — so the object “sees” its composition.
- **shared**: a list of UIDs of entities available outside the local scope (exported functions, objects, variables; public fields/methods of classes).
- **exports index**: a reverse index “who imports this entity and why”. Maintained for any imported entity (Object, Function, external).


### 4) Storage: the `.dsp` directory

#### 4.1. Directory structure

At the repository root, a `.dsp/` directory is created. For each entity, a directory is created:

- `.dsp/<uid>/`

UID format (to avoid collisions and indicate type by prefix):

- `obj-<8 hex>` — for objects (example: `obj-a1b2c3d4`)
- `func-<8 hex>` — for functions (example: `func-7f3a9c12`)

Generation: first 8 characters of `uuid4().hex`. 4 billion possible UIDs is enough for any project.

For entities **inside a file** (to avoid binding to line numbers), the UID is anchored to code via a **comment marker** right before the declaration:

```js
// @dsp func-a1b2c3d4
export function calculateTotal(items) { ... }
```

```python
# @dsp obj-e5f6g7h8
class UserService:
```

The `@dsp <uid>` marker lets you quickly find an entity in code via grep, is independent of lines/formatting, and does not require renaming symbols.

> Important: the UID must be _stable_ for “the same” entity across moves/renames (path/file may change, UID must not).

#### 4.2. Entity files

Each entity directory contains:

- `description` — purpose + link to the source code (path/symbol).
- `imports` — list of imports/references to entities (one entry per line).
- `shared` — list of UIDs of entities available outside the local scope (exports, public fields/methods).
- `exports/` — _(created as needed)_ reverse index: who imports this entity and/or its shared parts, and why. Works for any kind (Object, Function, external).

##### 4.2.1. `description` format

The `description` file is a **short, human- and LLM-readable** block. Minimal recommended template:

```text
source: <repo-relative-path>[#<symbol>]
kind: object|function|external
purpose: <1-3 sentences: what it is and why>
```

After that (optional), freeform text/markdown sections may follow (no rigid schema), e.g. `notes:` / `contracts:`.

**Rule for the root file (root entrypoint):** its `description` must include a **brief project overview** (what the system is, its main pipeline/workflow, and what is public API/boundaries) — as short as possible so it becomes the first “project context” for the LLM.

**Root-only field `scope:`** — the repo-relative directory subtree this root covers (`.` = whole repo). Set via `create-object ... --new-root --scope <dir>` or later via `update-description <rootUid> --scope <dir>`. Scope drives automatic TOC assignment (§5.1): an entity created without an explicit `--toc` is appended to every TOC whose root scope covers the entity's source path.

##### 4.2.2. `imports` format

Minimal format (one line — one dependency):

```text
<imported_uid>
```

Allowed extension (if you need to encode “via which exporter” or other metadata):

```text
<imported_uid> via=<exporter_obj_uid>
```

##### 4.2.3. `shared` format

One line — one shared entity UID:

```text
<shared_uid>
```

#### 4.3. Export index (reverse index)

The `exports/` directory is created for **any** imported entity (Object, Function, external) and shows who uses it and why.

**For an entity without shared** (Function, external, or an Object imported as a whole):

- `.dsp/<uid>/exports/<importer_uid>` — a file with text “why it is imported” (1–3 sentences).

**For an Object with shared entities**, add the following:

- `.dsp/<uid>/exports/<shared_uid>/description` — what is exported (briefly).
- `.dsp/<uid>/exports/<shared_uid>/<importer_uid>` — “why this shared is imported” (1–3 sentences).

This gives the LLM answers to three questions:

- **who imports the entity and why** (via `exports/<importer_uid>`),
- **what can be imported from the object** (via `shared`),
- **why a specific shared is imported** (via `exports/<shared_uid>/<importer_uid>`).

> If the same shared UID is re-exported from multiple objects (barrel exports), export indices are kept _separately in each exporter_.

#### 4.4. Table of contents (TOC) files — mandatory

For each root entrypoint, **its own TOC file** is created under `.dsp/`. One root — one TOC.

**Naming:** `.dsp/TOC` for a single root, `.dsp/TOC-<rootUid>` if there are multiple roots.

**Format:**

```text
<uid_root>
<uid_2>
<uid_3>
...
<uid_N>
```

**Rules:**

- **TOC[0] is always the root** of this entrypoint. This is how the LLM gets a starting point.
- Next — all entities belonging to that root's zone (covered by its `scope`, reachable from it, or assigned explicitly), in documentation order.
- Each UID appears in a given TOC **exactly once**.
- The same entity **may** be in multiple TOCs (overlapping scopes, shared/external dependencies used by several roots).
- When documenting new entities — they are appended to the end of the corresponding TOC(s): automatically by scope matching, or explicitly via `--toc` / `add-to-toc`.
- Membership is reshaped with `add-to-toc` (add to more TOCs) and `move-to-toc` (transfer between TOCs); a root cannot be moved out of its own TOC.

**Purpose:**

- A complete overview of all entities in a given root's zone.
- Lets the LLM start navigation from the right entrypoint and dive into its structure.
- In multi-root projects (monorepo, multiple applications), each TOC is an independent map of its subtree.

#### 4.5. Reverse-index cache (`.dsp/.cache/`)

To answer reverse queries — “who imports X” — without scanning the whole graph on every call, DSP keeps a persistent reverse index under `.dsp/.cache/`:

- `.dsp/.cache/rev/<imported_uid>` — the importer UIDs of `<imported_uid>`, one per line (sorted).
- `.dsp/.cache/built` — a sentinel: present once the cache has been built. It distinguishes “X has no importers” (rev file absent, sentinel present) from “cache not built yet” (sentinel absent).

**What it stores (and what it does not).** Only the reverse adjacency `imported → importers`. The `why` text and the direct/shared recipient names are **not** cached — they are cheap local reads (`exports/<X>/` and the importer’s own `imports` line), so they stay live and can never go stale on their own.

**Who uses it.** The reverse and traversal commands: `getRecipients` (§5.13), `getParents` (§5.15), `getPath` (§5.16), and `getEntity`’s “exported to” (§5.11). Local/forward commands (`getChildren`, `getShared`, `readTOC`, `findBySource`, `search`, and the diagnostics) read live files and never touch the cache.

**Freshness.** The CLI is the sole writer of `.dsp/` (the §9 contract), so every mutating operation updates the affected reverse entries incrementally — the cache stays correct as the graph is built. A missing cache is rebuilt automatically on the next reverse/traversal command or reverse-affecting mutation; no manual step is needed in normal use.

**Committed with the graph.** `.cache/` is versioned together with `.dsp/` (not git-ignored), so a plain `git checkout`/`pull` carries it along. Changes made **outside** the CLI are not detected: after hand-editing `.dsp/`, or after a `merge`/`rebase` that touched `.dsp/` (where `.cache/` files may merge incorrectly or conflict), run `rebuildCache` (§5.25) to regenerate it from scratch.

### 5) Operations (tooling-level API)

Below are the operations used by the `.dsp` generator.

#### 5.0. `init`

Initialize the `.dsp/` directory at the project root. Required first step before any operations. Idempotent — repeated calls are safe.

CLI: `dsp-cli init`

#### 5.1. `createObject(sourceRef, purpose, kind?, tocs?, newRoot?, uid?, scope?) -> objUid`

Parameters:

- `sourceRef` — path to source (+ symbol if applicable),
- `purpose` — purpose,
- `kind` — `object` (default) or `external` (for external dependencies),
- `tocs` — list of TOC targets (root UID or `default`, repeatable): append the new entity to exactly these TOCs. Every explicitly named TOC must already exist,
- `newRoot` — make the object a **new root**: create `TOC-<objUid>` with `objUid` as its first line (mutually exclusive with `tocs`). This is the only way to start a new root TOC — the root's UID is generated by this very call, so it cannot be passed via `tocs`,
- `uid` — use this UID instead of generating one (re-indexing a project whose code already carries `@dsp` markers). Fails on a collision or an `obj-`/`func-` prefix mismatch,
- `scope` — only with `newRoot`: the directory subtree this root covers (`.` = whole repo); written into `description` as `scope:`.

**TOC resolution** (when neither `tocs` nor `newRoot` is given):

1. the entity is appended to **every** TOC whose root `scope` covers `sourceRef` (the path part, without `#symbol`);
2. no scope matches → the default `.dsp/TOC`, if it exists;
3. no TOC files exist at all (fresh project) → the default `.dsp/TOC` is created;
4. otherwise the operation **fails** with a hint to pass `tocs` explicitly — it never invents a new TOC silently.

Actions:

- generate `objUid`, or validate the supplied `uid` (format, prefix, uniqueness),
- resolve target TOCs (see above) — **before any write**, so a failure leaves no trace,
- create `.dsp/<objUid>/`,
- write `.dsp/<objUid>/description` (source, kind, purpose, and `scope` for a new root),
- create `.dsp/<objUid>/imports` if missing (empty),
- if needed — `.dsp/<objUid>/shared` (empty),
- **append `objUid` to every target TOC**: the freshly created `.dsp/TOC-<objUid>` when `newRoot` is set, otherwise the resolved/explicit list.

CLI writes two lines to stdout: first `toc: ...` (the TOCs the entity landed in), then the created UID on the **last** line; stderr is reserved for real errors. (The status goes to stdout, not stderr, so PowerShell does not wrap every call in `NativeCommandError` noise.) Machine callers must read the UID as the **last** line of stdout.

#### 5.2. `createFunction(sourceRef, purpose, ownerUid?, tocs?, uid?) -> funcUid`

Parameters: `tocs` and `uid` behave exactly as in `createObject` (§5.1), including automatic TOC resolution by root scopes — the path part of `sourceRef` (without `#symbol`) is matched.

Actions:

- generate `funcUid`, or validate the supplied `uid` (format, `func-` prefix, uniqueness),
- validate `ownerUid` and resolve target TOCs — **before any write**,
- create `.dsp/<funcUid>/`,
- write `.dsp/<funcUid>/description`,
- create `.dsp/<funcUid>/imports` (empty),
- if `ownerUid` is provided:
  - append `funcUid` to the owner object’s `imports` (so the object “sees” its methods),
  - create a reverse record `.dsp/<funcUid>/exports/<ownerUid>` (so `getParents` can find the owner without a full scan),
- **append `funcUid` to every target TOC**.

> Function ownership is determined through the owner’s `imports`. Reverse lookup — through `getParents(funcUid)`. A standalone function (without an owner) is simply added to a module’s `shared` if it is exported.

#### 5.3. `createShared(exporterUid, sharedUids[])`

Every `sharedUid` must be an **existing entity** — create it first via `createObject`/`createFunction`. Export *names* are rejected: shared entries are UIDs, otherwise the graph accumulates references to nonexistent nodes.

Actions:

- append `sharedUids` to `.dsp/<exporterUid>/shared`,
- ensure `.dsp/<exporterUid>/exports/` exists,
- for each `sharedUid`, ensure `.dsp/<exporterUid>/exports/<sharedUid>/description` exists — if the file is created for the first time, `description` is auto-filled from the `purpose` of the shared entity (if it already exists in `.dsp`).

#### 5.4. `addImport(importerUid, importedUid, exporterUid?, why)`

All referenced UIDs (`importerUid`, `importedUid`, and `exporterUid` if given) must exist in `.dsp` — this keeps the graph closed (§8.5). For an external dependency, create its Object (`kind: external`) first.

Actions:

- append `importedUid` (and optionally `via=exporterUid`) to `.dsp/<importerUid>/imports`,
- write the reverse feedback “why we import” **into `exports` of the imported entity**:
  - if importing a **shared entity** and `exporterUid` is known:
    - create/update `.dsp/<exporterUid>/exports/<importedUid>/<importerUid>` with text `why`,
  - otherwise (importing the **Object as a whole** — local module, external package/submodule, side-effect import, etc.):
    - ensure `.dsp/<importedUid>/exports/` exists,
    - create/update `.dsp/<importedUid>/exports/<importerUid>` with text `why`.

**When one `addImport` call is enough vs when you need two:**

You need two calls when importing **both the whole module (or as a namespace) and a specific symbol from it**. One call is enough when only one of those happens.

```js
// Example 1: namespace import + named import from the same module
import * as utils from './utils';     // → addImport(thisUid, utilsObjUid, why="formatting utilities")
import { calc } from './utils';       // → addImport(thisUid, calcUid, utilsObjUid, why="total calculation")
// Total: 2 addImport calls

// Example 2: named import only
import { UserService } from './services';
// → addImport(thisUid, userServiceUid, servicesObjUid, why="user management")
// Total: 1 call (to the shared entity, exporter provided via exporterUid)

// Example 3: side-effect import (no specific symbol)
import './polyfills';
// → addImport(thisUid, polyfillsObjUid, why="browser polyfills")
// Total: 1 call (to the whole Object)

// Example 4: default import
import express from 'express';
// → addImport(thisUid, expressObjUid, why="HTTP framework")
// Total: 1 call (to the whole Object, external)
```

---

#### Update operations

#### 5.5. `updateDescription(uid, fields)`

Update the description of an existing entity. Typical scenarios: the purpose of a module changed, the file path changed (rename/move), the description was refined after refactoring, or a root's `scope` is being set/changed.

Validation:

- `kind` must be one of `object` / `function` / `external`, and must stay consistent with the UID prefix: a `func-` entity is always `function`; an `obj-` entity can be `object` or `external`, never `function`,
- `scope` is accepted **only for root entities** (TOC[0] of some TOC file) and is normalized (backslashes → `/`, trailing slashes stripped, `.` = whole repo).

Actions:

- read `.dsp/<uid>/description`,
- update specified fields (`source:`, `purpose:`, `kind:`, `scope:`, freeform sections); untouched fields (including freeform `notes:` etc.) are preserved,
- write back `.dsp/<uid>/description`.

#### 5.6. `updateImportWhy(importerUid, importedUid, exporterUid?, newWhy)`

Update the reason for an import (the `why` text). Typical scenario: a module still imports a dependency, but uses it for a different purpose.

Actions:

- locate the feedback file in `exports`:
  - if `exporterUid` is provided: `.dsp/<exporterUid>/exports/<importedUid>/<importerUid>`,
  - otherwise: `.dsp/<importedUid>/exports/<importerUid>`,
- overwrite the file contents with `newWhy`.

#### 5.7. `moveEntity(uid, newSourceRef)`

The entity moved (file rename/move). UID stays the same; only the source reference changes.

Actions:

- update `source:` in `.dsp/<uid>/description` to `newSourceRef`.

> This is a special case of `updateDescription`, separated for clarity: the UID **does not change** on moves.

---

#### Delete operations

#### 5.8. `removeImport(importerUid, importedUid, exporterUid?)`

Remove an import relationship. Typical scenario: an `import` was removed from code.

Matching is **exact on the exporter**: without `exporterUid` only a plain line (no `via=`) is removed; with `exporterUid` only the line `importedUid via=<exporterUid>`. This mirrors `addImport` — the two link kinds are distinct edges with reverse records in different places, and removing one by the other's call would desync `imports` from `exports/`.

Actions:

- remove the matching line from `.dsp/<importerUid>/imports`,
- delete the feedback file from `exports`:
  - if `exporterUid` is provided: delete `.dsp/<exporterUid>/exports/<importedUid>/<importerUid>` (and the now-empty `<importedUid>/` directory, if nothing else remains in it),
  - otherwise: delete `.dsp/<importedUid>/exports/<importerUid>`,
- if **neither** the import line **nor** the feedback file existed — fail with a hint to pass (or drop) `--exporter`.

#### 5.9. `removeShared(exporterUid, sharedUid)`

The entity is no longer exported. Typical scenario: `export` was removed from code.

Actions:

- remove `sharedUid` from `.dsp/<exporterUid>/shared`,
- delete the directory `.dsp/<exporterUid>/exports/<sharedUid>/` with all recipient files,
- for each recipient (former files under `exports/<sharedUid>/`) — remove `sharedUid` from their `imports`.

#### 5.10. `removeEntity(uid)`

Remove an entity from DSP completely. Typical scenario: a file/module was deleted from the project.

Actions:

1. **Full imports scan**: for each entity in `.dsp` — remove from `imports` all lines where `uid` appears as `imported` or as a `via=` target. This covers direct imports, shared-imports via `uid`, owner links — everything in one pass.
2. **Full reverse-index sweep**: for each other entity, remove every trace of `uid` from its `exports/`:
   - the file `exports/<uid>` (`uid` imported that entity as a whole),
   - the directory `exports/<uid>/` (`uid` was exported via that entity — swept even if `uid` is missing from its `shared`, so nothing dangles when shared registration was skipped),
   - the file `exports/<sharedUid>/<uid>` for every shared subdirectory (`uid` imported that shared entity); a subdirectory left completely empty is removed.
   A sweep (rather than a targeted cleanup driven by `uid`'s own `imports`/`shared`) guarantees zero dangling references even on a partially desynced graph.
3. **Clean shared lists**: remove `uid` from every entity’s `shared` file where it appears.
4. Remove `uid` from **all** TOC files. If `uid` was a root with its own `.dsp/TOC-<uid>` file, delete that file entirely.
5. Delete the `.dsp/<uid>/` directory entirely.

---

#### Read operations (single entity)

#### 5.11. `getEntity(uid) -> EntityInfo`

Get a full snapshot of an entity. Basic operation — an entry point for any analysis of a specific module.

Returns:

- `description` (source, kind, purpose, notes),
- `imports[]` — list of dependency UIDs,
- `shared[]` — list of exported entity UIDs (for Objects),
- `exportedTo[]` — list of recipients from `exports/` (who imports it and why).

Implementation: read files from `.dsp/<uid>/`.

#### 5.12. `getShared(uid) -> SharedInfo[]`

Get the public API of an entity — what it makes available externally and who uses it. Typical scenario: an agent needs to understand what can be imported from a module/class/function.

Returns for each shared UID:

- description (from `.dsp/<uid>/exports/<sharedUid>/description`),
- list of recipients with reasons (files under `.dsp/<uid>/exports/<sharedUid>/`).

#### 5.13. `getRecipients(uid) -> RecipientInfo[]`

Get everyone who imports this entity, and why. Typical scenario: impact analysis — who will be affected by changes in this module.

Returns: a list of pairs `(recipientUid, why)`.

Implementation: the importer set is served by the persistent reverse-index cache (§4.5) and the `why` of each edge is read live from `exports/`. The set covers three kinds of edges (deduplicated by UID), each of which names `uid` as the first token of an `imports` line:

1. **Direct recipients**: `why` from `.dsp/<uid>/exports/<importerUid>` (direct imports via `addImport` without `exporter`).
2. **Via shared exporters**: if `uid` is imported with an `exporter`, `why` from `.dsp/<exporterUid>/exports/<uid>/<importerUid>`.
3. **Owner / plain-imports edges**: any entity that names `uid` in its `imports` (e.g., an owner relationship) — covered by the same index.

---

#### Graph traversal operations

#### 5.14. `getChildren(uid, depth?) -> Tree`

Get the dependency tree **downwards** — what this entity imports (and what its dependencies import, etc.). Typical scenarios: understand what a module consists of, which libraries it pulls in.

Parameters:

- `uid` — starting point,
- `depth` — traversal depth (default `1` — direct imports only; `Infinity` — full tree).

Returns: a tree of nodes `{ uid, description.purpose, children[] }`.

Implementation: recursive reading of `imports` with a `visited` set to guard against cycles.

#### 5.15. `getParents(uid, depth?) -> Tree`

Get the dependency tree **upwards** — who imports this entity (and who imports those, etc.). Typical scenarios: understand blast radius, find all entry points that use this code.

Parameters:

- `uid` — starting point,
- `depth` — traversal depth (default `1` — direct recipients only; `Infinity` — up to the root(s)).

Returns: a tree of nodes `{ uid, description.purpose, why, parents[] }`.

Implementation: recursive walk of reverse edges (served by the reverse-index cache, §4.5) with a `visited` set.

#### 5.16. `getPath(fromUid, toUid) -> uid[] | null`

Find the shortest path between two entities in the graph (in any direction along `imports` edges). Typical scenario: understand how two modules are connected to each other.

Returns: an ordered list of UIDs from `fromUid` to `toUid`, or `null` if no path exists.

Implementation: BFS over the graph in both directions — forward via `imports`, reverse via the reverse-index cache (§4.5). The cache is what keeps the per-node reverse lookup O(1) instead of an O(N) scan, so BFS does not degrade to O(N²).

---

#### Search and discovery operations

#### 5.17. `search(query) -> SearchResult[]`

Full-text search across `.dsp`. Typical scenarios: find a module by a keyword (“authentication”, “routing”, “cache”), find entities related to a specific file.

Searches for matches in:

- `description` (purpose, source, notes),
- file names under `exports/` (recipient UIDs).

Returns: a list `{ uid, matchContext }` — the UID and the fragment where the match was found.

Implementation: `grep -r "query" .dsp/` over `description` files.

#### 5.18. `findBySource(sourcePath) -> uid[]`

Find entities by a source file path. Typical scenario: an agent sees a file in code and wants its DSP representation.

Returns a **list** of UIDs, because one file may contain multiple entities (the module Object + shared functions/classes inside). Matching: exact by `source:` or by the `sourcePath#` prefix (for entities inside a file).

Implementation: search for `source:` across all `.dsp/*/description`.

#### 5.19. `readTOC() -> uid[]`

Read the project table of contents. Entry point for getting familiar with the project: TOC[0] is the root, then all other entities in documentation order.

Implementation: read `.dsp/TOC`.

---

#### Diagnostics operations

#### 5.20. `detectCycles() -> uid[][]`

Detect cyclic dependencies in the `imports` graph. Typical scenario: project audit, finding architectural issues.

Returns: a list of cycles; each cycle is an array of UIDs forming a closed path.

#### 5.21. `getOrphans() -> uid[]`

Find “orphan” entities — those that nobody uses except the root. Typical scenario: find dead code and unused modules.

An entity is **not** considered an orphan if at least one of the following holds:

- it is a root (the first UID in any TOC),
- it appears in `imports` of any other entity (as `imported` or as a `via=` target),
- its `exports/` is non-empty (there is at least one recipient).

Implementation: collect the set of all UIDs appearing in imports (including `via=` targets), then for the remaining ones check `exports/`.

#### 5.22. `getStats() -> ProjectStats`

Overall statistics for the DSP graph. Typical scenario: quick orientation in the scale of the project.

Returns:

- total number of entities (Object / Function / External),
- number of edges (imports),
- number of shared entities,
- number of cycles (if any),
- number of orphans.

---

#### TOC membership operations

#### 5.23. `addToToc(uids[], tocs[])`

Add **existing** entities to one or more TOCs, single or batch. Typical scenarios: an external dependency registered under root A turns out to be used by root B as well; an entity should appear in an additional root's map.

CLI: `dsp-cli add-to-toc <uid> [<uid> ...] --toc <TOC> [--toc <TOC> ...]` where `<TOC>` is a root UID or `default`.

Actions:

- validate that every `uid` exists and every target TOC file exists,
- append each `uid` to each target TOC (idempotent — a UID already present in a TOC is reported and left in place, never duplicated).

#### 5.24. `moveToToc(uids[], fromToc, toToc)`

Transfer entities from one TOC to another, single or batch. Typical scenarios: a module migrated between subprojects of a monorepo; an entity was indexed into the wrong root's map.

CLI: `dsp-cli move-to-toc <uid> [<uid> ...] --from <TOC> --to <TOC>`.

Validation (the whole batch is checked **before** anything is written — all-or-nothing):

- `fromToc` ≠ `toToc`, both TOC files exist, every `uid` exists,
- every `uid` is present in `fromToc`,
- no `uid` is the **root** of `fromToc` (TOC[0] cannot be moved out of its own TOC — the root defines the TOC).

Actions:

- remove each `uid` from `fromToc`,
- append each `uid` to the end of `toToc`; if it is already there, only the removal happens (reported as “already in target”).

> Only TOC membership changes. The entity itself, its imports/shared/exports edges, and its membership in other TOCs are untouched.

---

#### Maintenance operations

#### 5.25. `rebuildCache()`

Rebuild the persistent reverse-index cache (§4.5) from scratch. Idempotent.

Typical scenario: `.dsp/` was changed **outside** the CLI — hand-edited files, or a `merge`/`rebase` that touched `.dsp/` — so the incremental cache cannot see those changes. Normal CLI mutations keep the cache current, so this is rarely needed.

Actions:

- delete `.dsp/.cache/` entirely,
- scan the forward `imports` of every entity and rebuild `rev/<imported>` for each imported UID (direct, via-exporter, and owner edges all count),
- write the `built` sentinel.

CLI: `dsp-cli rebuild-cache` — prints the number of imported entities indexed.

### 6) Bootstrap (initial mapping)

#### Algorithm (three waves over fixed batches, after root discovery)

Bootstrap is **not** a graph traversal. It is three flat passes over the project's file list, executed by **parallel subagents over fixed file batches**. The core economy rule: **each file is read exactly once, by exactly one subagent** — all three waves run on top of that single read, so token cost ≈ one pass over the codebase regardless of the number of waves.

```
Phase 0:    discover roots                 →  createObject(..., newRoot, scope)  — one TOC per root
Inventory:  list all files + sizes         →  batches per TOC, balanced by volume;
                                              1 batch = 1 subagent
Wave 1:     subagent reads its batch ONCE  →  createObject / createFunction      — every file becomes an entity
Wave 2:     same subagent, same read       →  createShared                       — public API of every file
─────────── barrier: ALL batches done; orchestrator registers externals once ───────────
Wave 3:     same subagent, same read       →  addImport                          — every dependency edge
```

**Phase 0. Discover roots (TOCs)** — orchestrator:

- identify entrypoints — by default auto-detect via the LLM (package.json `main`, framework entrypoint, `main.py`, etc.), or specify manually,
- decide each root's **scope** — the directory subtree it covers (`.` for the whole repo, `backend` / `frontend` for a monorepo),
- `createObject(rootPath, purpose + project overview, newRoot, scope)` per root — each gets its own `TOC-<rootUid>`,
- thanks to scopes, the waves never pass TOC arguments: every created entity is auto-assigned to all TOCs whose root scope covers its path (§5.1).

**Inventory and batching** — orchestrator, before any file content is read:

- list **every** project file with its content volume (respect `.gitignore`; exclude vendored code, build output, lock files, `.dsp/`),
- group files by TOC (root scopes); a batch never mixes TOCs,
- split each group into batches of roughly **equal total volume** (not file count) — a batch must fit in one subagent's context; equal volume means subagents finish together,
- dispatch one subagent per batch, all in parallel.

**Wave 1. Index all files** — each subagent over its batch:

- **read each file once — the only read in the whole bootstrap**; while reading, capture purpose, inner entities, exports, and each import with its usage sites,
- `createObject(path, purpose)`; for each significant inner entity (exported function/class) — `createFunction(path#symbol, purpose, ownerUid)`; place `@dsp <uid>` markers in source,
- checkpoint per batch: every file resolves via `findBySource`; an interrupted batch is re-dispatched (skip already-indexed files).

**Wave 2. Index all exports** — same subagent, no re-reading:

- per file: `createShared(objUid, memberUids)` — exports are batch-local, so no cross-batch synchronization is needed; a subagent proceeds right after its own Wave 1.

**Barrier** — Wave 3 references entities across batches, so it starts **only after every batch completed Waves 1–2**. At the barrier each subagent reports the externals its batch imports (known from the Wave 1 read); the orchestrator dedupes and registers each external **once**: `createObject(pkg, purpose, kind: external)` + `addToToc(extUid, rootToc)` for every other root using it. **Never descend inside externals.**

**Wave 3. Index all imports** — same subagent, still no re-reading:

- each import was already **verified alive** at the Wave 1 read (the symbol is used in the file body — dead imports are removed from code, not registered),
- resolve local targets via `findBySource` (no file reading; everything exists after Wave 1), then `addImport(thisUid, importedUid, why, exporterUid?)` with a usage-based `why`,
- external targets already exist — only edges are added.

**Verification:** `getStats`, `getOrphans` (unreferenced files are expected for scripts/configs — review the rest), `detectCycles`, spot-check `readTOC` per root; every inventory file resolves via `findBySource`.

**Re-indexing:** if `.dsp/` is rebuilt while the code still carries `@dsp` markers, collect them via grep and pass each old UID through the `uid` parameter of `createObject`/`createFunction` — the graph is rebuilt with stable UIDs and markers stay valid.

**Key rules:**

- Phase 0 strictly first — roots and scopes must exist before Wave 1 so files have TOCs to land in.
- One file — one subagent — one read; all waves run on top of that read. A subagent that cannot survive the barrier persists a compact per-file digest (purpose, exports, imports with usage evidence) so Wave 3 works from the digest, not from sources.
- No subagents available → the same plan runs sequentially with per-file digests; each file is still read only once.
- After Wave 3, each TOC contains the complete ordered list of its root's zone — including files not (yet) reachable through imports; `getOrphans` reveals them.

**Why flat waves:** every entity exists before the first `addImport` (no missing-UID failures, no creating targets mid-pass); batches are independent, so the work parallelizes up to the number of subagents and resumes from the inventory; coverage is complete — every project file is indexed, including those not reachable through imports.

### 7) UID: stability and “versioning”

#### 7.1. Invariants

- UID must not depend on the file path.
- UID must survive:
  - rename/move,
  - code rearrangement,
  - formatting,
  - small implementation changes.

#### 7.2. UID change policy

A new UID is created only if an entity **changes its purpose** (semantic identity), for example:

- a module/class/function started solving a _different_ problem,
- the entity was “reborn” (the old one was replaced with different logic while keeping the name).

In all other cases, update descriptions/links and keep the UID.

#### 7.3. UID for entities inside a file (comment marker)

Separate identity between “file as an Object” and “entities inside a file”:

- **File as an Object**: `uid = obj-<uuid>`, `source: <filePath>`.
- **Entities inside a file** (shared functions, shared objects, exported classes): their own `uid = obj-<uuid>` or `func-<uuid>`, anchored to code via a **comment marker** `@dsp <uid>` before the declaration.

Example (TypeScript):

```ts
// @dsp func-7f3a9c12
export function calculateTotal(items: Item[]): number { ... }

// @dsp obj-b4e82d01
export class OrderService { ... }
```

Example (Python):

```python
# @dsp func-3c19ab8e
def process_payment(order):
    ...
```

**Why a comment, not a line-number binding:**

- you can **instantly find the UID in code** via `grep "@dsp func-7f3a9c12"`,
- it does not depend on line numbers, formatting, code rearrangement,
- it does not require renaming symbols — names stay clean,
- it works for any language (every language has comments).

`sourceRef` in `description` is stored as `source: <filePath>#<uid>`.

> The source of truth is `.dsp`: after a file rename/move it is enough to update `source:` in `description` without changing the UID.

### 8) Special cases

#### 8.1. Cyclic dependencies

- the tool must be able to detect cycles in the `imports` graph,
- traversal must be resilient to cycles,
- cycles are diagnostic information (not fatal), but must be recorded.

#### 8.2. Re-export (barrel exports)

- one shared UID may be available from multiple exporters,
- the `exports index` is maintained **per exporter**, because the LLM must understand “where it is usually imported from”.

#### 8.3. Code generation by an agent

When an agent (LLM) writes new code, it **simultaneously calls DSP operations** to register the created entities:

- created a new module → `createObject`,
- created a function → `createFunction`,
- added an export → `createShared`,
- added an import → `addImport`.

DSP is updated **during code generation**, not after the fact.

#### 8.4. Dynamic imports

- Dynamic dependencies (e.g., `import()` in JS, `importlib` in Python) are recorded as normal `imports` when discovered.
- If a dynamic import cannot be determined statically — it is added to DSP upon first execution/discovery.

#### 8.5. External dependencies (libraries, SDKs, stdlib)

DSP works with any data and codebases. At the same time, **DSP does not dive into external dependencies** — it only records the fact of import:

- An external import is represented as an `Object` with `kind: external` in `description`.
- `description` records: package/module/version and purpose (why it is imported).
- **The internal structure of the library is not analyzed.** For example: in Node.js — do not go into `node_modules`; in Python — do not go into `site-packages`; in Go — do not go into `vendor`/module cache; etc.
- The `exports index` **is maintained** — you can see who imports this library and why. This allows you to immediately get the list of all recipients when updating/replacing a dependency.

This keeps the graph closed (all links point to existing UIDs) and fully navigable, without inflating `.dsp` with descriptions of third-party internals.

### 9) LLM integration: contract and navigation

Two logical components work with DSP:

- **DSP Builder** — a tool (script/agent) that builds and updates `.dsp`. It calls operations from §5 and maintains graph integrity.
- **LLM Orchestrator** — an agent (LLM) that uses `.dsp` as project memory. It reads TOC, searches entities, expands the relationship graph, and builds context for code generation.

**DSP Builder** is responsible for:

- building `.dsp` (bootstrap and ongoing updates),
- graph integrity,
- minimal, precise descriptions of entities and dependency reasons.

**LLM Orchestrator** is responsible for:

- selecting relevant UIDs for a task,
- building “context bundles”:
  - `description` of the target entities,
  - their `imports` (+ transitive dependencies if needed),
  - `shared` and the `exports index` to understand API and usage patterns,
- passing strictly limited sections into the model — without overloading the context.

#### 9.1) Navigation and search in `.dsp`

An agent can find required modules and entities in several ways:

**Via TOC:**

- Read `.dsp/TOC` → get the full UID list → read `description` of the required entities.

**Via grep/search over files, including the `.dsp` directory:**

- Search `description` files — find entities by keywords, purpose, source path.
- Search `imports` — find dependencies of a specific entity.
- Search `exports/` — find all recipients (who uses a given entity and why).

### 10) Granularity and minimal-context policy

- **Completeness at the file level, not at the code-within-file level.** “Import completeness” (§2) means every **file/module** that is imported in the project must have an Object in `.dsp`. This is about files and modules — not about every variable inside a file. Within one file, a separate UID is assigned only to an entity that is **shared outward** (`shared`) or **used from multiple places**. Local variables, internal helpers, private fields — remain part of the parent Object, without their own UID. If granularity keeps growing, something is wrong.

- **Update recipients via `exports`.** To update a library/module/symbol, it is enough to open `exports` of the imported entity and get the list of importers (recipients) by UID, then update them precisely.

- **Change tracking.** `git diff` shows what changed — a new file was created, a function or an object changed. Changed files are fed to the LLM to update DSP. Changes inside functions often do not require DSP updates, because the description captures *purpose*, not implementation details — unless imports were added/removed.

