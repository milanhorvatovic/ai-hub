---
name: coding-principles-typescript
description: >
  TypeScript-specific capability of the coding-principles skill. Loaded
  when the task touches *.ts / *.tsx / *.mts files or sits in a
  tsconfig.json context. Covers the strict-mode floor, typing rules
  (unknown over any, discriminated unions, readonly), boundary validation
  with zod/valibot, error and async conventions, module/export idioms,
  React/JSX guidance, anti-patterns (enum, namespace, @ts-ignore), and
  before/after code examples anchored to numbered principles 2, 5, 16, 18,
  19, and 21 of the parent skill.
allowed-tools: Read Grep
---

# TypeScript capability

Language-specific rules layered on top of the parent `coding-principles` skill. Apply when editing `*.ts` / `*.tsx` / `*.mts` files.

> **Industry best practices** — modern toolchain consensus (pnpm, vitest, biome / eslint+prettier, msw, zod), ESM-first packaging, `@tsconfig/strictest` baseline, type-only imports, branded types pattern, schema-first APIs, built-in `fetch`, monorepo patterns, security (npm audit, prototype pollution, SSRF), and testing conventions including property-based testing with `fast-check` live in `references/best-practices.md` in this directory. Load it alongside this file when the task warrants justifying choices against industry standards.

## Floor

- `tsconfig.json` has `"strict": true`. Non-negotiable. If a project does not, fix that before anything else (with the user's approval).
- Also enable: `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noFallthroughCasesInSwitch` when the project is healthy enough to absorb them.
- `tsc --noEmit` as the typecheck. `eslint` (or `biome`) for lint. `prettier` (or `biome`) for format. Pick the toolchain the repo already uses; do not introduce a second one.
- Target ESM (`"type": "module"`) for new packages unless the project is CJS-locked.

## Types

- Prefer `unknown` over `any`. `any` opts out of typechecking entirely — use it as a last resort with a comment explaining why.
- Narrow with type predicates (`function isFoo(x: unknown): x is Foo`) or schema parsers (zod, valibot) at runtime boundaries.
- Discriminated unions over enums for state machines. `type Status = { kind: 'idle' } | { kind: 'loading' } | { kind: 'error'; message: string }`.
- `readonly` on properties that should not mutate. `ReadonlyArray<T>` / `readonly T[]` for params that should not be pushed to.
- `const` assertions (`as const`) for literal preservation in tuples and object shapes.

## Boundaries

- Every untyped input — HTTP request body, env vars, file reads, IPC messages — passes through a schema validator before reaching typed code. zod, valibot, or arktype; pick one and stick with it per project.
- `as` casts are allowed only:
  1. immediately after a runtime validation that narrows the type, or
  2. at a documented boundary with an invariant comment (`// safe: the upstream API guarantees this shape`).

## Errors

- Throw `Error` subclasses, not strings. Custom errors carry context: `class NotFoundError extends Error { constructor(public id: string) { super(\`not found: \${id}\`); } }`.
- Async functions either return `Promise<T>` and may reject, or use a Result type if the project has standardized on one. Do not mix paradigms in one module.
- Always `await` promises you create — unhandled rejections crash node and silently fail in browsers. Use `void` prefix only when explicitly fire-and-forget and the function is annotated `Promise<void>`.

## Modules and exports

- Named exports over default exports. Default exports break refactor tooling and inconsistent naming across the codebase.
- One concept per file. If `user.ts` exports a class, a parser, three constants, and an unrelated util — split.
- Avoid `index.ts` barrel files in app code (slower compile, harder for tree-shaking, circular import traps). Use them only for published library entry points.

## React / JSX (when applicable)

- Functional components with hooks. No class components in new code.
- `useMemo` / `useCallback` only with a measured cause — they have overhead and false dependency arrays are bugs.
- Inline object/array props re-render the child every render. Hoist or memoize when the child is expensive.
- `key` on list items must be stable and unique; never the array index when items can reorder.

## Anti-patterns

Language-specific anti-patterns live in `references/anti-patterns.md`. Load it for review-mode scans or pre-commit smell checks; the language-agnostic catalog is in `../../references/smells.md`.

## Verification

- `tsc --noEmit`
- `eslint .` (or `biome check .`)
- Run the affected unit tests; don't trust types alone for behavior.
- If the change touches a UI, exercise it in a browser; types don't catch layout regressions.

## Examples by principle

Concrete before/after code for high-leverage principles (2, 5, 16, 18, 19, 21) lives in `references/examples.md`. Load it when matching patterns at write-time or validating suggested fixes at review-time.

## Performance

Performance idioms (and the "measure first" discipline) live in `references/performance.md`. Load it when working on a hot path or large-data code — not for routine changes.

## Concurrency

Concurrency model, decision matrix, and correctness traps live in `references/concurrency.md`. Load it when the task involves parallelism, async, or shared state.

## Project structure

Language-specific structure mechanics (modularity unit, visibility/boundary enforcement, ports & adapters, dependency injection, layout) live in `references/project-structure.md`. It is the *how* for this language; `../../references/architecture.md` is the cross-language *why*. Load when structuring or restructuring a project.

## Dependencies

Dependency-management mechanics (version pinning, lockfiles, audit tools, update cadence, minimal footprint) live in `references/dependencies.md`. Default stance: **pin explicit exact versions** for applications/binaries (reproducibility); ranges only for published libraries. Load when adding, updating, or auditing dependencies.

## Cross-cutting references

Concern-specific, language-agnostic references live in `../../references/` — `api-design.md`, `persistence.md`, `observability.md`, `platform-matrix.md`, `resilience.md`, `data-handling.md`, `architecture.md`, `configuration.md`. Load the one matching the concern the code touches (see the table in the root `SKILL.md`). They apply across all language capabilities.
