# TypeScript — project structure & mechanics

Language-specific *mechanics* for the architecture concepts in `../../../references/architecture.md` (dependency-points-inward, hexagonal, package-by-feature). That file is the *why*; this is the TypeScript *how*. Load when structuring or restructuring a TS project or monorepo.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Unit of modularity

- **Module** = a file (ESM). **Package** = a directory with its own `package.json` (in a monorepo workspace).
- Group by **feature/domain** (`orders/`, `billing/`), not by layer (`controllers/`, `services/`) — see the concept file. Layer *within* each feature.
- One concept per file; named exports (not default — see capability.md).

## Visibility / boundary enforcement

- **Module-level**: only `export` what's public; un-exported names are file-private. This is the primary boundary.
- **Package-level** (monorepo): the **`exports` field** in `package.json` defines the package's public surface — consumers can import only what `exports` maps. Internal files are unreachable from outside even if they're in the package (minimum public surface — modular-by-composition mantra).
- **Avoid barrel `index.ts`** that re-exports everything in app code — it defeats tree-shaking and creates circular-import traps (capability.md). Use `exports` maps for libraries instead.
- **Enforce dependency rules** in CI with `eslint-plugin-boundaries` or `dependency-cruiser` — e.g. "domain may not import infrastructure."

## Ports & adapters

- A **port** is an `interface` (or a `type` for a function port). Define it in the domain/application layer.
- An **adapter** is a class/object implementing the interface in the infrastructure layer.

```typescript
// application layer — the port it needs
export interface UserRepository {
  get(id: UserId): Promise<User | null>;
}

// infrastructure layer — adapter
export class PostgresUserRepository implements UserRepository {
  async get(id: UserId): Promise<User | null> { /* ... */ }
}
```

The domain imports the `UserRepository` interface, never the Postgres class.

## Dependency injection

- **Constructor injection** is idiomatic — `constructor(private repo: UserRepository)`.
- The composition root is the entry point (`main.ts`, the server bootstrap, the framework's app factory) — instantiate concrete adapters there (imperative shell — principle 16).
- DI *containers* (`tsyringe`, `InversifyJS`, NestJS's built-in) are common in larger apps but optional; manual wiring is clearer for small/medium apps (explicit-over-implicit mantra). Reach for a container only when manual wiring genuinely hurts.

## Layout

Single package:

```
project/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts              # public API surface
│   ├── orders/               # feature
│   │   ├── domain.ts         # entities + rules (pure)
│   │   ├── service.ts        # use cases; defines ports
│   │   └── repository.ts     # adapter
│   └── billing/
└── src/**/*.test.ts          # tests next to source (vitest convention)
```

Monorepo:

```
repo/
├── pnpm-workspace.yaml
├── tsconfig.base.json        # shared config; packages "extends" it
└── packages/
    ├── domain/               # no deps on infra
    ├── api/                  # depends on domain
    └── db/                   # adapter; depends on domain
```

- **`tsconfig.base.json`** shared via `"extends"`; **`exports`** controls each package's surface; **pnpm workspaces** as the base (turborepo/nx only when build orchestration hurts — best-practices.md).
- **Tests** next to source (`foo.test.ts`) is the vitest convention; a separate `tests/` tree also works — match the repo.

## When not to structure

A script, a Lambda handler, a small CLI — one file or a flat handful, no packages/ports/layers (principle 4 / when-NOT-to-layer in the concept file).
