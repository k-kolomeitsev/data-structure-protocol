# Brownfield Workflow — Adding a Feature with DSP (Codex)

A realistic walkthrough of using DSP when working on an existing codebase with OpenAI Codex.

`dsp-cli` is shorthand for `python <skill-path>/scripts/dsp-cli.py --root .`.

## Scenario

You have an e-commerce project with DSP already bootstrapped. You ask Codex to add a "wishlist" feature.

## Prerequisites

- DSP skill installed in `.codex/skills/data-structure-protocol/`
- DSP initialized (`.dsp/` exists with registered entities)

## Step 1: Understand the Existing Structure

You prompt Codex:

> Add a wishlist feature. Users should be able to save products and view their wishlist.

Codex uses the DSP skill to understand the project first:

```bash
dsp-cli read-toc
```

Output:

```
obj-1a2b3c4d [root]
obj-5e6f7a8b
obj-9c0d1e2f
obj-3a4b5c6d
```

Codex reads the descriptions of these entities (`get-entity`) and learns the layout: `obj-1a2b3c4d` is the products module, `obj-5e6f7a8b` — auth, `obj-9c0d1e2f` — cart, `obj-3a4b5c6d` — database layer.

## Step 2: Find Related Entities

Codex searches for product and user-related entities:

```bash
dsp-cli search "product"
dsp-cli search "user"
```

Then inspects the product module for its public API:

```bash
dsp-cli get-entity obj-1a2b3c4d
dsp-cli get-children obj-1a2b3c4d
```

This reveals `obj-1a2b3c4d` has a shared export `func-ab12cd34` (`ProductService`) and child functions like `getProductById`.

## Step 3: Check Impact Before Changes

Codex checks who depends on the product module:

```bash
dsp-cli get-parents obj-1a2b3c4d
dsp-cli get-recipients obj-1a2b3c4d
```

The cart module already imports from products — Codex follows the same pattern for the wishlist.

## Step 4: Implement the Feature

Codex creates the wishlist module files:

- `src/wishlist/wishlist.service.ts`
- `src/wishlist/wishlist.controller.ts`
- `src/wishlist/wishlist.repository.ts`

## Step 5: Register New Entities in DSP

```bash
# Register the wishlist module
dsp-cli create-object src/wishlist/ \
  "Wishlist module — save and manage favorite products per user"
# → obj-aa11bb22

# Register the service function
dsp-cli create-function src/wishlist/wishlist.service.ts \
  "Wishlist business logic — add, remove, list saved products" \
  --owner obj-aa11bb22
# → func-cc33dd44
```

## Step 6: Record Dependencies

```bash
# Wishlist depends on ProductService
dsp-cli add-import obj-aa11bb22 obj-1a2b3c4d \
  "uses ProductService to validate product existence"

# Wishlist depends on Database layer
dsp-cli add-import obj-aa11bb22 obj-3a4b5c6d \
  "persists wishlist items"

# Wishlist depends on Auth module
dsp-cli add-import obj-aa11bb22 obj-5e6f7a8b \
  "authenticates user before wishlist operations"
```

## Step 7: Declare Public API

The wishlist service is consumed by other modules, so its entity (created in Step 5) is shared by UID:

```bash
dsp-cli create-shared obj-aa11bb22 func-cc33dd44
```

## Step 8: Verify Consistency

```bash
dsp-cli get-orphans
dsp-cli get-stats
```

No orphans — the graph is consistent.

## Result

Codex used DSP to understand the existing architecture before writing code, then kept the graph up to date with the new feature. On the next task, Codex will instantly know the wishlist exists, what it does, and how it connects to other modules.
