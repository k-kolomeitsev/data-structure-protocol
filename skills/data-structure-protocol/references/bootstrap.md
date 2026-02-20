# DSP Bootstrap Procedure

## Table of Contents

- [Overview](#overview)
- [Algorithm](#algorithm)
- [Step-by-Step](#step-by-step)
- [Visual Example](#visual-example)
- [Key Rules](#key-rules)

## Overview

Bootstrap is a DFS (depth-first search) traversal of dependencies from root entrypoint(s). Each reachable file gets documented as an entity in `.dsp/`. For each root — a separate TOC file.

## Algorithm

### Step 1: Identify Root Entrypoint(s)

- Auto-detect via LLM: `package.json` main, framework entry, `main.py`, `cmd/main.go`, etc.
- Or specify manually.
- Multiple roots → separate bootstrap per root, each with its own `TOC-<rootUid>`.

### Step 2: Document the Root File Completely

```
createObject(rootPath, rootPurpose)          → rootUid (first in TOC)
createFunction(path#symbol, purpose, rootUid) → funcUid (for each function)
createShared(rootUid, [funcUid, ...])         (for exports)
addImport(rootUid, importedUid, why)          (for each import)
createObject(pkgName, purpose, kind=external) (for external deps, add to TOC but don't descend)
```

**Root's description must include a brief project overview.**

### Step 3: Take First Non-External Import

From the current file's imports, pick the first one that is NOT an external dependency (not a library, not `node_modules`, not stdlib). Document it fully (same as Step 2). Add its UID to TOC.

### Step 4: Recursive Descent

From the just-documented file, take its first non-external import:
- If exists → document it, repeat Step 4 (go deeper).
- If none → **backtrack** to the previous level, take the next unprocessed non-external import.

### Step 5: Repeat Until Complete

Continue until all reachable non-external files are documented.

## Visual Example

```
root (document)
 ├─ import_A (local → document)
 │   ├─ import_A1 (local → document)
 │   │   └─ ... (descend deeper)
 │   ├─ import_A2 (external → record kind:external, DON'T descend)
 │   └─ import_A3 (local → document)
 │       └─ ... no local imports → backtrack
 ├─ import_B (local → document)
 │   └─ ...
 └─ import_C (external → record kind:external, DON'T descend)
```

## Key Rules

- Maintain a `visited` set by UID/sourceRef — no infinite recursion.
- External dependencies: `createObject(..., kind=external)` + add to TOC, but **never analyze their internals** (no `node_modules`, no `site-packages`, no `vendor`).
- After traversal, the TOC file contains a complete ordered list of all project entities.
- One file may contain multiple entities (Object + shared Functions) — all get separate UIDs.
- Place `@dsp <uid>` comment markers in source code before each entity declaration.
