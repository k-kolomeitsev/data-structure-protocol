# DSP Operations Reference

## Table of Contents

- [Create Operations](#create-operations)
- [Update Operations](#update-operations)
- [Delete Operations](#delete-operations)
- [Read Operations](#read-operations)
- [Graph Traversal](#graph-traversal)
- [Search and Discovery](#search-and-discovery)
- [Diagnostics](#diagnostics)
- [Import Patterns](#import-patterns)

## Create Operations

### createObject (§5.1)

```
dsp-cli create-object <source> <purpose> [--kind external] [--toc ROOT_UID]
```

Creates an Object entity (module, class, config, external dep).

Actions:
1. Generate `obj-<8hex>` UID
2. Create `.dsp/<uid>/` with `description`, empty `imports`, empty `shared`
3. Append UID to TOC

### createFunction (§5.2)

```
dsp-cli create-function <source> <purpose> [--owner UID] [--toc ROOT_UID]
```

Creates a Function entity.

Actions:
1. Generate `func-<8hex>` UID
2. Create `.dsp/<uid>/` with `description`, empty `imports`
3. If `--owner` specified:
   - Add funcUid to owner's `imports` (object "sees" its methods)
   - Create `.dsp/<funcUid>/exports/<ownerUid>` with "owner: method/member"
4. Append UID to TOC

### createShared (§5.3)

```
dsp-cli create-shared <exporter_uid> <shared_uid> [<shared_uid> ...]
```

Register entities as exported/public from an object.

Actions:
1. Append each shared_uid to `.dsp/<exporter>/shared`
2. Create `.dsp/<exporter>/exports/<shared_uid>/description` (auto-filled from entity's purpose)

### addImport (§5.4)

```
dsp-cli add-import <importer_uid> <imported_uid> <why> [--exporter UID]
```

Record an import relationship.

Actions:
1. Append `imported_uid [via=exporter]` to importer's `imports`
2. Write reverse link:
   - With `--exporter`: `.dsp/<exporter>/exports/<imported_uid>/<importer_uid>` = why
   - Without: `.dsp/<imported_uid>/exports/<importer_uid>` = why

## Update Operations

### updateDescription (§5.5)

```
dsp-cli update-description <uid> [--source S] [--purpose P] [--kind K]
```

Update specific fields in entity's description. Unspecified fields remain unchanged.

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
2. Clean outgoing links — remove reverse entries in other entities' `exports/`
3. Clean shared references — remove from any exporter's `shared` + delete `exports/<uid>/`
4. Remove uid from all TOC files
5. Delete `.dsp/<uid>/` directory

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

All importers of this entity (three-level search: direct, via shared exporters, fallback by imports scan).

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
