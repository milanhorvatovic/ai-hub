# Mantras (full prose)

Universal shorthand that governs every decision the skill makes. The numbered principles in `principles.md` are the operational form; the mantras are the labels you carry across decisions.

## Tier hierarchy and conflict resolution

This file is the one normative home for the tier rule; it governs *design conflicts* — which rule outranks which when two of them fight. Triage order, a different question, is severity's, stated in `principles.md`.

Three tiers. **Tier wins over tier** when mantras conflict — a Tier 1 *goal* outranks a Tier 2 *design rule*, which outranks a Tier 3 *pruning rule*. Inside a tier, siblings are case-by-case; they answer different questions and rarely conflict head-on. When two same-tier rules appear to fight, look for the trap rather than picking a winner — modular-by-composition's "delegate behavior, not the held object" dissolves the apparent tension between composition and encapsulation, for instance.

- **Tier 1 — Goals**: *what* we are trying to achieve (quality attributes of the system).
- **Tier 2 — Design**: *how* we achieve the goals (techniques and shapes).
- **Tier 3 — Pruning**: *what we don't add* (brakes on over-design).

## Tier 1 — Goals (what we're trying to achieve)

- **Readability first** — Code is read more than it is written. Optimize for the next person, who is often you in six months with less context than you have now.
- **KISS** — Keep It Simple, Stupid. Prefer simple solutions over clever ones. Boring code that obviously works beats elegant code that needs explanation.
- **Testability** — Production code is verifiable in isolation. A unit that cannot be tested without booting half the system, mocking five collaborators, or freezing the clock with patches is a unit with the wrong shape. Testability is the most honest measure of every Tier 2 rule: if SRP, modular composition, and isolated I/O are working, tests are easy to write; if they aren't, the design is the bug.
- **Scalability** — The system grows by *adding* pieces, not by *enlarging* existing ones. Adding the tenth feature should not require touching the first nine. Adding the second backend should not require rewriting the first. Scalability is a shape property — earned by SRP + modular + narrow interfaces — *not* infrastructure to build up front. Building a sharding layer for a single-node service is speculative; building today's feature so it doesn't accidentally couple itself to a single node is earned. The right question is never "will this scale to a million users?" — it is "when growth comes, will we *add* code or *rewrite* code?"
- **Observability** — Production code is debuggable without attaching a debugger to it. Logs at the edges (entry, exit, error) with structured fields, not raw string-concat narration of the interior. Errors carry context (what was attempted, with what inputs, against what state) — `raise ValueError("invalid")` is worthless; `raise ValueError(f"invalid email: {email!r} (user_id={user_id})")` is debuggable. Metrics where load or correctness matters; tracing across async or service boundaries. Like testability, observability is a quality signal of Tier 2 design: if the only way to understand a failure in production is to add a log line and redeploy, the design did not earn its shape.

## Tier 2 — Design (how we achieve the goals)

- **SRP** — Single Responsibility Principle. Each change, function, and module should do one thing. A function that "saves a user, sends an email, and logs the event" is three functions wearing a trench coat.

- **Modular by composition** — One design philosophy with three angles. Build the system as small pieces *(shape)*, combined by holding not extending *(technique)*, each exposing only what callers need *(boundary)*. Apply all three; the principle is incomplete without any one of them.
  - *Shape — small pieces with clear edges.* Each piece has clear inputs, clear outputs, and minimal hidden state. A piece is "small enough" when it can be tested in isolation and replaced without surgery. "Modular" does not mean "many files" — a single 80-line file with three small pure functions is more modular than five files connected by an interface and a factory. The goal is testable, replaceable units; file count is incidental.
  - *Technique — composition over inheritance.* Combine behavior by *holding* and delegating, not by *extending* a base class. Inheritance creates rigid hierarchies, fragile-base-class problems, and couples subclasses to parent internals. Prefer composition (a `class` *holds* a `Logger`; it does not `extends LoggingBase`), small interfaces, and traits/mixins where the language supports them. Inheritance is acceptable for true *is-a* relationships the language idiomatically expects (extending `Exception`, implementing a framework-required base class) — never as a code-reuse mechanism. "Reuse via inheritance" is reuse purchased on credit.
  - *Boundary — minimum public surface.* Export the smallest API that satisfies callers; everything else private/internal. The public surface is a contract — every exported function, type, or constant is a future maintenance commitment. Default to private and promote on demand: `_prefix` in Python, omit `pub` in Rust, no re-export in TS index files, package-private in Java. A module that exports forty things has effectively no encapsulation; one that exports four has shape.
  - *The trap where technique fights boundary — delegate behavior, not the object.* Composition can leak surface area when a wrapper exposes pass-through accessors to its held collaborators. Resolution: expose `client.send(msg)`, not `client.getInternalSocket()`. The held collaborator is an implementation detail; the wrapper's API is the contract callers see. Use the held thing inside; do not hand it out.
  - *What this principle rejects:* plugin systems, abstract base classes, DI containers, and "extension points" introduced without evidence of need — those are *speculative generality* (see principle 4 in `principles.md`), not modularity. Modular shape is free; modular infrastructure is not.

- **Strong typing** — Prefer concrete types over escape hatches (`any`, `Any`, `unknown`-without-narrowing, `Object`, `dynamic`, `void*`, `interface{}`). Escape hatches are a deliberate, justified choice — never the default. Types are how the compiler does free code review; don't disable it.

- **Fail fast, fail loud** — Surface invalid state at the boundary it enters, not three call frames later as a confusing downstream error. Validate inputs at the function/module/service edge; assert invariants (`assert`, `invariant()`, type narrowing, range checks) at construction. Never silently coerce, default, or swallow — `try/except Exception: pass` is a future incident. When something is genuinely unexpected, throw or panic; don't return `None`, `false`, or an empty list and hope the caller notices. Pairs with principle 5 in `principles.md` (trust internal code): once validated at the boundary, downstream code does not re-check.

- **Immutability by default** — `const` / `readonly` / `final` / `let` over mutable bindings; new values over in-place mutation; copy-on-write at boundaries. A mutated variable is a mini-state-machine; an immutable value is a fact. Pure functions over methods that mutate `self`. Mutability is a *justified* choice (performance-critical inner loops, accumulator patterns) — not the default. Reduces aliasing bugs, makes concurrency safer, and makes types more honest (`readonly T[]` says what it means).

- **Make illegal states unrepresentable** — Encode mutually-exclusive states as sum types / discriminated unions, not bags-of-optionals. `type Load<T> = {kind:'idle'} | {kind:'loading'} | {kind:'success', data:T} | {kind:'error', err:Error}` beats `{loading?: bool, data?: T, err?: Error}` — the second one permits `{loading:true, data:..., err:...}` which is incoherent. Same for: status enums that are really exclusive, pairs of "is X / is Y" booleans, "either A or B" function signatures. The compiler enforces what the design says.

- **Locality of behavior** — Counter-weight to modular/composable. Code that changes together lives together. Don't split for splitting's sake. A 50-line function that handles one cohesive operation is not "too long" — eight 8-line functions connected by an interface and three callbacks is *worse*. The right unit size is "everything the reader needs to understand this concept, and nothing more." Split when concepts diverge, not when line count crosses a threshold.

- **Pure / impure separation** (functional core, imperative shell) — Push side effects to the edges. The center of the system is pure functions on values; the rim does I/O, mutation, and external calls. A request handler reads input, calls into pure logic, writes output — it does not interleave database calls into the middle of the business decision. Makes testability free (pure cores need no mocks), makes refactoring safe (no hidden state), and makes concurrency tractable (no shared mutable state in the hot path).

- **Explicit over implicit** — No magic globals, no decorators that quietly do five things, no framework auto-wiring whose behavior cannot be predicted from the call site. The reader of a function should be able to tell what it does without spelunking the import graph for hidden behavior. Pass dependencies in; do not pull them from a registry. Load configuration once at startup and pass the resolved value down; do not read env vars from deep in the call stack. When the framework forces magic (decorators, middleware, lifecycle hooks), confine it to a thin shell at the edge and keep the interior straightforward.

## Tier 3 — Pruning (what we don't add)

- **DRY** — Don't Repeat Yourself. Extract common patterns, *but not prematurely*. Three similar lines are not a duplication — they are three lines. Wait for the third caller before abstracting.
- **YAGNI** — You Aren't Gonna Need It. A check, not a veto. Once the modular shape is settled and SRP is honored, don't pile on extra features, options, parameters, or layers of indirection until something concrete demands them. YAGNI prunes overgrowth; it does not block reasonable up-front design.

## Mantra → principle reverse map

Diagnostic aid. When a mantra is being violated, these are the numbered principles in `principles.md` that operationalize it. Use this to translate a high-level concern ("this design isn't testable") into specific actionable findings.

| Mantra | Operationalized by principles |
| ------ | ----------------------------- |
| Readability first (T1) | 7 (comment content), 9 (read before edit), 17 (naming), 21 (comment value) |
| KISS (T1) | 1 (scope), 4 (no speculative generality), 14 (no over-engineering) |
| Testability (T1) | 2 (failing-first test), 15 (mock at boundaries), 16 (inject time/randomness) |
| Scalability (T1) | 14 (modular/composable/scalable), 18 (single source of truth) |
| Observability (T1) | 13 (security: structured logs), 15 (tests describe behavior) |
| SRP (T2) | 1 (scope), 8 (no half-impls), 14 (small functions) |
| Modular by composition (T2) | 4 (earned shape), 14 (modular/composable/scalable) |
| Strong typing (T2) | 5 (trust internal code), 19 (parse at boundaries) |
| Fail fast, fail loud (T2) | 2 (root cause), 5 (boundary validation), 13 (security) |
| Immutability by default (T2) | (no dedicated principle — flagged via the checklist) |
| Make illegal states unrepresentable (T2) | 19 (typed boundaries) |
| Locality of behavior (T2) | 9 (read before edit), 14 (small but not tiny) |
| Pure / impure separation (T2) | 14 (I/O at the edges), 16 (inject external state) |
| Explicit over implicit (T2) | 7 (no PR/ticket refs in comments), 16 (inject env / config) |
| DRY (T3) | 14 (no premature abstraction), 20 (no dead code) |
| YAGNI (T3) | 3 (edit-existing), 4 (no speculative generality), 6 (no compat shims) |

**Outside the map, deliberately: principles 10, 11, and 12.** Every mantra above names a property of the code — how it reads, how it composes, how it fails. These three name a property of the person or agent doing the work: verify the change actually works before calling it done (10), let reversibility set how much confirmation an action needs (11), apply the preferences the user has already stated (12). No mantra operationalizes them because no design property can — an unrunnable-but-beautiful change violates 10 while satisfying every mantra here. They are _must_ rules and they are reached directly from `principles.md` and the checklist, not by translating a design concern through this table. Their absence is a statement, not a gap: a future editor who finds one missing should ask whether it is conduct or design before adding a row.

A mantra without a dedicated numbered principle (e.g. immutability) is enforced through the application checklist in `../SKILL.md`. A principle that operationalizes multiple mantras (e.g. 14, 16) is a high-leverage rule — violating it tends to violate several mantras at once.
