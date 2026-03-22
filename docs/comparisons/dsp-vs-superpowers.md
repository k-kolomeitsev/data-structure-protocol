# DSP vs Superpowers

## The real question

Superpowers sells engineering discipline — TDD enforcement, structured planning, code review, subagent orchestration. It wraps the agent in a methodology: think first, plan first, test first, review everything.

The question is: does a modern agent need this?

Claude Sonnet 4, GPT-4.1, Gemini 2.5 Pro — these models already know TDD. They know RED-GREEN-REFACTOR. They plan before coding when asked. They review their own output. They decompose tasks. They write tests. They don't need a skill file to tell them that tests should exist before implementation — they learned this from millions of engineering discussions in their training data.

What they **cannot** do is remember your project. Every new session is a blank slate. The agent re-reads your codebase, re-discovers dependencies, re-learns the architecture. On a 200-file project this "orientation phase" is expensive and lossy — the agent builds an incomplete mental model and makes decisions based on partial information.

**DSP solves the problem agents actually have.** Superpowers solves a problem that modern models handle natively.

## What each actually does

**DSP** gives agents persistent structural memory. A graph of entities, dependencies, public APIs, and the *reasons* behind every connection. The agent reads `.dsp/` and knows the project — instantly, accurately, across sessions.

**Superpowers** gives agents engineering methodology. Composable skills that trigger automatically: brainstorming, planning, TDD, code review, subagent-driven development. It tells the agent *how* to approach tasks.

The difference: DSP provides knowledge the agent doesn't have. Superpowers provides discipline the agent already has.

## Feature comparison

| Feature | DSP | Superpowers |
|---|---|---|
| **Core idea** | Persistent structural memory | Engineering discipline enforcement |
| **What it solves** | Agent has no memory of project between sessions | Agent might skip tests/planning/review |
| **Is the problem still real?** | Yes — no model has built-in project memory | Diminishing — modern models follow TDD and plan when prompted |
| **Architecture** | Graph database in `.dsp/` (plain text) | Composable skills/subagents |
| **Memory / Persistence** | Full graph persists across sessions, tools, branches | No persistent project memory |
| **Brownfield support** | First-class — DFS bootstrap for existing codebases | No explicit brownfield workflow |
| **Impact analysis** | Built-in — graph traversal shows what breaks | Not available |
| **TDD** | Not in scope — agent handles this natively | Core selling point — enforces RED-GREEN-REFACTOR |
| **Overhead** | Low — memory layer, no ceremony | Medium — mandates full TDD cycle even for trivial changes |
| **Install** | `curl \| bash` or `irm \| iex` | Plugin marketplace or manual setup |
| **Codebase mapping** | Full entity graph with `why` for every edge | Agent must scan files manually |
| **Session continuity** | Agent reads `.dsp/` — instant context | No built-in session memory |
| **Dependency discovery** | `search`, `find-by-source`, `get-children` — seconds | Agent must explore on its own |
| **Tool support** | Claude Code, Cursor, Codex | Primarily Claude Code and Cursor |

## Why agents don't need discipline enforcement

Superpowers' core value proposition: left to themselves, agents skip tests, don't plan, write sloppy code. You need a framework to force discipline.

This was partly true with earlier models. With current models:

- **TDD** — tell any modern agent "follow TDD, write failing tests first" and it will. It doesn't need a skill file to enforce this — it needs a single line in the system prompt or project rules.
- **Planning** — agents plan naturally when the task is complex. When it's simple, forcing a planning phase is overhead.
- **Code review** — agents can review their own work, run linters, run tests, check types. An external review skill adds a round trip for something the agent already does.
- **Brainstorming** — a modern agent exploring architecture options doesn't need a dedicated skill triggering. It thinks about tradeoffs as part of its reasoning.

What agents **genuinely cannot** do:
- Remember that `PaymentService` imports `StripeClient` and `DatabaseService`, and that `OrderService` and `WebhookHandler` depend on it
- Know that changing `src/lib/common/config-fragment.ts` affects 12 other modules
- Recall the purpose and contract of a module they worked with 3 days ago
- Navigate a multi-root project (backend + frontend) without reading hundreds of files

That's what DSP provides. No amount of "discipline enforcement" solves the memory problem.

## Example: "Add rate limiting to API endpoints"

### With DSP + agent

```bash
# Agent reads DSP — instant structural context
dsp-cli search "middleware"
# obj-55667788  [purpose] API middleware stack — cors, logging, error handling

dsp-cli get-children obj-55667788 --depth 1
# Middleware stack → [cors-config, request-logger, error-handler]

dsp-cli get-recipients obj-55667788
# obj-11223344: API router applies middleware stack to all routes

# Agent already knows: where middleware lives, what's already there,
# who depends on it, how to extend it.
# Plans, writes tests, implements, registers — all with full context.

dsp-cli create-object "src/middleware/rate-limiter.ts" "Rate limiting — sliding window per IP with Redis"
dsp-cli add-import obj-55667788 obj-NEW_RATE_LIMITER "rate limiting before route handlers"

# Next session: agent knows rate limiter exists, where it sits, who uses it.
```

### With Superpowers + agent

```bash
# Brainstorm skill fires — agent scans codebase from scratch
# (reads files to figure out what middleware exists, what routes look like)

# Plan skill fires — creates implementation plan
# (based on the incomplete picture from file scanning)

# Implementation skill: TDD cycle
# Write failing test (agent knows how to do this without the skill)
# Implement rate limiter
# Green test, refactor

# Review skill checks code quality
# (agent could have done this by running tests + linting)

# Next session: agent has no memory. Re-scans everything.
# Doesn't know rate limiter exists or who depends on it.
```

### The difference

With DSP, the agent starts with full structural knowledge and spends tokens on **work**. Without it, every skill in Superpowers starts with a "re-discover the project" phase that burns tokens and produces incomplete context.

The irony: Superpowers' skills would work **dramatically better** if they had DSP's structural context. The brainstorming skill would brainstorm with full knowledge of existing architecture. The planning skill would plan with accurate impact analysis. The review skill would check DSP consistency alongside code quality.

## Can you use both?

Yes. If you find value in Superpowers' TDD enforcement or subagent orchestration, DSP makes every skill more effective by providing instant structural context. The brainstorming skill stops guessing about architecture. The planning skill gets accurate dependency graphs. Subagents receive targeted context from `.dsp/` instead of scanning the full repo.

But the honest question remains: if your agent has DSP's structural memory and you give it a clear instruction like "follow TDD, plan before coding, review your work" — do you still need a framework enforcing this?

For most teams using modern models, the answer is no. The agent is already disciplined. It just needs memory.

## Summary

| | DSP | Superpowers |
|---|---|---|
| **Solves** | Lack of persistent project memory | Lack of engineering discipline |
| **Is the problem real in 2026?** | Yes — no model has built-in project memory | Diminishing — modern models are disciplined when prompted |
| **What you need** | DSP + any modern agent | Superpowers + hope the agent can't write tests on its own |
| **Overhead** | Low | Medium |
| **Persistence** | Full graph across sessions | None |

**The bottom line:** modern agents already know TDD, planning, and code review. They don't know your project structure. DSP is the fix.

## Try it

- **DSP protocol + skill**: [data-structure-protocol](https://github.com/k-kolomeitsev/data-structure-protocol)
- **Fullstack boilerplate with DSP pre-initialized**: [dsp-boilerplate](https://github.com/k-kolomeitsev/dsp-boilerplate) — NestJS + React + Docker Compose, ready to clone and build on
