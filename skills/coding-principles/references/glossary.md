# Glossary

Terms used consistently across the parent skill, references, and capabilities. Definitions here are authoritative; if a term in any other file appears to mean something else, that's a bug — flag it.

## Boundary / Trust line

The point where data or control crosses from *untrusted* / *external* into *trusted* / *internal*. Examples: HTTP request entry, file read, IPC message, deserialization, environment variable read, CLI argv. The matching outbound boundary is where typed internal values become bytes again — HTTP response, log record, persisted row, IPC send.

The skill's stance: **validate inbound, serialize outbound, trust everything in between** (see principles 5 and 19).

## Shape

The structural form of code — how it is split into functions, modules, and types; how data flows; where side effects live. Independent of file count or line count. A 200-line monolith with one decision tree has *worse shape* than the same logic split into a parser, a validator, and a writer (each pure) even if the latter occupies more lines.

The skill distinguishes shape (the design) from **infrastructure** (the wiring).

## Infrastructure (in the YAGNI sense)

The plumbing that holds an abstraction together — interfaces with one implementation, plugin systems, strategy classes, factories, DI containers, configuration layers, abstract base classes used for code reuse. Infrastructure is what *makes* an abstraction polymorphic or pluggable; shape is what makes code *small and composable*.

YAGNI prunes infrastructure, not shape (see principle 4 and mantra "modular by composition").

## Pure function

A function whose output depends only on its inputs and which produces no observable side effects: no I/O, no mutation of arguments or globals, no calls to `Date.now()` / `random()` / file or network access, no logging at the function's level. Calling it twice with the same arguments returns the same result.

Pure functions are the *functional core* in the functional-core-imperative-shell pattern (mantra: pure/impure separation).

## Functional core, imperative shell

A design where pure computation sits in the center of the system and all impure operations (I/O, mutation, time, randomness) live at the edges in a thin shell. The shell reads input → calls the pure core → writes output. The shell is where `main()`, request handlers, CLI entrypoints, and adapter classes live; everything else is pure.

Makes testing free (pure cores need no mocks), refactoring safe, and concurrency tractable.

## Escape hatch

A type construct that opts out of static checking: `any` / `unknown`-without-narrowing in TypeScript, `Any` in Python, `Object` in Java, `dynamic` in C#, `void*` in C/C++, `interface{}` in Go (pre-1.18), `serde_json::Value` carried past the boundary in Rust. Acceptable at trust boundaries before parsing; never the default for internal code (mantra: strong typing).

## Bag of optionals

An object or struct type that uses many optional fields to encode mutually-exclusive states: `{loading?: bool, data?: T, error?: Error}`. The type permits incoherent combinations like `{loading: true, data: X, error: Y}` which the design says cannot happen. Fix: replace with a sum type / discriminated union (mantra: make illegal states unrepresentable).

## Earned shape vs speculative generality

- **Earned shape**: design choices that benefit the *current* feature — small pure functions, narrow interfaces, separated I/O, orthogonal modules. Free to apply at write-time.
- **Speculative generality**: design choices that benefit *imagined future* features — interfaces with one implementation, plugin points for nonexistent plugins, configuration flags with no current caller, abstract base classes anticipating subclasses. Costs surface area and indirection; defer until a second concrete caller exists.

See principle 4 for the line between them.

## Half-implementation

A function or feature that ships some of its declared behavior and stubs the rest — A and B work, C raises `NotImplementedError`, returns null, or quietly does nothing. Looks done; type-checks; passes lint; silently misbehaves at runtime.

Ship all of A/B/C or none (principle 8). The exception is an *explicitly approved* incremental rollout with tracked follow-ups.

## Decay suffix

Naming patterns that mark code as transitional and then never get cleaned up: `_old`, `_new`, `_v2`, `_temp`, `_tmp`, `Old`, `New`, `Legacy`. The replacement should have a clear name describing what it *does*; the original should be deleted when the migration completes. Leaving both is rot bait (principle 17).

## Derived state vs stored state

- **Derived state**: a value computed from other values (`total = sum(items)`, `is_complete = status == "done"`). Should be computed on read, not stored.
- **Stored state**: a value that is the *source of truth* — not reconstructible from anything else. The smallest possible set of stored values yields the most maintainable system.

When stored state and derived state both exist for the same value, you have a cache-invalidation problem. See principle 18.

## Severity (must / should / could)

Per-principle violation tags:

- **must** — non-negotiable. Treat a violation as a bug; fix before shipping.
- **should** — strong default. Deviation needs a stated reason.
- **could** — preference. Deviation is fine when surrounding code differs; apply silently when you can.

Severity governs *triage*. Tier (Goals / Design / Pruning, in `references/mantras.md`) governs *design conflicts*. They answer different questions.

## Write-mode vs review-mode

- **Write-mode** — the default; applying the skill while authoring code. Checklist asks *"am I about to violate X?"*. Defined inline in `SKILL.md`.
- **Review-mode** — applying the skill to an existing diff/PR. Workflow asks *"did the author violate X?"*. Defined in `../capabilities/review/capability.md`.

Same rules; opposite vantage.
