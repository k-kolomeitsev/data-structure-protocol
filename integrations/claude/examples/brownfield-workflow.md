# Brownfield Workflow — Adding a Feature with DSP (Claude Code)

A realistic walkthrough of using DSP when working on an existing codebase with Claude Code.

`dsp-cli` is shorthand for `python <skill-path>/scripts/dsp-cli.py --root .`.

## Scenario

You have an e-commerce project with DSP already bootstrapped. The user asks Claude to add a "wishlist" feature.

## Step 1: Understand the Existing Structure

The user prompts Claude:

> Add a wishlist feature. Users should be able to save products and view their wishlist.

Claude starts by reading DSP:

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

Claude reads the descriptions of these entities (`get-entity`) and learns the layout: `obj-1a2b3c4d` is the products module, `obj-5e6f7a8b` — auth, `obj-9c0d1e2f` — cart, `obj-3a4b5c6d` — database layer.

## Step 2: Find Related Entities

Claude searches for existing product and user-related entities:

```bash
dsp-cli search "product"
dsp-cli search "user"
```

Then inspects the product module for its public API:

```bash
dsp-cli get-entity obj-1a2b3c4d
dsp-cli get-children obj-1a2b3c4d
```

Output reveals `obj-1a2b3c4d` has a shared export `func-ab12cd34` (`ProductService`) and child functions like `getProductById`.

## Step 3: Check Impact Before Changes

Claude checks who depends on the product module:

```bash
dsp-cli get-parents obj-1a2b3c4d
dsp-cli get-recipients obj-1a2b3c4d
```

This shows `cart` module already imports from `products` — Claude can follow the same pattern.

## Step 4: Implement the Feature

Claude creates the wishlist module files:

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

The DSP graph now reflects the new feature. Next time an agent works on this codebase, it will instantly know:

- The wishlist module exists and what it does
- It depends on products, auth, and database
- It exposes the wishlist service (`func-cc33dd44`) as a public API
- Who else might be affected if wishlist changes
