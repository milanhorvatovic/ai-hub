---
name: coding-principles
description: >
  Implementation discipline for any coding task — writing, modifying, fixing,
  refactoring, or reviewing code. Carries 16 universal mantras (tiers: goals,
  design, pruning) and 21 numbered principles with must/should/could severity,
  with on-demand language capabilities (bash, python, typescript, rust), a
  cross-language comments capability, and a review workflow. Triggers when the
  user asks to write, implement, add, fix, refactor, clean up, or review code,
  on planning docs (plans, ADRs, work specs) that mention comments or
  docstrings, or via /coding-principles. Skip for other docs-only,
  config-only, pure-data, or ops/infra tasks.
allowed-tools: Read Grep
metadata:
  version: "1.0.0" # x-release-please-version
---

# coding-principles

## Purpose

Single source of implementation discipline for coding tasks. Loaded as active context so the agent applies the same rules every time without the user re-stating them per session.

## Design philosophy

Built for *AI agents authoring code*, optimizing for first-pass correctness — right *and* simple *and* tested in one draft. The human "make it work, then right, then fast" sequence is deliberately rejected: it would license shipping the works-but-ugly version. Two operating rules follow: **severity** (must / should / could) governs triage, and **mantra tier** (Goals > Design > Pruning) governs conflicts. When in doubt, prefer the interpretation that yields simpler, more typed, more testable, more observable code in *this* draft over one that anticipates future flexibility.

## What this skill is

A rulebook the agent reads before and during code changes — scope, abstraction, error handling, comments, and compatibility decisions flow through its rules. It is read-only: it does not modify files, emit a report, or run linters, formatters, or refactor tools; it shapes how the Edit/Write calls that follow happen. Adjacent concerns (post-edit cleanup, repo-local conventions, change narration) are out of scope — see "Scope boundaries" below.

## File layout

This SKILL.md is the always-loaded **router** — the mantra/principle summaries, checklist, and anti-patterns below cover routine work. Load deeper material on demand:

- **Full prose** — `references/mantras.md` (all 16 mantras by tier + reverse map), `references/principles.md` (all 21 principles, full text + severity), `references/glossary.md` (boundary, shape, infrastructure, pure function, trust line, …), `references/smells.md` (observable smell → anchoring principle, for review and write-mode self-check).
- **Cross-language concern references** — load when the code touches the concern, regardless of language:

| Reference | Load when the code… |
| --------- | ------------------- |
| `references/api-design.md` | exposes or consumes a network API (REST/GraphQL/gRPC) |
| `references/persistence.md` | reads or writes a datastore |
| `references/observability.md` | runs in production and emits logs/metrics/traces |
| `references/platform-matrix.md` | must run on more than one OS (paths, shells, coreutils) |
| `references/resilience.md` | makes outbound calls / coordinates distributed work |
| `references/data-handling.md` | handles timestamps, money/precise math, or external text |
| `references/architecture.md` | is structured / restructured above the module level |
| `references/configuration.md` | reads config, env vars, secrets, or feature flags |
| `references/testing.md` | needs a testing-strategy decision (what to test, which doubles) |
| `references/refactoring.md` | is restructuring / cleaning up / modernizing existing code |

- **Language capabilities** (see Capabilities below) — load `capabilities/<lang>/capability.md` for the task's language. Each language directory holds `capability.md` plus a `references/` subdir of on-demand supporting files, pulled in as the work calls for them: `anti-patterns.md` (review/smell scans), `examples.md` (before/after code), `best-practices.md` (external standards), `performance.md` (hot paths), `concurrency.md` (async/shared state), `project-structure.md` (layout/DI), `dependencies.md` (pinning/lockfiles/audit). The `capability.md` entry point links them.

**Reference direction.** Pointers run one way: this router and the capability entry points may point into `capabilities/`; the shared `references/` files above point only sideways to each other or up to here. A shared reference that needs to name a capability names it in prose — "the matching language capability's project-structure reference" — never by path, because a path makes the reference unloadable without hauling a capability along, and a reference and a capability pointing at each other is a cycle with no entry point. Two shared references naming each other is a different thing and is expected — they sit at the same level, and either loads without the other.

## When to apply

Applies whenever the agent will write, implement, fix, refactor, or clean up code (any Edit/Write/NotebookEdit on source), review a diff/PR for quality, or author a planning-phase document (plan, ADR, work spec) that mentions comments, docstrings, or annotations — there the comments capability supplies the rubric the plan should reflect. Skip it for exploration-only tasks ("how does X work?"), docs-only / config-only / pure-data changes (except the planning documents just named), ops/infra actions (deploy, restart, rollback), and security review (a separate concern). The skip governs triggering, not reach: once a task has triggered the skill, the comments capability's rubric covers every file that task touches — configs, workflows, and markdown included. When delegating code authoring to a sub-agent, either instruct it in the spawn prompt to load `capabilities/comments/capability.md` before authoring, or review its diff against that capability before committing.

## Mantras (one-line summaries)

Full prose: `references/mantras.md`.

**Conflict resolution:** three tiers, tier wins over tier. Tier 1 *goals* outrank Tier 2 *design rules*, which outrank Tier 3 *pruning rules*. Inside a tier, siblings are case-by-case — they answer different questions and rarely conflict head-on.

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
7. **Comments explain *why*, not *what*** — *could* — the code says the what; a comment carries the why; avoid PR/ticket references.
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
21. **Comments earn their place: clear, direct, meaningful** — *should* — each comment carries what the code cannot (an invariant, a surprise, a stated deviation, an anchored workaround, a security assumption, profiled performance); revise or remove the rest; value gate before principle 7's content gate.

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
- [ ] Am I about to write any comment at all? → load `capabilities/comments/capability.md` and apply the rubric before writing.
- [ ] Am I writing a comment that restates the code? → stop, delete it.
- [ ] Am I adding a fallback / shim "just in case"? → stop, ask first.

**Before reporting done:**

- [ ] Did I verify the change actually does what it claims (run, test, exercise)?
- [ ] Did a sub-agent author any of this code? → review its diff against `capabilities/comments/capability.md` before reporting.
- [ ] Did I leave anything half-done that I should flag?
- [ ] Are unrelated observations captured as follow-ups rather than silent edits?
- [ ] Is the summary one or two sentences — what changed and what's next?

## Anti-patterns (in the code you write)

- **"While I'm here…"** — opportunistic refactors that balloon the diff. Open a separate PR if it matters.
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
- **Don't enforce `could` findings when the surrounding code already deviates.** Local consistency wins (principle 9). If every existing function uses `_old` suffixes, do not single out the one new line.
- **Don't moralize about user choices.** "This is technical debt" / "this is bad practice" framing implies judgment. Describe the consequence ("this couples X to Y, so future changes to Y will require touching X"), not the verdict.
- **Don't volunteer review-mode framing when the user asked you to write code.** Write the code; if it's good, ship it. Review-mode (`capabilities/review/capability.md`) is for explicit review tasks.

The brake on this skill is: when in doubt, write less *about* the code and more *of* it.

## Capabilities

Load on demand: language capabilities by the file's language; the comments capability when the task touches comment-bearing files, plans work that mentions comments or docstrings, or is about to write any comment; the review capability for review tasks. Load only what the task touches — reading all four languages for a Python change wastes context.

| Capability | Trigger | Path |
| ---------- | ------- | ---- |
| bash | `*.sh`, `*.bash`, bash shebang | capabilities/bash/capability.md |
| python | `*.py`, `pyproject.toml` | capabilities/python/capability.md |
| typescript | `*.ts`, `*.tsx`, `*.mts`, `tsconfig.json` | capabilities/typescript/capability.md |
| rust | `*.rs`, `Cargo.toml` | capabilities/rust/capability.md |
| comments | about to write any comment in a task this skill covers; comment-bearing files the task touches (source, config, workflow, infra, script, migration, test, notebook, markdown); plan docs that mention comments or docstrings | capabilities/comments/capability.md |
| review | reviewing an existing diff / PR / change | capabilities/review/capability.md |

For languages without a capability (Go, Ruby, Java, C/C++, Swift, …), use the core principles plus the repo's declared conventions; propose a new capability if the language recurs. Capabilities extend the core, never override it — a conflict is a bug, so flag it. Write-mode (avoid violations as you author) is the default and lives in this router; review-mode loads from the review capability.

## Output behavior

This skill produces no output of its own. It loads as context and shapes downstream tool calls (Edit, Write) and end-of-turn summaries. If invoked explicitly with `/coding-principles` and no follow-up task, respond with: *"Loaded. What are we coding?"* — nothing more.

## Scope boundaries

This skill covers implementation discipline only. Adjacent concerns are deliberately out of scope and belong to separate passes or tools:

- **Post-edit cleanup** — a separate refactor pass over already-written code (reuse opportunities, dead branches, redundant abstractions). This skill applies during *writing* (avoid violations via the router checklist) and during *review* (find violations via the review capability); cleanup runs *after* the edits are made, typically against the diff before commit, to catch what slipped through. Sequence on a typical task: write → clean up the diff → fix → commit. The two are different lenses — this one shapes the change; cleanup polishes what's already there.
- **Repo-local conventions** — what the specific repo already declares (style, naming, and structure in `CLAUDE.md` / `AGENTS.md` / `CONTRIBUTING.md`, lint configs, and sibling files). This skill tells you how to think; the repo's conventions tell you what this repo expects. When they conflict, repo-local conventions win for style decisions; principles win for design decisions.
- **Change narration** — how the change is described in commits, PRs, and branches. This skill is silent on narration.
- **Security review** — threat-model evaluation. This skill evaluates implementation hygiene, not threat models.
- **Docs formatting** — documentation formatting and lint, not code. Comment *content* inside files a triggered coding task touches is in scope through the comments capability; only formatting and lint stay out.

## Edge cases

- **Spike / prototype code** — the user asks for a quick exploratory implementation. Relax principles 4 (speculative generality is impossible since the prototype is the proof) and 10 (verification depth scales with intent). Keep 1, 2, 5, 6 — even prototypes should be scoped, root-caused, non-defensive, and unencumbered by shims.
- **Codebase with strong existing patterns that violate these principles** — local consistency wins. Note the divergence in the summary but match the file. Suggest a separate cleanup task if the user is open to it.
- **Generated code (codegen output, migrations)** — these principles do not apply to the generator's output; they apply to the generator itself.
- **Tests** — same principles, with one addition: tests should fail clearly when the thing under test breaks. A test that always passes is worse than no test.
