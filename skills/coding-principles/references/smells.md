# Code smells → principles

Diagnostic catalog. Given an observable symptom in code under review or in code you're about to write, this file maps it back to the numbered principle(s) and mantra(s) that explain why it's a smell and what to do about it.

## When to consult

- **Review mode** — after spotting something off in a diff, find the principle anchor here before writing the finding. A smell without a principle anchor is taste, not a rule (see `../capabilities/review/capability.md`).
- **Write mode (self-check)** — when you've just written something that feels off but can't name why, grep this file for the symptom.
- **Debugging a design discussion** — when two contributors disagree on whether something is acceptable, the principle anchor is the common reference.

## How to read an entry

Each entry has four parts:

- **Smell** — what you observe.
- **Anchor** — the principle(s) and/or mantra(s) that explain why it is a smell.
- **Severity** — inherits from the anchor's severity (must / should / could).
- **Fix** — one-line direction; full details in the linked principle.

The smells are grouped by category. Some smells appear in multiple categories — the entry lives where its primary symptom is observed.

---

## Tests

### Mocking hell — five+ mocks per test

- **Anchor:** principle 15 (mock at boundaries) — but the deeper signal is SRP (mantra) or principle 14 (small functions). When the subject needs five mocks, the subject is doing five things.
- **Severity:** *should* (P15) / *should* (SRP)
- **Fix:** split the subject by responsibility before splitting the test. If the test cannot avoid five collaborators, it is an integration test pretending to be a unit test.

### Test passes on first try (was never red)

- **Anchor:** principle 2 (failing-first test for bug fixes)
- **Severity:** *must*
- **Fix:** for bug fixes, write the test against the spec first, watch it fail, then fix the code. For new features, deliberately break the implementation to confirm the test catches it.

### Test patches a `_private_helper`

- **Anchor:** principle 15 (mock at boundaries, not internals)
- **Severity:** *should*
- **Fix:** mock the real boundary (HTTP client, DB driver, clock, mailer) instead. Tests against internals break on every refactor.

### `time.sleep(0.1)` in a test

- **Anchor:** principle 16 (inject time)
- **Severity:** *should* (escalates to *must* in CI — sleeps cause flakes)
- **Fix:** inject a fake clock; advance it explicitly in the test.

### Test names like `test_user_1`, `test_2`

- **Anchor:** principle 15 (tests describe behavior)
- **Severity:** *should*
- **Fix:** rename to `test_<subject>_<behavior>_<condition>`: `test_create_user_returns_400_when_email_invalid`.

### One test asserts a dozen unrelated things

- **Anchor:** principle 15 (one behavior per test)
- **Severity:** *should*
- **Fix:** split. A single failure should point at a single behavior.

---

## Types

### `any` / `Any` / `unknown` / `dynamic` in business code

- **Anchor:** mantra strong typing
- **Severity:** *should* (in business code) / acceptable at trust boundaries before parsing
- **Fix:** at the boundary, parse into a typed value; never propagate the escape hatch inward.

### `dict[str, Any]` / `Record<string, unknown>` as a return type

- **Anchor:** principle 19 (typed boundaries) + mantra strong typing
- **Severity:** *should*
- **Fix:** return a typed model (`pydantic.BaseModel`, `dataclass`, named TS type).

### `cast<T>(x)` without a preceding runtime check

- **Anchor:** mantra strong typing
- **Severity:** *should*
- **Fix:** parse the value (schema validator) before casting; or restructure so the cast isn't needed.

### `isinstance(x, ...)` inside code receiving a typed parameter

- **Anchor:** principle 5 (trust internal code)
- **Severity:** *should*
- **Fix:** remove the runtime type check; rely on the static type. Validate at the boundary where the value entered.

### Bag-of-optionals modeling exclusive states (`{loading?, data?, error?}`)

- **Anchor:** mantra make illegal states unrepresentable
- **Severity:** *should*
- **Fix:** sum type / discriminated union: `Idle | Loading | Success<T> | Error`.

### Boolean explosion: parallel `is_x`, `has_y`, `should_z` flags that are really one enum

- **Anchor:** mantra make illegal states unrepresentable + principle 17 (naming)
- **Severity:** *should*
- **Fix:** model the state as one enum / sum type. `status: 'idle' | 'running' | 'done'` beats `is_running + is_done + is_idle`.

---

## Errors

### `try: ... except Exception: pass`

- **Anchor:** mantra fail-fast-fail-loud + principle 13 (security hygiene; silenced errors hide breaches)
- **Severity:** *must*
- **Fix:** handle the specific exception meaningfully or let it propagate. Logging-and-swallowing is a future incident.

### `try: ... except: log.error(...)` then continue

- **Anchor:** mantra fail-fast-fail-loud
- **Severity:** *must*
- **Fix:** either the error is recoverable (handle it explicitly) or it is not (propagate). Logging is not handling.

### `raise ValueError("invalid")` with no context

- **Anchor:** mantra observability + principle 13
- **Severity:** *should*
- **Fix:** include what was attempted, with what inputs, against what state: `raise ValueError(f"invalid email: {email!r} (user_id={user_id})")`.

### Manual None-propagation: `if x is None: return None` chains

- **Anchor:** mantra strong typing + mantra make illegal states unrepresentable
- **Severity:** *should*
- **Fix:** model the absence at the type level (`Optional[T]` + structured handling, `Result<T, E>`, monadic combinators); or eliminate the optional at the boundary.

### Error response body leaks stack traces / SQL / file paths

- **Anchor:** principle 13 (security)
- **Severity:** *must*
- **Fix:** generic message + request ID to the client; full detail to internal logs only.

---

## I/O and external state

### `Date.now()` / `time.now()` / `Instant::now()` inside business logic

- **Anchor:** principle 16 (inject time)
- **Severity:** *should*
- **Fix:** take a `clock` parameter; wire the real clock at the entry point.

### `Math.random()` / `random.random()` / `Uuid::new_v4()` inside business logic

- **Anchor:** principle 16 (inject randomness)
- **Severity:** *should*
- **Fix:** take an `rng` / `id_source` parameter; wire the real source at the entry point.

### `os.environ` / `process.env` / `std::env::var` deep in the call stack

- **Anchor:** principle 16 + mantra explicit-over-implicit
- **Severity:** *should*
- **Fix:** read env once at startup; pass the resolved value down.

### Module-level mutable state / package-private globals

- **Anchor:** mantra pure/impure separation + principle 14 (hidden state is debt)
- **Severity:** *should*
- **Fix:** make the state a parameter or a member of an object owned by the entry point.

### DB call interleaved with a business decision in the same function

- **Anchor:** mantra pure/impure separation (functional core, imperative shell)
- **Severity:** *should*
- **Fix:** load all the data first (impure shell), pass it to a pure function that makes the decision, then act on the result (impure shell).

### `JSON.stringify(internalObject)` over the wire

- **Anchor:** principle 19 (serialize at boundary)
- **Severity:** *should* (*must* when the boundary is security-relevant — auth, PII)
- **Fix:** write an explicit serializer (`toPublicX`) that chooses which fields cross.

### Inbound HTTP handler accepts `dict` / `Value` / `any`

- **Anchor:** principle 19 (parse at boundary)
- **Severity:** *should* (*must* if security-relevant)
- **Fix:** parse into a typed request model at the entry; downstream code receives the typed value.

---

## Structure

### `class Subclass extends BaseClass` for code reuse (not is-a)

- **Anchor:** mantra modular-by-composition (technique: composition over inheritance)
- **Severity:** *should*
- **Fix:** hold the collaborator instead of extending it. Inheritance is for true is-a relationships the language idiomatically demands.

### Pass-through accessors: `obj.getInternalSocket()`, `obj.getRawClient()`

- **Anchor:** mantra modular-by-composition (the trap: delegate behavior, not the held object)
- **Severity:** *should*
- **Fix:** expose `obj.send(msg)`, not the internal collaborator. The held thing is an implementation detail.

### A `utils.ts` / `helpers.py` module containing 1-2 functions

- **Anchor:** anti-pattern list in SKILL.md; mantra locality of behavior
- **Severity:** *could*
- **Fix:** inline into the one caller until a second caller appears. Generic "utils" buckets accumulate noise.

### 200-line function with one decision tree

- **Anchor:** mantra SRP + principle 14 (small functions)
- **Severity:** *should*
- **Fix:** extract by concept (parse / validate / decide / persist), not by line count. Match where natural seams are.

### Eight 8-line functions chained through callbacks where one 60-line function would do

- **Anchor:** mantra locality of behavior (over-splitting is also a smell)
- **Severity:** *should*
- **Fix:** merge back. Splitting that fragments a single concept makes the code harder to read.

### Interface / abstract class with one implementation

- **Anchor:** principle 4 (no speculative generality)
- **Severity:** *should*
- **Fix:** delete the interface; promote the impl. Extract the seam when the second impl exists.

### Configuration flag with no current caller toggling it

- **Anchor:** principle 4 (no speculative generality)
- **Severity:** *should*
- **Fix:** delete the flag; inline the default branch.

### `index.ts` / barrel file re-exporting forty things

- **Anchor:** mantra modular-by-composition (boundary: minimum public surface)
- **Severity:** *should*
- **Fix:** re-export only what callers outside the package need; the rest stays internal.

### Two values that must stay in sync (e.g. `items` and a cached `total`)

- **Anchor:** principle 18 (single source of truth)
- **Severity:** *should*
- **Fix:** derive one from the other on read. If caching is justified (measured), implement and test invalidation alongside.

---

## Naming

### Decay suffixes: `_old`, `_new`, `_v2`, `_temp`, `Legacy`

- **Anchor:** principle 17 (naming discipline)
- **Severity:** *could* (*should* when names are actively misleading)
- **Fix:** name the replacement for what it *does*; delete the original when the migration completes.

### `tmp` / `temp` as a field, module, or public symbol

- **Anchor:** principle 17
- **Severity:** *could*
- **Fix:** reserve `tmp`/`temp` for true throwaways scoped to a few lines.

### Single-letter names outside loop indices

- **Anchor:** principle 17
- **Severity:** *could*
- **Fix:** descriptive names; canonical short names (`i`, `j`, `k` in loops; `id`, `url`, `db`, `http` as standalone) excepted.

### Boolean named as a noun: `admin`, `access`

- **Anchor:** principle 17 (booleans are predicates)
- **Severity:** *could*
- **Fix:** `is_admin`, `has_access`, `should_retry`, `can_delete`.

### Cryptic abbreviations: `cnt`, `usr`, `mgr`, `svc`

- **Anchor:** principle 17
- **Severity:** *could*
- **Fix:** write them out. The five characters saved at write-time cost ambiguity on every read.

### Function name needs a docstring to explain its basic purpose

- **Anchor:** principle 17 (function names describe what they do)
- **Severity:** *should*
- **Fix:** rename the function. `get_user`, `ensure_user`, `find_user` each carry their semantics.

---

## Comments and dead code

### Comment restates the code: `i = i + 1  # increment i`

- **Anchor:** principle 7 (comments explain why, not what)
- **Severity:** *could*
- **Fix:** delete the comment. The code already says it.

### Comment references a specific PR / ticket / caller (`// added for X flow`)

- **Anchor:** principle 7
- **Severity:** *could*
- **Fix:** move the context to the commit message; delete the comment.

### Commented-out code block

- **Anchor:** principle 20 (no commented-out code)
- **Severity:** *could*
- **Fix:** delete. Git history is searchable.

### Functions / classes / constants no caller reaches

- **Anchor:** principle 20 (no dead code)
- **Severity:** *could*
- **Fix:** delete with their references. Compiler / linter usually flags them.

### Bare `TODO` / `FIXME` / `XXX` with no ticket, no date, no condition

- **Anchor:** principle 20
- **Severity:** *could*
- **Fix:** delete or replace with a tracked item. Permanent uncertainty is debt.

### Unused imports

- **Anchor:** principle 20
- **Severity:** *could*
- **Fix:** delete. Most linters auto-fix.

---

## Security

### API keys, tokens, passwords, signing secrets in source

- **Anchor:** principle 13
- **Severity:** *must*
- **Fix:** stop. Use env / secret manager / the project's existing pattern. Flag the finding before committing.

### Logging tokens, passwords, request bodies, full headers

- **Anchor:** principle 13
- **Severity:** *must*
- **Fix:** log identifiers and shapes (`user_id`, `request_id`, `payload_size`); never raw secrets.

### Concatenating user input into SQL / shell / template

- **Anchor:** principle 13 (validate at trust boundaries)
- **Severity:** *must*
- **Fix:** parameterized queries / shell escaping / template auto-escaping. Never string-concat.

### Bearer token in a URL query string

- **Anchor:** principle 13
- **Severity:** *must*
- **Fix:** Authorization header. URLs end up in access logs, proxies, browser history.

### Authentication checked but not authorization (any logged-in user can mutate any record)

- **Anchor:** principle 13 (authorization is not authentication)
- **Severity:** *must*
- **Fix:** add `can_user_do_action_on_resource(user, action, resource)` at every mutation/sensitive-read handler.

### Hardcoded secrets in test fixtures

- **Anchor:** principle 13
- **Severity:** *must*
- **Fix:** use clearly-fake values that pattern-match as fake (`fake-token-do-not-use`); never recycle real-looking secrets.

---

## Performance and readability tension

### `@cache` / `@memoize` / `useMemo` added without a measured cause

- **Anchor:** mantras KISS + YAGNI
- **Severity:** *should*
- **Fix:** remove until profiling shows the call is hot. Memoization has overhead and wrong-dependency-array bugs.

### Microbenchmark-driven complexity in a non-hot path

- **Anchor:** mantras KISS + readability-first
- **Severity:** *should*
- **Fix:** revert to the readable version. Optimize what's measured, not what's imagined.

### `Object.freeze` / deep-clone everywhere as "defensive immutability"

- **Anchor:** mantra immutability by default — but *as a type-level discipline*, not a runtime tax
- **Severity:** *should*
- **Fix:** use `readonly` / `const` / `final` at the type level; freeze only at trust boundaries where mutation by callers is plausible.

---

## How smells compose

Some violations cluster: one root smell often produces several visible smells. Examples:

- **Mocking hell + many params + long function** → the subject violates SRP. Fixing SRP fixes all three.
- **Date.now() inline + sleep in tests + flaky CI** → no clock injection. Fixing principle 16 fixes the test flakes too.
- **Bag-of-optionals + isinstance checks + None-propagation chains** → modeling problem. A sum type collapses all three.

When you see multiple smells in one file, look for the root cause before fixing each surface.
