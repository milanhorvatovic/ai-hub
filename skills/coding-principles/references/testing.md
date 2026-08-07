# Testing strategy — industry conventions

Language-agnostic testing _strategy_. The per-language _tactics_ (pytest/vitest/cargo-test, hypothesis/proptest, mocking libs) live in each language capability's best-practices and capability-entry docs; this file is the strategy layer above them. Load when deciding what to test, at what level, with what doubles.

Anchored to principle 2 (bug fixes need a failing-first test) and principle 15 (tests describe behavior, mock at boundaries) — this file is the strategy those rules operate within.

> **The named tools below were last checked 2026-08.** The strategy does not decay; the libraries implementing it do. How to read a stamped file is stated once under "Currency" in `../SKILL.md`.

## The test pyramid

Most tests cheap and fast, few tests slow and broad:

- **Unit** (most) — one unit in isolation; milliseconds; no I/O. The bulk of your tests.
- **Integration** (some) — a few units + a real boundary (DB, HTTP) wired together; slower.
- **End-to-end** (few) — the whole system through its real entry point; slowest, flakiest, most valuable for "does it actually work."

Inverted pyramids (mostly e2e) are slow and flaky; all-unit-no-integration misses wiring bugs. Aim for the shape, not a precise ratio.

## What to test / what not to test

- **Test logic that can be wrong** — branches, edge cases, error paths, calculations, state transitions.
- **Skip trivial code** (principle 15) — getters, simple delegation, type-only declarations, generated code, framework glue. A test that just restates the implementation tests nothing.
- **Test behavior at the boundary you control** — public functions, module APIs, HTTP handlers — not private internals (principle 15).
- **Test the contract, not the implementation** — a test that breaks on every refactor is testing the wrong thing.

## Test double taxonomy (Meszaros)

Precise vocabulary — these are not interchangeable:

| Double | What it does | Use when |
| --- | --- | --- |
| **Dummy** | Passed but never used (fills a parameter) | Satisfying a signature |
| **Stub** | Returns canned answers | Controlling indirect _input_ to the unit |
| **Spy** | A stub that records how it was called | Verifying a call happened, after the fact |
| **Mock** | Pre-programmed with expectations; fails if not met | Verifying interactions (use sparingly) |
| **Fake** | A working lightweight implementation (in-memory DB, fake clock) | Realistic behavior without the real dependency |

**Prefer fakes and stubs over mocks.** Mocks couple the test to the call sequence; an in-memory **fake** lets you assert on observable outcomes (state after) instead of interaction details. Mock at _boundaries_ (the HTTP client, the clock) — never internal collaborators (principle 15).

## Test data

- **Builders / factories** over inline literals — `aUser().withEmail("x").build()` keeps tests readable and resilient to schema changes. Libs: factory_boy (Python), fishery/test-data-bot (TS), fake/builder structs (Rust).
- **Object Mother** for a few canonical fixtures shared across tests.
- **Minimal data** — construct only the fields the test actually exercises; irrelevant data hides what matters.
- **No shared mutable fixtures** across tests — a test that depends on another test's leftover state is order-dependent and flaky.

## Determinism (the flaky-test killers)

Flaky tests come from a small set of causes — all fixable:

- **Time** → inject the clock (principle 16); never `sleep` in a test to "wait for" something.
- **Randomness** → inject the RNG / seed it (principle 16).
- **Order dependence** → isolate state; each test sets up and tears down its own world.
- **Shared mutable state** → no global/module state between tests (immutability + pure/impure mantras).
- **Real network / time-based waits** → fakes, deterministic clocks, polling with bounded retries instead of fixed sleeps.
- **Concurrency** → control scheduling in tests; don't assert on race-prone timing.

A flaky test is worse than no test — it trains the team to ignore red. Fix or delete it; never `@retry` it into green.

## Specialized strategies

- **Property-based testing** — generate inputs, assert invariants; the framework shrinks failures to minimal repros. For parsing, encoding, math, normalization. The per-language tool and its idioms live in the matching language capability's best-practices reference — `hypothesis` for python, `fast-check` for typescript, `proptest` for rust. Shell is the gap that stays a gap: no generator-and-shrinker library reached adoption there, so a script whose logic has properties worth generating against is a script whose logic belongs in a language that has one.
- **Contract testing** — for service ecosystems, consumer-driven contracts (Pact) verify the provider honors what consumers depend on, without full e2e. Prevents "we changed the API and broke three teams."
- **Snapshot / golden-file testing** — assert output matches a stored reference. Useful for serializers, generated code, complex structures. _Dangerous_ when over-used: a snapshot nobody reads becomes "approve the diff" rubber-stamping. Keep snapshots small and reviewed.
- **Mutation testing** — mutate the code, check tests catch it. Measures whether tests actually test (vs just execute) the code. Run periodically, not every CI (slow).
- **Fuzzing** — feed random/malformed input to find crashes and panics. For parsers, decoders, anything taking untrusted bytes (cargo-fuzz, atheris, jazzer).

## Coverage

- Coverage is a **signal, not a target.** High coverage of trivial code + zero coverage of the gnarly branch is worse than the number suggests.
- 100% coverage proves every line _ran_, not that behavior is _correct_ — mutation testing measures the latter.
- Use coverage to find _untested_ logic; don't game it with assertion-free tests.

## Principle alignment

- **Principle 2** — bug fixes: failing-first test, fix without changing the test, confirm green.
- **Principle 15** — behavior-named tests, mock at boundaries, one behavior per test, skip trivia.
- **Principle 16** — inject time/randomness so tests are deterministic.
- **Principle 10** — verification: tests are _part_ of "verify it works," not a substitute for exercising the feature.
- **Pure/impure separation** mantra — a pure core needs no doubles; if a unit needs five mocks, the design (not the test) is the problem.
