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
> 7. **Bootstrap** — if `.dsp/` is empty, traverse the project from the root entrypoint downwards (DFS over imports), documenting every file.
>
> **Key commands:**
> ```
> dsp-cli init
> dsp-cli create-object <source> <purpose> [--kind external] [--toc ROOT_UID]
> dsp-cli create-function <source> <purpose> [--owner UID] [--toc ROOT_UID]
> dsp-cli create-shared <exporter_uid> <shared_uid> [<shared_uid> ...]
> dsp-cli add-import <importer_uid> <imported_uid> <why> [--exporter UID]
> dsp-cli remove-import <importer_uid> <imported_uid> [--exporter UID]
> dsp-cli remove-shared <exporter_uid> <shared_uid>
> dsp-cli remove-entity <uid>
> dsp-cli move-entity <uid> <new_source>
> dsp-cli update-description <uid> [--source S] [--purpose P] [--kind K]
> dsp-cli get-entity <uid>
> dsp-cli get-children <uid> [--depth N]
> dsp-cli get-parents <uid> [--depth N]
> dsp-cli search <query>
> dsp-cli find-by-source <path>
> dsp-cli read-toc [--toc ROOT_UID]
> dsp-cli get-stats
> ```

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
- **Start from roots.** Each root is a separate entrypoint with its own TOC file. By default, roots are auto-detected via the LLM; if needed, they are specified manually. Imports are traversed depth-first from each root.
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
- Next — all entities reachable from that root, in documentation order (traversal order during bootstrap).
- Each UID appears in a given TOC **exactly once**.
- The same entity **may** be in multiple TOCs (if reachable from multiple roots).
- When documenting new entities — append them to the end of the corresponding TOC.

**Purpose:**

- A complete overview of all entities reachable from a given root.
- Lets the LLM start navigation from the right entrypoint and dive into its structure.
- In multi-root projects (monorepo, multiple applications), each TOC is an independent map of its subtree.

### 5) Operations (tooling-level API)

Below are the operations used by the `.dsp` generator.

#### 5.0. `init`

Initialize the `.dsp/` directory at the project root. Required first step before any operations. Idempotent — repeated calls are safe.

CLI: `dsp-cli init`

#### 5.1. `createObject(sourceRef, purpose, kind?) -> objUid`

Parameters:

- `sourceRef` — path to source (+ symbol if applicable),
- `purpose` — purpose,
- `kind` — `object` (default) or `external` (for external dependencies).

Actions:

- generate/resolve `objUid` (stably),
- create `.dsp/<objUid>/`,
- write `.dsp/<objUid>/description` (source, kind, purpose),
- create `.dsp/<objUid>/imports` if missing (empty),
- if needed — `.dsp/<objUid>/shared` (empty),
- **append `objUid` to `.dsp/TOC`**.

#### 5.2. `createFunction(sourceRef, purpose, ownerUid?) -> funcUid`

Actions:

- generate/resolve `funcUid` (stably),
- create `.dsp/<funcUid>/`,
- write `.dsp/<funcUid>/description`,
- create `.dsp/<funcUid>/imports` (empty),
- if `ownerUid` is provided:
  - append `funcUid` to the owner object’s `imports` (so the object “sees” its methods),
  - create a reverse record `.dsp/<funcUid>/exports/<ownerUid>` (so `getParents` can find the owner without a full scan),
- **append `funcUid` to `.dsp/TOC`**.

> Function ownership is determined through the owner’s `imports`. Reverse lookup — through `getParents(funcUid)`. A standalone function (without an owner) is simply added to a module’s `shared` if it is exported.

#### 5.3. `createShared(exporterUid, sharedUids[])`

Actions:

- append `sharedUids` to `.dsp/<exporterUid>/shared`,
- ensure `.dsp/<exporterUid>/exports/` exists,
- for each `sharedUid`, ensure `.dsp/<exporterUid>/exports/<sharedUid>/description` exists — if the file is created for the first time, `description` is auto-filled from the `purpose` of the shared entity (if it already exists in `.dsp`).

#### 5.4. `addImport(importerUid, importedUid, exporterUid?, why)`

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

Update the description of an existing entity. Typical scenarios: the purpose of a module changed, the file path changed (rename/move), or the description was refined after refactoring.

Actions:

- read `.dsp/<uid>/description`,
- update specified fields (`source:`, `purpose:`, `kind:`, freeform sections),
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

Actions:

- remove `importedUid` from `.dsp/<importerUid>/imports`,
- delete the feedback file from `exports`:
  - if `exporterUid` is provided: delete `.dsp/<exporterUid>/exports/<importedUid>/<importerUid>`,
  - otherwise: delete `.dsp/<importedUid>/exports/<importerUid>`.

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
2. **Clean outgoing links**: read `.dsp/<uid>/imports` — for each imported entity, delete the feedback file from its `exports/`.
3. **Clean shared references in exporters**: for each entity — if `uid` appears in someone’s `shared`, remove `uid` from `.dsp/<exporterUid>/shared` and delete `.dsp/<exporterUid>/exports/<uid>/`.
4. Remove `uid` from **all** TOC files.
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

Implementation — a three-level search (each level complements the previous, with UID deduplication):

1. **Direct recipients**: files under `.dsp/<uid>/exports/` (direct imports via `addImport` without `exporter`).
2. **Via shared exporters**: if `uid` is present in someone’s `shared`, read files under `.dsp/<exporterUid>/exports/<uid>/` (imports via `addImport` with `exporter`).
3. **Imports fallback**: scan all entities — if `uid` is found in someone’s `imports` (e.g., owner relationship) but wasn’t discovered at previous levels.

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

Implementation: recursive reading of `exports/` with a `visited` set.

#### 5.16. `getPath(fromUid, toUid) -> uid[] | null`

Find the shortest path between two entities in the graph (in any direction along `imports` edges). Typical scenario: understand how two modules are connected to each other.

Returns: an ordered list of UIDs from `fromUid` to `toUid`, or `null` if no path exists.

Implementation: BFS over the `imports` graph (bidirectional — via `imports` and `exports`).

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

### 6) Bootstrap (initial mapping)

#### Algorithm (depth-first traversal)

Bootstrap is a simple DFS traversal of dependencies starting from a root file. **For each root entrypoint**, bootstrap is executed separately with its own TOC file.

**Step 1. Identify root entrypoint(s):**

- by default — auto-detect via the LLM (package.json `main`, framework entrypoint, etc.),
- or specify manually,
- if there are multiple roots — run bootstrap for each, creating a separate TOC (`TOC-<rootUid>`).

**Step 2. Fully document the root file:**

- `createObject` for the module (UID is written to TOC **first**),
- extract functions → `createFunction` for each (with ownerUid pointing to this Object),
- extract `shared` (exports/public API) → `createShared`,
- extract all `imports` → `addImport`,
- external dependencies from imports → `createObject(..., kind: external)` (append to TOC, but do not descend).

**Step 3. Take the first import from the current file that is NOT an external dependency** (not a library, not node_modules, not stdlib):

- document it fully (same as Step 2),
- append its UID to TOC.

**Step 4. Recursive descent:**

- from the just-documented file, take the first non-library import,
- if it exists — document it and repeat Step 4,
- if **none exist** — **go up one level** and take the next unprocessed non-library import.

**Step 5.** Repeat until all reachable non-library files are documented.

**Visually:**

```
root (document)
 ├─ import_A (non-library → document)
 │   ├─ import_A1 (non-library → document)
 │   │   └─ ... (descend deeper)
 │   ├─ import_A2 (external → record kind: external, DO NOT descend)
 │   └─ import_A3 (non-library → document)
 │       └─ ... no non-library imports → backtrack
 ├─ import_B (non-library → document)
 │   └─ ...
 └─ import_C (external → record kind: external, DO NOT descend)
```

**Key rules:**

- Traversal uses a `visited` set by UID/sourceRef — **no infinite recursion**.
- External dependencies are recorded as Objects with `kind: external`, but their internal structure **is not analyzed**.
- After traversal completes, `.dsp/TOC` contains a complete ordered list of all project entities.

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

