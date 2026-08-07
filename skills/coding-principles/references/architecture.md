# Architecture & project structure — industry conventions

Language-agnostic guidance on how to organize code above the function/module level: layering, dependency direction, where things live. Load when starting a new component, restructuring a project, or deciding where a new piece of code belongs.

**Opinionated-topic caveat**: repo-local conventions win (principle 9). If the project already has a structure, match it — don't impose a different architecture mid-stream. This file is for greenfield decisions and for naming the patterns so reviewers can reference them.

**YAGNI caveat**: architecture is infrastructure (principle 4). A CLI script does not need hexagonal architecture; a 200-line service does not need a domain layer. Apply the _minimum_ structure the current scope needs. These patterns earn their keep in systems with real complexity and multiple integrations — not in everything.

## Layering and dependency direction

The one rule that matters most: **dependencies point inward, toward the domain.**

```
   ┌─────────────────────────────────────┐
   │  Infrastructure (DB, HTTP, queues)   │  ← depends on application
   │   ┌───────────────────────────────┐  │
   │   │  Application (use cases)       │  │  ← depends on domain
   │   │   ┌─────────────────────────┐  │  │
   │   │   │  Domain (entities,      │  │  │  ← depends on nothing
   │   │   │  business rules)        │  │  │
   │   │   └─────────────────────────┘  │  │
   │   └───────────────────────────────┘  │
   └─────────────────────────────────────┘
```

- **Domain** — pure business logic and entities. No imports of frameworks, DB drivers, HTTP libraries. This is the _functional core_ (pure/impure separation mantra) at architecture scale.
- **Application** — use cases / orchestration. Coordinates domain objects; defines _ports_ (interfaces) for what it needs from the outside (a `UserRepository` interface, not a Postgres class).
- **Infrastructure** — _adapters_ implementing the ports (the Postgres `UserRepository`, the HTTP controller, the queue consumer). This is the _imperative shell_.

The domain never imports infrastructure. Infrastructure depends on the domain, never the reverse. This is what makes the domain testable without a database and swappable without a rewrite (scalability mantra: add an adapter, don't rewrite the core).

## Named patterns (same idea, different vocab)

- **Hexagonal / Ports & Adapters** (Cockburn) — the domain exposes ports; adapters plug in. Same as above.
- **Clean Architecture** (Martin) — concentric circles, dependencies point inward. Same.
- **Onion Architecture** — same, different drawing.

Don't cargo-cult the full ceremony. The _load-bearing_ idea is "dependencies point toward the stable core, I/O at the edges." The folder names are negotiable.

## Package by feature vs package by layer

- **Package by layer**: `controllers/`, `services/`, `repositories/`, `models/`. Easy to start; scales poorly — one feature is smeared across four directories, and everything in `services/` can reach everything in `repositories/`.
- **Package by feature**: `users/`, `orders/`, `billing/` — each containing its own handler, logic, persistence. Higher cohesion (locality of behavior mantra), clearer boundaries, easier to extract into a service later.
- **Recommendation**: package by feature for anything non-trivial; layer _within_ each feature. A change to "orders" lives in `orders/`, not scattered.

## Module boundaries

- A module exposes the **smallest public surface** that satisfies its consumers (modular-by-composition mantra: boundary). Internal types stay internal.
- **No circular dependencies between modules.** A cycle means the boundary is wrong — merge them or extract the shared piece.
- **Stable things don't depend on volatile things.** The domain (stable) doesn't depend on the HTTP framework (volatile, replaceable).

## Where things go

| Thing | Conventional location |
| --- | --- |
| Source | `src/` (Python src-layout, Rust `src/`, TS `src/`) |
| Unit tests | next to source or mirrored `tests/` tree — match the language (Rust: in-file `#[cfg(test)]`; Python/TS: either) |
| Integration tests | separate `tests/` directory |
| Public API entry | one obvious entry point (`__init__.py`, `index.ts`, `lib.rs`, `main`) |
| Config | loaded at the edge, not scattered (see `configuration.md`) |
| Generated code | clearly marked, separate dir, never hand-edited |

## When NOT to layer

- One-off scripts, CLIs, lambdas, glue code — a single file with a few functions is correct. Imposing domain/application/infrastructure on a 100-line tool is over-engineering (principle 4).
- Prototypes / spikes — structure emerges as the thing proves out; don't pre-build the cathedral.
- The signal to _add_ structure is pain: the file is too big to navigate, tests need the whole world, a change touches five unrelated places. Refactor toward structure when you feel that — not before (scalability mantra: shape is earned by the current need).

## Language-specific mechanics

This file is the _concept_ layer — the patterns above (dependency direction, hexagonal, package-by-feature) are language-agnostic. The _mechanics_ of expressing them — the unit of modularity, how visibility/boundaries are enforced, how ports/adapters and dependency injection are written, where tests live — differ per language and live in each capability.

Load the matching language capability's project-structure reference for the concrete how; this file for the why.

## Principle alignment

- **Pure/impure separation** mantra is hexagonal architecture at function scale; hexagonal is the same idea at module scale.
- **Modular by composition** mantra (boundary): minimum public surface per module.
- **Scalability** mantra: layering lets you _add_ an adapter (new DB, new transport) without _rewriting_ the core.
- **YAGNI** (principle 4) + **locality of behavior** mantra: don't pre-impose layers; package by feature so related code stays together until a real boundary emerges.
