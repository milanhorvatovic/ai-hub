# Numbered principles (full prose)

Operational rules. Each principle is enforceable on its own; the mantras in `mantras.md` are the shorthand category labels they live under.

Cross-references to mantras are by name. Cross-references between principles are by number (`see principle N`).

## Severity tags

Each principle is tagged with a severity:

- **must** — non-negotiable. Treat a violation as a bug; fix before shipping. Common in security, correctness, and trust-related rules.
- **should** — strong default. Deviation needs a stated reason; silent violations are debt.
- **could** — preference. Deviation is fine when surrounding code differs or when the cost outweighs the benefit. Apply silently when you can; do not lecture when you cannot.

When several violations exist at once: fix the **musts** first, recommend the **shoulds**, apply the **coulds** silently unless they would conflict with file-local style.

## Conflict resolution (tier wins over tier)

Severity governs *triage* (which violation to fix first). The **mantra tier hierarchy** governs *design conflicts* (which principle outranks which when they fight).

- **Tier 1 — Goals** (readability, KISS, testability, scalability, observability) outrank everything.
- **Tier 2 — Design** (SRP, modular-by-composition, strong typing, fail-fast, immutability, illegal-states-unrepresentable, locality-of-behavior, pure/impure, explicit-over-implicit) serve Tier 1 and outrank Tier 3.
- **Tier 3 — Pruning** (DRY, YAGNI-as-check) are checks applied last; they prune overgrowth, not block reasonable shape.

Inside a tier, siblings are case-by-case — they answer different questions and rarely conflict head-on. When two principles in the same tier appear to fight, look for the trap (e.g. modular-by-composition's "delegate behavior, not the held object" resolves the apparent tension between composition and encapsulation).

This rule is duplicated in `mantras.md` because it is load-bearing: an agent that loads `principles.md` without the mantras still needs to know how design conflicts resolve.

## 1. Match scope to the request — *should*

Do exactly what was asked. A bug fix fixes the bug — it does not also refactor the surrounding function, rename variables, or "improve" unrelated code. A one-shot script does not need a helper module. Three similar lines are better than a premature abstraction.

If you notice unrelated issues, note them in the end-of-turn summary as follow-ups, do not silently address them.

## 2. Root cause over bandaid — *must*

When something breaks, find the underlying cause before patching the symptom. A failing test is a signal — silencing it (`.skip`, `xfail`, broad try/except) without understanding why is debt. A flaky behavior under load is a real bug, not "just retry it."

**Bug fixes need a reproducing test.** Add a test that fails because of the bug *first*, then fix the code without changing that test, then re-run to confirm the test now passes. A fix without a failing-first test cannot prove it actually fixed anything.

Exception: when the user explicitly asks for a temporary mitigation with a follow-up plan, mark the workaround clearly (`TODO: temporary — remove after <condition>`) and surface it in the summary.

## 3. Edit existing files; do not create new ones speculatively — *should*

Prefer modifying an existing file over creating a new one. New files imply new structure, new imports, new mental load. Create a new file only when the change genuinely belongs in a new place (a new feature module, a new test fixture, a new migration).

Never create README/docs/markdown files unless the user explicitly asks for them.

## 4. No *speculative* generality (but earn the shape) — *should*

Do not design for hypothetical future requirements. Do not add config options "in case someone wants to customize this later." Do not add a plugin point, a strategy interface, a factory, or a DI container for a single caller.

The hardest-to-remove code is the code that has one user but pretends to support many.

This principle is a **check**, not a veto. Modularity, composability, and clear seams (mantras) are not "speculative" — they are how the *current* feature is shaped. Choosing small functions with clear inputs and outputs, separating I/O from logic, and keeping modules orthogonal is earning the shape, not speculating about the future. The line is concrete:

- **Earned shape** (allowed, even encouraged): splitting a 200-line handler into four small pure functions; separating the parser from the validator; putting persistence behind a single function so it can be swapped at test time.
- **Speculative generality** (not allowed without evidence): introducing an interface with one implementation; adding a config flag with no current caller toggling it; carving a plugin API for plugins that do not exist; adding a base class for "future subclasses."

When in doubt, ask: *does the current feature, as specified, benefit from this shape?* If yes — earned. If "it'll help later" — speculative.

> **Code examples** — Python: `capabilities/python/capability.md` (Principle 4).

## 5. Trust internal code; validate only at boundaries — *should*

Internal functions trust their callers. Frameworks honor their contracts. Do not add type checks, null guards, or "defensive" branches for states that internal code cannot produce. Validate user input, external API responses, and file/network data at the system boundary — then trust it onward.

Defensive code for impossible states is noise that hides real bugs.

> **Code examples** — Python: `capabilities/python/capability.md` (Principle 5).

## 6. No backwards-compatibility shims unless asked — *should*

Renaming a function? Rename it and update callers. Removing an argument? Remove it. Do not leave a deprecated alias, a `// removed in v2` comment, a re-export, or an unused `_old_name` parameter unless the user has explicitly asked you to preserve compatibility (published API, external consumers, multi-version migration).

When in doubt about whether something is published or internal, ask once — do not default to preservation.

## 7. Comments explain *why*, not *what* — *could*

Default to writing no comments. Well-named identifiers already explain what. Add a comment only when the *why* is non-obvious: a hidden constraint, a workaround for a specific bug, behavior that would surprise a reader, an invariant the type system cannot express.

Do not write comments that reference the current PR, ticket, or caller ("added for the X flow", "used by Y", "fix for #123") — those rot. Put that in the commit message.

Never write multi-paragraph docstrings or block comments unless the project's existing style demands it (check `repo-conventions`).

## 8. No half-implementations — *must*

If a function is supposed to do A, B, and C, ship all three or none. Do not commit A and B with a stubbed C that returns null/raises NotImplementedError, unless the user has explicitly approved an incremental approach with follow-up tasks tracked.

A half-implementation is worse than nothing — it looks done, passes the typecheck, and silently misbehaves at runtime.

## 9. Read before you edit — *must*

Before modifying a file, read enough of it (and its callers) to understand the local conventions: naming, error handling, logging, test patterns. Match the surrounding style even when it differs from your default. Consistency inside a file matters more than absolute purity.

When the file is new, `repo-conventions` or sibling files anchor the style.

## 10. Verify the change works — *must*

Before reporting a task as done:

- If a test suite exists and is fast, run the relevant tests.
- If the change is UI/frontend, exercise the feature in a browser (or say explicitly that you could not).
- If the change is a CLI/script, run it once with realistic input.
- If verification is genuinely impossible (no test infra, no runnable env), say so — do not claim success.

Typechecks and lint passing are necessary but not sufficient; they verify code shape, not behavior.

## 11. Reversibility shapes caution — *must*

Local file edits are cheap to undo. Risky actions (`git push --force`, `rm -rf`, `DROP TABLE`, `git reset --hard`, deleting branches, sending external messages) are not. For irreversible operations, pause and confirm even if the user previously approved a similar action — prior approval is scoped, not blanket.

## 12. Honor the user's stated preferences — *must*

If the user has expressed a preference in this session, in memory, or in `CLAUDE.md` / `AGENTS.md`, apply it consistently. Do not regress to defaults across turns. When a stored preference conflicts with the current task, surface the conflict and ask — do not silently override.

## 13. Security hygiene is a baseline, not a feature — *must*

These rules apply to every change, not only changes labeled "security":

- **No secrets in source** — API keys, tokens, passwords, private keys, signing secrets, connection strings with credentials. Use env vars, secret managers, or the project's existing pattern. If you find a hardcoded secret in code you're editing, flag it and stop — do not commit alongside it.
- **No secrets in logs** — even at debug level. Log identifiers and shapes (`user_id=...`, `token=<redacted>`), never raw bearer tokens, raw request bodies, or full headers.
- **No sensitive data in error messages** — error responses that leak stack traces, SQL queries, file paths, or PII to end users are bugs.
- **Validate at trust boundaries** — see principle 5; for security, the boundary list also includes deserialization, template rendering, shell invocation, and SQL composition. Use parameterized queries, escaping libraries, and the framework's built-in sanitizers.
- **Authorization is not authentication** — verify "can this user do this action on this resource?" at every handler that mutates or reads sensitive state, even when authentication has already happened upstream.
- **Dependency hygiene** — when adding a new dependency, sanity-check it (download count, last release, maintained?) and prefer the standard library or an already-used dep when reasonable.

When in doubt about a security-sensitive change, surface the concern and pause rather than ship.

> **Code examples** — Python (logging redaction + error response): `capabilities/python/capability.md` (Principle 13).

## 14. Prefer modular, composable, scalable designs — without over-engineering — *should*

Default shape for any non-trivial change:

- **Small functions with explicit inputs and outputs.** Side effects pushed to the edges (read input, compute pure, write output). Pure cores are easy to test, reuse, and parallelize.
- **Narrow interfaces.** A function that takes three primitives is easier to compose than one that takes a 30-field options object. A module that exports four functions is easier to consume than one that exports forty.
- **Orthogonal modules.** Two modules should not need to know each other's internals. If module A's behavior changes when module B's implementation changes (without their shared contract changing), they are coupled — fix the contract.
- **Hidden state is debt.** Globals, module-level mutable state, singletons-by-convention. Each one is a future test fixture and a future bug.
- **Scale by composition, not by complication.** When the system needs to do more, prefer adding another small piece over enlarging an existing one. New behavior is a new function/module/job; new performance is a new layer (cache, queue, batch) added between existing pieces.

Tension with YAGNI is real. Resolution:

- **Shape is free; infrastructure is not.** Building the current feature out of small composable pieces costs almost nothing and pays off the first time anything changes — do it. Adding plugin points, strategy interfaces, factories, configuration layers, or abstract base classes is *infrastructure* and requires evidence of need — defer it until something concrete asks for it.
- "Modular" does not mean "many files." A single 80-line file with three small, pure functions is more modular than five files connected by an interface and a factory.
- YAGNI prunes the *infrastructure* side of this principle, not the *shape* side. When in doubt, lean toward clean modular shape; lean away from speculative wiring.

Sequence: write the simplest version that has the right *shape* (small functions, narrow interfaces, isolated I/O). Add wiring (configurability, indirection, polymorphism) only when a second concrete caller forces it.

## 15. Tests describe behavior, not implementation — *should*

- **Test names state behavior**: `test_create_user_returns_400_when_email_invalid`, not `test_create_user_2`. The name should read like a sentence about what the system does.
- **Mock at boundaries, not at internal logic.** Mock the HTTP client, the database driver, the clock — not the function under test's helpers. Tests that mock internal collaborators verify wiring, not behavior, and break on every refactor.
- **One behavior per test**, in most cases. Multiple assertions are fine when they verify one behavior together; multiple unrelated behaviors mean split the test.
- **Avoid mocking-hell** — if a unit test needs five mocks to construct its subject, the subject has too many responsibilities (see SRP) or the test should be an integration test.
- **Skip trivial code** — getters, simple imports, type-only declarations, generated code. Test the logic that can be wrong.

> **Code examples** — Python: `capabilities/python/capability.md` (Principle 15).

## 16. Inject time, randomness, and external state — *should*

Business logic does not reach into globals for non-determinism. Specifically:

- **Time** — never call `time.now()`, `Date.now()`, `new Date()`, `Instant::now()`, `chrono::Utc::now()`, etc. from business code. Take a `clock` / `now` / `time_provider` parameter. The same goes for `time.sleep` / `setTimeout` outside of explicitly time-based primitives.
- **Randomness** — never call `Math.random()`, `random.random()`, `uuid.uuid4()` from business code. Take a `rng` / `id_generator` parameter, or accept the value as input.
- **Environment** — never read `os.environ` / `process.env` / `std::env::var` from deep in the call stack. Read it once at startup, pass the resolved value down.
- **Filesystem and network** — wrap behind an interface or pass the resource in. The function that decides *what* to write should not also call `open()`.

Why: deterministic units are testable without freezing patches, reproducible across runs, and safe under concurrency. The cost is a single extra parameter at the boundary; the payoff is every test below that boundary stops being flaky.

The thin shell at the edge — `main()`, the request handler entry point, the CLI bootstrap — is where the real clock, real RNG, real env, real I/O get wired in. Everything else gets them passed in.

> **Code examples** — TypeScript: `capabilities/typescript/capability.md` (Principle 16).

## 17. Naming discipline — *could* (*should* when names are actively misleading)

Names are the cheapest documentation. Spend the effort once at write-time; readers pay the cost every time afterward.

- **Descriptive over short.** `user_id` not `uid`, `connection_pool` not `cp`, `parse_request` not `pr`. Exceptions: canonical short names (`id`, `url`, `db`, `http`, `io`, `tx`, `ctx`) and idiomatic loop indices (`i`, `j`, `k`).
- **No decay suffixes.** `_old`, `_new`, `_v2`, `_temp`, `_tmp`, `Old`, `New`, `Legacy` — these mark code as transitional and then linger past the transition. If you are mid-migration, name the *replacement* clearly and delete the original when done; do not leave both forever.
- **Function names describe what they do or return.** `get_user(id)` returns a user; `ensure_user(id)` creates if missing; `find_user(id)` returns optional. If you need a docstring to clarify the function's purpose at a basic level, the name is wrong.
- **Booleans are predicates.** `is_admin`, `has_access`, `should_retry`, `can_delete`. Not `admin` (count or bool?), not `access` (noun, not predicate).
- **No abbreviations except canonical ones.** `usr`, `cnt`, `mgr`, `svc`, `req`, `resp` save five characters at write-time and cost ambiguity every read. `req`/`res` are accepted in HTTP-handler contexts; outside that, write them out.
- **Reserve `tmp` / `temp` for true throwaways** — local variables whose scope is a few lines. Never a field name, never a module name, never a public symbol.
- **Match the codebase's existing patterns** for casing (camelCase / snake_case / PascalCase) and noun/verb conventions. Consistency inside a file matters more than your personal preference.

> **Code examples** — Python: `capabilities/python/capability.md` (Principle 17).

## 18. Single source of truth for state — *should*

Derived state is *computed*, not *stored*. Cache invalidation is one of the two hard problems in computer science for a reason — do not opt into it for free.

- If `total = sum(items)`, do not also store `total` next to `items` — compute it on read.
- If `is_complete = status == "done"`, do not also store `is_complete` — derive it.
- If the same value lives in two places and they must stay in sync, it is a bug waiting for the next contributor to forget the sync.
- If a relationship between two entities can be reconstructed from a join, do not denormalize it into a third column "for convenience."

Exceptions are deliberate, measured, and documented:

- **Persistence caches** for proven hot reads. Implement the invalidation alongside the cache; document the invariant ("`total` is denormalized from `items`; call `recompute_total(item_id)` on any item mutation"). Add a test that the cache drifts to wrong-and-detectable when invalidation is skipped, not wrong-and-silent.
- **External integrations** where the upstream system stores derived state and you must mirror it. Boundary problem, not internal design.

Default: one source. Derive the rest. If you find yourself debugging a "the two values disagree" bug, the fix is rarely to add a third reconciliation step — it is to delete one of the two and derive it instead.

> **Code examples** — TypeScript: `capabilities/typescript/capability.md` (Principle 18).

## 19. Boundaries parse input and serialize output — *should* (*must* for security-relevant boundaries)

Data crossing a trust line is *transformed*, not waved through. Generalizes principle 5 from "validate" into "transform":

- **Inbound** — HTTP request bodies, file reads, IPC messages, deserialized snapshots, env vars, CLI flags. Parse into a *typed* value at the entry point; reject malformed data with a useful error there; downstream code receives the typed value and trusts it. Tools: zod / valibot / pydantic / serde / parser combinators / hand-rolled with assertions.
- **Outbound** — HTTP responses, log records, audit events, persisted rows, IPC sends. Serialize *from* typed values through an explicit serializer that decides what is exposed. Never `JSON.stringify(internal_object)` and ship it — the next field you add to the internal object will silently leak.

The rule of thumb: at the edge, a function's signature is `(bytes) -> Typed` on the way in and `Typed -> bytes` on the way out. Everything else operates on `Typed`. Combined with strong typing + illegal-states-unrepresentable, this is most of how a codebase stays honest.

> **Code examples** — Python (inbound parse): `capabilities/python/capability.md` (Principle 19). TypeScript (outbound serialize): `capabilities/typescript/capability.md` (Principle 19).

## 20. No dead code, no commented-out code — *could*

Delete it. Git remembers.

- **Unreachable functions, classes, constants, types, branches** — delete them. They make readers ask "is this used somewhere I haven't seen?" and slow every navigation.
- **Commented-out code blocks** — delete them. If the code might be needed later, it lives in git history; `git log -S '<unique string>'` finds it. Inline `// previously: ...` blocks are noise that nobody ever cleans up.
- **Unused imports** — delete them; let the linter help.
- **Bare `TODO` / `FIXME` / `XXX` markers without a tracked item, a condition, or a date** — delete or replace with a tracked item. Permanent uncertainty is debt.
- **Parameters / fields no caller uses** — delete (with the call sites). Type systems often surface these; respect the signal.

Exceptions are rare and documented:

- An `if False:` / `# pragma: no cover` guard preserving a known-needed-soon block with a one-line `# kept: <reason>` comment.
- A platform-specific branch unreachable in the current build target, gated by a feature flag or `cfg!()`, with the gate explicit.

When tempted to comment out instead of delete, ask: "If I needed this back in six months, would I find it faster in git history or in a stale comment?" The answer is always git history.
