# DSP vs GSD (Get Shit Done)

## The real question

Modern AI coding agents — Claude Sonnet 4, GPT-4.1, Gemini 2.5 Pro — are already better at planning, structuring work, verifying output, and writing tests than most mid-level engineers. They don't need a wrapper to tell them how to plan. They don't need lifecycle phases imposed from outside. They already know.

The one thing they **cannot** do is remember your project between sessions.

Every new chat, every new task, every context window reset — the agent starts from zero. It re-reads files, re-discovers dependencies, re-learns what depends on what. On large codebases this "orientation tax" burns tokens, burns time, and produces worse results because the agent is working from incomplete information.

**DSP fixes the actual problem.** GSD wraps a problem that modern models have largely solved on their own.

## What each actually does

**DSP** gives agents persistent structural memory. A graph of entities, dependencies, public APIs, and the *reasons* behind every connection — stored in `.dsp/`, versioned with git, readable in seconds. The agent opens a new session and immediately knows the project.

**GSD** gives agents a workflow wrapper. Structured phases (plan → execute → verify → ship), fresh-context management, wave execution. It tells the agent *how* to work — planning docs, verification steps, atomic commits.

The difference: DSP solves a problem agents genuinely have (no memory). GSD solves a problem that was real 12 months ago but that modern models handle natively.

## Feature comparison

| Feature | DSP | GSD |
|---|---|---|
| **Core idea** | Persistent structural memory | Process/confidence wrapper |
| **What it solves** | Agent has no memory of project between sessions | Agent doesn't follow structured workflow |
| **Is the problem still real?** | Yes — no model has built-in project memory | Partially — modern models plan, verify, and ship without external phases |
| **Memory / Persistence** | Full graph persists across sessions, tools, branches | No persistent project memory |
| **Brownfield support** | First-class — DFS bootstrap maps existing codebases | `map-codebase` command — one-time scan, not persistent |
| **Impact analysis** | Built-in — `get-parents`, `get-recipients`, `get-children` | Not available |
| **Overhead** | Low — memory layer, no ceremony | Medium — lifecycle phases, planning docs, verification steps |
| **Install** | `curl \| bash` or `irm \| iex` | `npx get-shit-done-cc@latest` |
| **Codebase mapping** | Full entity graph with `why` for every edge | One-time scan |
| **Session continuity** | Agent reads `.dsp/` — instant structural context | Fresh-context model — each wave starts clean |
| **Dependency discovery** | `search`, `find-by-source`, `get-children` — seconds | Requires re-scanning or agent exploration |
| **Reason tracking** | Every import has a `why`; every export tracks who uses it and why | Not tracked |
| **Git hooks / CI** | Pre-commit, pre-push, GitHub Actions | Git hooks for workflow enforcement |
| **Tool support** | Claude Code, Cursor, Codex | Claude Code, OpenCode, Gemini CLI, Codex, Copilot |

## Why agents don't need lifecycle wrappers

GSD's value proposition is: your agent needs structured phases, otherwise it produces chaotic output.

This was a reasonable claim in early 2025. It is increasingly untrue in 2026:

- **Planning** — ask any modern agent to plan before coding and it will. It doesn't need `/gsd:plan-phase` to know that planning is useful.
- **Verification** — agents already run tests, check types, lint code, and review their own output. They don't need `/gsd:verify-work` as an external trigger.
- **Atomic commits** — any agent instructed to commit atomically will do so. This is prompt-level, not framework-level.
- **Fresh contexts** — useful concept, but the agent can manage context windows without a wrapper orchestrating "waves."

What agents **cannot** do without external help:
- Remember what `src/services/payment.service.ts` imports and why
- Know that 7 modules depend on the auth middleware before you change it
- Recall that the frontend config fetcher was refactored last week and moved to a new path
- Navigate a 200-file codebase without loading everything into context

That's what DSP does. No other tool in the category addresses this.

## Example: "Add authentication to an existing Express.js project"

### With DSP + agent

```bash
# Agent starts a session — reads DSP for instant context
dsp-cli search "express app"
# obj-a1b2c3d4  [purpose] Express application entry point and middleware setup

dsp-cli get-children obj-a1b2c3d4 --depth 2
# Full dependency tree: routes → controllers → services → database

dsp-cli get-recipients obj-a1b2c3d4
# Every module that depends on the app setup

# Agent has full structural context in seconds.
# Plans, implements, tests, ships — using its own intelligence.
# Registers new entities as it goes:
dsp-cli create-object "src/middleware/auth.ts" "JWT authentication middleware"
dsp-cli add-import obj-a1b2c3d4 obj-NEW_AUTH "applies JWT auth to protected routes"

# Next session: agent reads DSP, sees auth already integrated, continues from where it left off.
```

### With GSD + agent

```bash
# /gsd:plan-phase
# Agent scans codebase from scratch (expensive — reads dozens of files)
# GSD generates planning docs (agent could have planned without this)

# /gsd:execute-phase
# Wave 1: Create auth middleware (fresh context — re-reads relevant files)
# Wave 2: Create auth service (another fresh context — re-reads again)
# Wave 3: Integrate with routes (another fresh context — re-reads yet again)

# /gsd:verify-work
# Agent verifies (it would have done this anyway if asked)

# Next session: agent has no memory. Starts from zero again.
# No persistent knowledge that auth exists, what depends on it, or why.
```

The difference: with DSP, the agent spends tokens on **work**. Without it, the agent spends tokens on **re-orientation** — every single session.

## What about using both?

You can use DSP alongside GSD. DSP provides memory; GSD provides workflow ceremony. If your team finds value in GSD's structured phases, DSP makes every phase faster and more accurate because the agent starts with structural context instead of re-scanning.

But the honest take: if the agent already has DSP's structural memory, much of GSD's value disappears. The agent doesn't need a wrapper to plan well when it already knows the full dependency graph. It doesn't need fresh-context waves when it can read `.dsp/` and instantly understand the project.

## Summary

| | DSP | GSD |
|---|---|---|
| **Solves** | Lack of persistent project memory | Lack of structured workflow |
| **Is the problem real in 2026?** | Yes — no model has built-in project memory | Diminishing — modern models are disciplined by default |
| **What you need** | DSP + any modern agent | GSD + hope the agent can't plan on its own |
| **Overhead** | Low | Medium |
| **Persistence** | Full graph across sessions | None |

**The bottom line:** modern agents are smart enough to plan, verify, and ship. They are not smart enough to remember your project. DSP is the fix. Everything else is optional ceremony.

## Try it

- **DSP protocol + skill**: [data-structure-protocol](https://github.com/k-kolomeitsev/data-structure-protocol)
- **Fullstack boilerplate with DSP pre-initialized**: [dsp-boilerplate](https://github.com/k-kolomeitsev/dsp-boilerplate) — NestJS + React + Docker Compose, ready to clone and build on
