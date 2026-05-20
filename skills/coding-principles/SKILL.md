---
name: coding-principles
description: >
  Implementation discipline for any coding task — authoring, modifying,
  fixing, refactoring, reviewing code. Carries the universal mantras in a
  three-tier hierarchy (goals, design, pruning) and 20 numbered principles
  with severity tags (must / should / could). Router pattern: SKILL.md
  loads always; `references/` holds generic prose (mantras, principles,
  glossary, smell→principle diagnostic catalog); `capabilities/` holds
  language-specific entry points (bash, python, typescript, rust) and the
  review-mode workflow, each as `capability.md` per the Agent Skills
  convention. Load capabilities on
  demand based on file extensions or task type. Triggers when the user
  asks to write, implement, add, fix, refactor, clean up, or review code;
  or via /coding-principles. Skip for docs-only, config-only, pure-data,
  or ops/infra tasks.
allowed-tools: Read Grep
metadata:
  version: "1.0.0"
---

# coding-principles

## Purpose

Single source of implementation discipline for coding tasks. Loaded as active context so the agent applies the same rules every time without the user re-stating them per session.

## Design philosophy

This skill is built for *AI agents authoring code*, not for human teams iterating toward done. The distinction matters and shapes every choice below:

- **Optimize for first-pass correctness, not iteration speed.** An AI agent with the right rules can produce correct, modular, observable code in one pass. The classic human-velocity sequencing — "make it work, then right, then fast" — is deliberately *rejected* here because it would license shipping the works-but-ugly version. Each draft is expected to be right *and* simple *and* tested.
- **Severity (must / should / could) governs triage.** When several violations exist at once, fix musts first, recommend shoulds, apply coulds silently.
- **Mantra tier (Goals > Design > Pruning) governs design conflicts.** When two principles fight, the higher tier wins. Inside a tier, siblings are case-by-case — they answer different questions and rarely conflict head-on.
- **YAGNI is a check, not a veto.** Modular shape (small functions, narrow interfaces, isolated I/O, typed boundaries) is free at write-time and earned by the current feature. Infrastructure (one-impl interfaces, plugin points, factories, configuration layers) requires evidence of need and is deferred.
- **The skill is read-only.** It shapes the Edit/Write calls that follow; it does not run linters, formatters, or refactor tools. Pair with `simplify` (post-edit cleanup) and `repo-conventions` (file-local style) — see "Relationship to other skills" below.

When in doubt about how a rule applies: prefer the interpretation that produces simpler, more typed, more testable, more observable code in *this* draft — not the one that anticipates future flexibility.

## What this skill is and is not

- **Is:** a rulebook the agent reads before and during code changes. Decisions about scope, abstraction, error handling, comments, and compatibility flow through this skill's rules.
- **Is not:** a linter, a code reviewer, a refactor tool, or a doc generator. It does not modify files. It does not produce a report. It shapes how *other* writes happen.

Pairs with `simplify` (post-hoc cleanup of changed code), `repo-conventions` (what the repo already declares), and `git-toolkit` (how the change gets narrated).

## File layout

This SKILL.md is a **router**. Two child trees:

| Tree | Purpose |
| ---- | ------- |
| `references/` | Generic, language-agnostic content. Prose for mantras + principles + how-to-review. |
| `capabilities/` | Language-specific content. Idioms + tooling floor + before/after code examples anchored to numbered principles. One file per language. |

| File                                          | Contents                                                          |
| --------------------------------------------- | ----------------------------------------------------------------- |
| `references/mantras.md`                       | Full prose for all 16 mantras, organized by tier; mantra→principle reverse map |
| `references/principles.md`                    | Full prose for all 20 numbered principles, with severity tags; links to capabilities for code examples |
| `references/glossary.md`                      | Defines terms used throughout (boundary, shape, infrastructure, pure function, trust line, etc.) |
| `references/smells.md`                        | Diagnostic catalog: observable code smells → anchoring principle(s); used in review mode and write-mode self-check |
| `references/api-design.md`                    | Language-agnostic API conventions (REST/GraphQL/gRPC): status codes, idempotency, pagination, versioning, error shapes |
| `references/persistence.md`                   | Language-agnostic DB practices: N+1, pooling, transactions, migrations, prepared statements, caching |
| `references/observability.md`                 | Language-agnostic telemetry: OpenTelemetry model (traces/metrics/logs), structured logging, RED/USE, correlation IDs |
| `references/platform-matrix.md`               | OS × concern matrix (Linux/macOS/Windows): paths, line endings, case sensitivity, signals, GNU vs BSD coreutils, CI matrix |
| `references/resilience.md`                     | Fault-tolerance patterns: timeouts/deadlines, retries+backoff+jitter, circuit breakers, bulkheads, graceful degradation, DLQs |
| `references/data-handling.md`                  | Cross-language correctness footguns: dates/timezones, numbers/money, text/encoding (UTF-8, normalization) |
| `references/architecture.md`                  | Project structure & layering: hexagonal/clean, dependency direction, package-by-feature, when NOT to layer |
| `references/configuration.md`                 | Config & feature flags: source precedence, validate-at-startup, secrets injection, flag lifecycle |
| `references/testing.md`                        | Testing strategy: test pyramid, double taxonomy (stub/mock/fake/spy), contract/snapshot/mutation/property/fuzz, flaky-test killers, coverage-as-signal |
| `references/refactoring.md`                    | Safe refactoring: under-green-tests, characterization tests, two-hats, expand-contract / branch-by-abstraction / strangler-fig, refactor-vs-rewrite |
| `capabilities/<lang>/...`                     | Per-language capability directories (`bash`, `python`, `typescript`, `rust`) — see file-set below |
| `capabilities/review/capability.md`           | Review-mode workflow: scan diff → tag findings by principle + severity → triage → report |
| `capabilities/review/best-practices.md`       | Conventional Comments format, approve-vs-request-changes, reviewer load discipline |

Capabilities follow the Agent Skills convention: one directory per capability, with `capability.md` as the entry point and optional frontmatter (used here so each capability is portable / promotable to standalone if reuse demands it). Each **language** capability directory (`bash`, `python`, `typescript`, `rust`) carries the same eight-file set:

| File in `capabilities/<lang>/` | Contents | Load when |
| ------------------------------ | -------- | --------- |
| `capability.md`                | Positive *rules* only — idioms, error/style discipline, tooling floor, verification. Pure prose, no code. | Always, for any task in that language |
| `anti-patterns.md`             | Language-specific smells / what-not-to-do | Review-mode scans, pre-commit smell checks |
| `examples.md`                  | Before/after code anchored to numbered principles | Matching patterns at write-time, validating fixes |
| `best-practices.md`            | External standards (PEPs, Rust API Guidelines, Google Shell Style Guide), modern toolchain consensus, documentation conventions | Justifying choices against industry standards |
| `performance.md`               | Performance idioms + "measure first" discipline | Hot-path / large-data work only |
| `concurrency.md`               | Concurrency model, decision matrix, correctness traps | Parallelism / async / shared-state work |
| `project-structure.md`         | Language structure mechanics (modularity unit, visibility, ports/adapters, DI, layout) — the *how* for `references/architecture.md`'s *why* | Structuring / restructuring a project |
| `dependencies.md`              | Dependency mechanics: version pinning (default: pin exact for apps, range for published libs), lockfiles, audit tools, update cadence | Adding / updating / auditing dependencies |

The entry point `capability.md` carries callouts pointing at every sibling, so the agent always knows what's available. Load just `capability.md` for routine writes; pull in siblings on demand.

Load mantras/principles references when you need nuance; the one-line summaries below are enough for routine application. Load `capabilities/review/capability.md` when reviewing existing code. Load a **cross-language reference** (in `references/`) when the code touches that concern, regardless of language:

| Reference | Load when the code… |
| --------- | ------------------- |
| `api-design.md` | exposes or consumes a network API (REST/GraphQL/gRPC) |
| `persistence.md` | reads or writes a datastore |
| `observability.md` | runs in production and emits logs/metrics/traces |
| `platform-matrix.md` | must run on more than one OS (paths, shells, coreutils) |
| `resilience.md` | makes outbound calls / coordinates distributed work |
| `data-handling.md` | handles timestamps, money/precise math, or external text |
| `architecture.md` | is being structured / restructured above the module level |
| `configuration.md` | reads config, env vars, secrets, or feature flags |
| `testing.md` | needs a testing-strategy decision (what to test, which doubles, why flaky) |
| `refactoring.md` | is restructuring / cleaning up / modernizing existing code | Load a language capability only when the task touches that language's files.

## When to trigger

- User asks to write, implement, add, modify, fix, refactor, or clean up code.
- User asks to review a diff or PR for quality (not for security — that's a different skill).
- Any task where the agent will call Edit, Write, or NotebookEdit on source files.
- Explicit invocation: `/coding-principles`.

Do not trigger when:

- The task is exploratory ("how does X work?", "where is Y defined?") with no edit intent.
- The change is docs-only, config-only, or pure data (e.g. JSON fixtures).
- The user is asking for an ops/infra action (deploy, restart, rollback).
- A more specific skill already owns the task (e.g. `git-toolkit` for commit messages).

## Mantras (one-line summaries)

Full prose: `references/mantras.md`.

**Conflict resolution:** three tiers, tier wins over tier. Tier 1 *goals* outrank Tier 2 *design rules*, which outrank Tier 3 *pruning rules*. Inside a tier, siblings are case-by-case.

### Tier 1 — Goals (what we're trying to achieve)

1. **Readability first** — code is read more than written; optimize for the next reader.
2. **KISS** — boring code that obviously works beats elegant code that needs explanation.
3. **Testability** — units verifiable in isolation; if tests need many mocks, the design is wrong.
4. **Scalability** — system grows by *adding* pieces, not by *enlarging* existing ones.
5. **Observability** — production failures debuggable from logs alone; errors carry context.

### Tier 2 — Design (how we achieve the goals)

6. **SRP** — each function/module does one thing.
7. **Modular by composition** — small pieces *(shape)*, composed not inherited *(technique)*, minimum public surface *(boundary)*; delegate behavior, never the held object.
8. **Strong typing** — concrete types over escape hatches (`any`, `unknown`-unchecked, `dynamic`).
9. **Fail fast, fail loud** — validate at the boundary, never silently swallow.
10. **Immutability by default** — `const` / `readonly` / `final`; mutability is a justified choice.
11. **Make illegal states unrepresentable** — sum types over bags-of-optionals; let the compiler enforce the design.
12. **Locality of behavior** — code that changes together lives together; don't split for splitting's sake.
13. **Pure / impure separation** — functional core, imperative shell; I/O at the edges only.
14. **Explicit over implicit** — no magic globals, no auto-wiring; pass dependencies in.

### Tier 3 — Pruning (what we don't add)

15. **DRY** — extract patterns when there are three callers, not before.
16. **YAGNI** — a check, not a veto; prunes overgrowth, doesn't block reasonable up-front design.

## Numbered principles (titles)

Full prose: `references/principles.md`.

Each principle carries a severity tag — **must** (non-negotiable; treat violation as a bug), **should** (strong default; deviation needs a stated reason), **could** (preference; deviation is fine when surrounding code differs). Severity guides triage: when many things are wrong simultaneously, fix the **musts** first, recommend the **shoulds**, and silently apply the **coulds** unless they conflict with existing style.

1. **Match scope to the request** — *should* — do exactly what was asked; capture unrelated observations as follow-ups.
2. **Root cause over bandaid** — *must* — find the underlying cause; bug fixes need a reproducing test that fails first.
3. **Edit existing files; do not create new ones speculatively** — *should* — never create README/docs unless explicitly asked.
4. **No *speculative* generality (but earn the shape)** — *should* — modular shape is free; infrastructure (plugin points, factories) is not.
5. **Trust internal code; validate only at boundaries** — *should* — defensive code for impossible states hides real bugs.
6. **No backwards-compatibility shims unless asked** — *should* — rename, delete; do not leave aliases/re-exports.
7. **Comments explain *why*, not *what*** — *could* — default to none; avoid PR/ticket references.
8. **No half-implementations** — *must* — ship all of A/B/C or none; partial impls silently misbehave at runtime.
9. **Read before you edit** — *must* — match the file's local conventions even when they differ from your default.
10. **Verify the change works** — *must* — run tests/exercise UI/CLI; typecheck-passing is not "done."
11. **Reversibility shapes caution** — *must* — destructive actions need confirmation even after prior approval.
12. **Honor the user's stated preferences** — *must* — apply session/memory/CLAUDE.md prefs consistently.
13. **Security hygiene is a baseline** — *must* — no secrets in source/logs/errors; authorize at every state-touching handler.
14. **Prefer modular, composable, scalable designs — without over-engineering** — *should* — shape is free; infrastructure is not.
15. **Tests describe behavior, not implementation** — *should* — behavior-style names; mock at boundaries; avoid mocking-hell.
16. **Inject time, randomness, and external state** — *should* — never call `Date.now()` / `random()` / `os.environ` from business logic.
17. **Naming discipline** — *could* — descriptive over short; no `_old` / `_v2` / `_temp` suffixes; booleans as predicates. (*should* when names are actively misleading.)
18. **Single source of truth for state** — *should* — derive don't store; caches are deliberate exceptions with invalidation.
19. **Boundaries parse input and serialize output** — *should* — `(bytes) -> Typed` at entry, `Typed -> bytes` at exit; explicit serializers. (*must* when the boundary is security-relevant — auth, PII, deserialization.)
20. **No dead code, no commented-out code** — *could* — delete it; git remembers.

## Application checklist

Apply mentally; do not output the checklist.

**Before editing:**

- [ ] Do I understand the *why* of this task, not just the *what*?
- [ ] Is the scope minimal — am I about to touch only what was asked? (KISS, SRP)
- [ ] If this is a bug fix, do I have a test that fails for the right reason?
- [ ] Have I read the target file and a sample of callers?
- [ ] Does this repo declare a convention (style, naming, structure) I should honor?

**While editing:**

- [ ] Am I adding abstraction for one use case? → stop, inline it. (YAGNI)
- [ ] Am I duplicating an existing helper because finding it was harder than re-writing? → stop, find it.
- [ ] Is the piece I'm adding small, pure where practical, and replaceable without surgery? If no → reshape before continuing.
- [ ] Could I write a test for this without mocking more than one or two collaborators? If no → the shape is wrong; reshape before continuing.
- [ ] When the next related feature lands, will it be an *added* piece or a *rewrite* of this one? If rewrite → reshape now.
- [ ] Am I adding a plugin point / strategy interface / config layer for a single caller? → stop, inline it.
- [ ] Am I reaching for an escape-hatch type (`any`, `unknown`-unchecked, `dynamic`, `Object`)? → stop, model the type.
- [ ] Am I adding a guard for a state internal code cannot produce? → stop, delete it.
- [ ] Am I logging a secret, token, or raw request body? → stop, redact.
- [ ] Am I declaring a mutable variable where an immutable one would do? → stop, make it const/readonly/final.
- [ ] Am I modeling state as a bag-of-optionals where a discriminated union would forbid the bad combos? → stop, use a sum type.
- [ ] Am I calling `Date.now()` / `Math.random()` / `os.environ` / `uuid()` from inside business logic? → stop, inject it at the boundary.
- [ ] Am I splitting a coherent block into many tiny pieces with no clear concept boundaries? → stop, keep it together.
- [ ] Am I extending a base class to reuse code (not to model is-a)? → stop, use composition.
- [ ] Am I exporting something a caller does not need? → stop, make it private.
- [ ] Am I reading env / config / globals from deep in the call stack? → stop, pass it in from the edge.
- [ ] Am I storing a value I could derive from existing state? → stop, derive it on read.
- [ ] Am I shipping `JSON.stringify(internal_object)` over the wire? → stop, write an explicit serializer.
- [ ] Am I about to comment out a block instead of deleting it? → stop, delete; git remembers.
- [ ] Are my names abbreviated or suffixed with `_old` / `_v2` / `_temp`? → stop, rename.
- [ ] Am I silently swallowing an error (`except: pass`, `catch (_) {}`, ignored Result)? → stop, fail loud or handle explicitly.
- [ ] Will a failure in this code be debuggable from logs alone? If no → add structured context to the error or log at the edge.
- [ ] Am I writing a comment that restates the code? → stop, delete it.
- [ ] Am I adding a fallback / shim "just in case"? → stop, ask first.

**Before reporting done:**

- [ ] Did I verify the change actually does what it claims (run, test, exercise)?
- [ ] Did I leave anything half-done that I should flag?
- [ ] Are unrelated observations captured as follow-ups rather than silent edits?
- [ ] Is the summary one or two sentences — what changed and what's next?

## Anti-patterns (in the code you write)

- **"While I'm here…"** — opportunistic refactors that balloon the diff. Open a separate PR if it matters.
- **Defensive null checks on values that cannot be null.** Trust the types.
- **`try/except` that swallows the exception with a log line.** Either handle it meaningfully or let it propagate.
- **Renaming things mid-task to match personal preference** when the existing name is clear and consistent with the file.
- **Adding `TODO` / `FIXME` / `XXX` markers without a ticket or condition** — they become permanent noise.
- **Writing tests after the implementation only when the tests pass on the first try** — that path tests nothing. Either TDD properly, or write the tests deliberately against the spec.
- **Claiming "the change is backwards compatible"** without checking that callers exist and exercise the changed surface.
- **Creating `utils.ts` / `helpers.py` modules** for one or two functions. Inline or co-locate with the one caller until a second caller exists.
- **Wrapping library calls in thin pass-through wrappers** "for testability" — the wrapper is the thing that needs a test now.

## Anti-patterns (in how you apply this skill)

These are failure modes of *using* this skill, not of writing code. Overzealous application is its own anti-pattern: a rulebook that lectures, refuses, or noises up every interaction is a rulebook that gets ignored.

- **Don't lecture the user about a principle they didn't violate.** If the user wrote good code, say nothing about it. Reciting "per principle 5, your validation is correctly at the boundary" is noise.
- **Don't preface edits with "per principle X, …"** in the user-facing summary. The user does not need the principle citation; they need the change. Cite the principle only when the user asks *why* you made a choice, or when reviewing someone else's code (review mode).
- **Don't add tests for trivial changes just to satisfy testability.** Testability is a property of the design, not a target metric. A one-line typo fix does not need a new test; principle 2's reproducing-test rule applies to bug *fixes*, not to every change.
- **Don't refuse `any` / `unknown` / escape hatches when they are the right answer at a boundary.** Strong typing is a default, not an absolute. The line that parses arbitrary JSON has to start with `unknown`.
- **Don't open follow-up PRs for cleanup that wasn't requested.** Match scope (principle 1). Note observations in the end-of-turn summary; let the user decide what to do.
- **Don't apply this skill to docs-only, config-only, or pure-data changes.** Skip the load. The triggers explicitly exclude these.
- **Don't argue principle precedence after the user has decided.** Once the user picks a tradeoff ("yes, ship the speculative interface; we'll need it soon"), apply it. Principle 12 — honor stated preferences.
- **Don't enforce **could** findings when the surrounding code already deviates.** Local consistency wins (principle 9). If every existing function uses `_old` suffixes, do not single out the one new line.
- **Don't moralize about user choices.** "This is technical debt" / "this is bad practice" framing implies judgment. Describe the consequence ("this couples X to Y, so future changes to Y will require touching X"), not the verdict.
- **Don't volunteer review-mode framing when the user asked you to write code.** Write the code; if it's good, ship it. Review-mode (`references/review-mode.md`) is for explicit review tasks.

The brake on this skill is: when in doubt, write less *about* the code and more *of* it.

## Capabilities

Capabilities load on demand based on either a *file-extension trigger* (language capabilities) or a *task-type trigger* (workflow capabilities). All follow the same `capabilities/<name>/capability.md` layout.

### Language capabilities (file-extension trigger)

For idioms, tooling floor, language-specific anti-patterns, and code examples anchored to numbered principles:

| Language       | Trigger (file extension / shebang)                 | Capability entry point                       |
| -------------- | -------------------------------------------------- | -------------------------------------------- |
| Bash           | `*.sh`, `*.bash`, `#!/usr/bin/env bash` shebang    | `capabilities/bash/capability.md`            |
| Python         | `*.py`, `pyproject.toml` context                   | `capabilities/python/capability.md`          |
| TypeScript     | `*.ts`, `*.tsx`, `*.mts`, `tsconfig.json` context  | `capabilities/typescript/capability.md`      |
| Rust           | `*.rs`, `Cargo.toml` context                       | `capabilities/rust/capability.md`            |

Load only when the task touches files in that language. Reading all four for a Python-only change wastes context. When a change spans languages, load both capabilities.

For languages not covered above (Go, Ruby, Java, C/C++, Swift, etc.), fall back to the core principles plus what `repo-conventions` reports for the specific repo. Propose a new capability if the language is recurring in this user's work.

### Workflow capabilities (task-type trigger)

| Workflow       | Trigger                                            | Capability entry point                       |
| -------------- | -------------------------------------------------- | -------------------------------------------- |
| Review         | Reviewing an existing diff / PR / branch / change  | `capabilities/review/capability.md`          |

Default mode is **write-mode** (avoid violations as you author code) — that workflow is documented inline in this router (the application checklist and anti-patterns sections). **Review-mode** (find violations in someone else's change) loads from `capabilities/review/capability.md`.

Capabilities extend the core principles; they do not override them. If a capability and the core conflict, the conflict is a bug — flag it.

## Output behavior

This skill produces no output of its own. It loads as context and shapes downstream tool calls (Edit, Write) and end-of-turn summaries. If invoked explicitly with `/coding-principles` and no follow-up task, respond with: *"Loaded. What are we coding?"* — nothing more.

## Relationship to other skills

- **`simplify`** — a separate post-edit refactor pass on already-written code (reuse opportunities, dead branches, redundant abstractions). This skill applies during *writing* (avoid violations via the router checklist) and during *review* (find violations via the review capability); `simplify` runs *after* the edits are made — typically against the diff before commit — to suggest cleanups this skill could have prevented but didn't. Sequence on a typical task: write with `coding-principles` → run `simplify` on the diff → fix → commit. Do not load both as the same task lens; they answer different questions (this one shapes the change; `simplify` polishes what's already there).
- **`repo-conventions`** — tells you what the repo already declares. This skill tells you how to think; `repo-conventions` tells you what this specific repo expects. When they conflict, repo-local conventions win for style decisions; principles win for design decisions.
- **`git-toolkit`** — handles how the change is narrated (commits, PRs, branches). This skill is silent on narration.
- **`security-review`** — separate concern; security review evaluates threat models, this skill evaluates implementation hygiene.
- **`docs-steward`** — separate concern; docs formatting and lint, not code.

## Edge cases

- **Spike / prototype code** — the user asks for a quick exploratory implementation. Relax principles 4 (speculative generality is impossible since the prototype is the proof) and 10 (verification depth scales with intent). Keep 1, 2, 5, 6 — even prototypes should be scoped, root-caused, non-defensive, and unencumbered by shims.
- **Codebase with strong existing patterns that violate these principles** — local consistency wins. Note the divergence in the summary but match the file. Suggest a separate cleanup task if the user is open to it.
- **Generated code (codegen output, migrations)** — these principles do not apply to the generator's output; they apply to the generator itself.
- **Tests** — same principles, with one addition: tests should fail clearly when the thing under test breaks. A test that always passes is worse than no test.
