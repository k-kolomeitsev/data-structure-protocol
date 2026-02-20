## DSP (Data Structure Protocol): how to give LLM agents "long-term memory" of a large repository

There’s a pattern everyone who works with agents recognizes: **the first 5–15 minutes are spent not on the task, but on “getting oriented.”** Where is the entry point? Where do the dependencies come from? Why this library and not another one? Who considers this a public API? In a small project it’s annoying. In a large one, it becomes a constant tax on tokens and attention.

DSP (Data Structure Protocol) “externalizes the project map” — into a simple, versioned, language-agnostic graph that lives alongside the code and is available to the agent as persistent memory.

The goal is phrased in the architecture like this:

```
1) Goal and scope

The goal of DSP is to store minimal, but sufficient context about a repository / artifact system as a graph “entities → dependencies / public API”, so that an LLM can:

- quickly locate the necessary fragments by UID,
- understand why entities exist and how they are connected,
- avoid having to load the entire source tree into the context window.

DSP is long-term memory and an index of the project for an LLM. At any time, the agent can run a project-wide search (grep), find the required entities by descriptions/keywords, and from the found UID expand the entire relationship graph: incoming dependencies, outgoing imports, and consumers via `exports`. This replaces the need to “remember” the project structure or load it in full — the entire project map is always available through `.dsp`.
```

---

## What DSP is, in essence

### **DSP = an entity graph + the reasons behind connections**

DSP is stored in the **`.dsp/`** directory. Each “entity” gets a stable **UID** and a small set of files:

- **`description`**: _where it is_ (`source`), _what it is_ (`kind`), _why it exists_ (`purpose`).
- **`imports`**: what this entity uses (UID references).
- **`shared`**: what it exposes as a public API (exports).
- **`exports/`**: a reverse index — **who imports this entity and why** (the `why` text next to each consumer).

In large systems, one detail matters especially: DSP captures not only “what depends on what,” but also **why**. This drastically reduces guesswork in refactoring, migrations, and legacy removal.

### **There are only two base entity types**

- **Object**: module/file/class/config/resource/external dependency — “everything that isn’t a function.”
- **Function**: function/method/handler/pipeline.

Another bonus: **DSP is language-agnostic**. It works the same across TS/JS, Python, Go, infrastructure YAML, SQL, assets, and so on. The architecture also explicitly defines “import completeness”: **if something is imported, it must exist in `.dsp`**, including styles, images, JSON, wasm, and other artifacts. This matters more than it seems: agents more often lose not code, but _resource dependencies_.

---

## Why UID is the central idea

DSP is built on identity by UID, not by path. A path is an attribute. A UID is an entity’s “identity.”

- Renamed a file → run `move-entity`, the UID stays the same.
- Moved code around / reformatted → the UID stays the same.
- **A UID changes only when the purpose (semantic identity) changes**: the module truly became “about something else.”

To attach a UID to entities inside a file (exported functions/classes), DSP uses a simple marker comment `@dsp <uid>` right in the source code. It’s a pragmatic choice: it doesn’t depend on line numbers, works in any language, and is easy to find with grep.

---

## How an agent “walks” DSP instead of endlessly reading code

A typical agent workflow in a DSP-based project looks like this:

- **Find an entity**: `search` by keywords, or `find-by-source` by file path.
- **Understand the boundaries**: read `description`, `shared`, `imports`.
- **Pull context in batches**: instead of “give me the whole repo,” the agent fetches only the nodes it needs plus 1–2 levels of dependencies.
- **Estimate impact**: who consumes the entity and why (`get-parents` / `get-recipients`), whether there are cycles, whether there are “orphans.”

Example commands (PowerShell style; the CLI is shipped inside the skill):

```powershell
python .\.claude\skills\data-structure-protocol\scripts\dsp-cli.py --root . search "authorization"

python .\.claude\skills\data-structure-protocol\scripts\dsp-cli.py --root . get-entity obj-a1b2c3d4
python .\.claude\skills\data-structure-protocol\scripts\dsp-cli.py --root . get-children obj-a1b2c3d4 --depth 2

python .\.claude\skills\data-structure-protocol\scripts\dsp-cli.py --root . get-recipients obj-a1b2c3d4
python .\.claude\skills\data-structure-protocol\scripts\dsp-cli.py --root . get-path obj-a1b2c3d4 func-7f3a9c12
```

---

## What the `data-structure-protocol` skill adds (and why it’s more important than it seems)

DSP architecture is a set of rules. But without discipline an agent can easily violate them: poke the code at random, drag half the repo into the context, forget to update the index, and break graph integrity.

The skill covers exactly the operational part:

- **It embeds an Agent Prompt**: “before changing anything — find the entities; when creating — register; when importing — add `why`; when deleting — perform cascade cleanup.”
- **It provides reference materials** in `references/`: the storage format, the bootstrap algorithm (DFS from entry points), the semantics of operations.
- **It ships a production-ready CLI** `scripts/dsp-cli.py` that implements the operations from `ARCHITECTURE.md` and supports navigation/diagnostics (cycles/orphans/stats).

**DSP becomes not a “document,” but a living contract** that the agent executes while working — and keeps `.dsp` consistent without manual intervention.

---

## Cost of adoption: bootstrapping a large project will be expensive

Yes. **The initial bootstrap on a large repository is expensive** — in time, attention, and tokens.

Why:

- You need to identify the root entry points (and there are many in a monorepo).
- You need to traverse dependencies depth-first (DFS) and record all reachable modules/files/resources.
- For each node, you need to write a _minimal, but precise_ `purpose`.
- You need to fill in the reasons (`why`) for import edges in a disciplined way — otherwise half of DSP’s value disappears.
- Sometimes you need to add `@dsp` markers in source files for exported entities (so the UID becomes an “anchor” in code).

On large systems, this can realistically be its own mini-project.

---

## Why it pays off (and usually pays off faster than it seems)

The value of DSP is not “a pretty structure.” It’s in the economics of agent work:

- **Fewer tokens spent on orientation**: instead of repeatedly “warming up” context, the agent reads short `description/imports/shared/exports` and pulls exactly the files that need to be changed.
- **Context doesn’t dissolve between tasks**: `.dsp` is external memory that doesn’t depend on the current context window or the model’s “mood.”
- **Fast semantic lookup**: `search` finds entities by keywords, and `exports/` answers the question “why is this even here.”
- **Refactoring becomes safer**: impact analysis gets cheaper — you quickly get all consumers of an entity and update them precisely.
- **External dependencies become transparent**: external packages are captured as `kind: external`, without bloating the graph, but they remain navigable via the exports index.

And here’s an important point from the architecture — **granularity control**, so DSP doesn’t turn into a junk drawer:

```
10) Granularity and minimal-context policy

- Completeness at the file level, not at the code-within-file level. “Import completeness” (section 2) means that every file/module that is imported in the project must have an Object in `.dsp`. This is about files and modules — not about every variable inside a file. Within a single file, a separate UID is assigned only to an entity that is shared externally (`shared`) or used from multiple places. Local variables, internal helpers, private fields — remain part of the parent Object, without their own UID. If granularity keeps growing, something is being done wrong.

- Update consumers via `exports`. To update a library/module/symbol, it’s enough to open `exports` of the imported entity and get the list of importers (consumers) by UID, then update them precisely.

- Change tracking. `git diff` shows what changed — a new file was created, a function or object changed. The changed files are passed to the LLM to update DSP. Changes inside functions often don’t require updating DSP, because descriptions capture purpose, not implementation details — unless imports were added/removed.
```

This is what makes DSP viable over time: **the index stays compact**, and updates stay rare and meaningful.

---

## When DSP really shines

- **Large monoliths and monorepos**, where the context “never fits.”
- **Long-lived products**, where agents will work for months and years, not just one sprint.
- **Teams that frequently do refactors/migrations/dependency replacements**.
- **Projects with a complex resource layer** (assets/configs/generation) that is hard for agents to keep in their heads.

---

## Conclusion

DSP is an attempt to do for LLM agents what people have long done informally: keep a mental map of a system. Only instead of a head — **a graph on disk**; instead of “that’s how I remember it” — **minimal descriptions, connections, and reasons**; instead of “read the whole project” — **targeted navigation from entry points**.

Yes, **bootstrapping a large project will be expensive**. But if you truly plan to use agents systematically, this cost typically comes back through:

- fewer tokens spent on orientation,
- less context loss between tasks,
- faster discovery of the needed modules/dependencies,
- more predictable task execution (especially refactoring work).
