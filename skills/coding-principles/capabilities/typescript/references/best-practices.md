# TypeScript — industry best practices

Modern toolchain consensus, idiomatic patterns the community has converged on, security and operational conventions. Complements the principle-anchored content in `../capability.md`.

> **Toolchain claims here were last checked 2026-08.** How to read a stamped file, and what the stamp does not cover, is stated once under "Currency" in `../../../SKILL.md`.

## External standards

- **[TC39](https://tc39.es/)** — JavaScript language spec; TypeScript tracks it. Use proposals only when they reach Stage 4 unless the project already opts in to earlier stages.
- **[`@tsconfig/strictest`](https://github.com/tsconfig/bases)** — known-good baseline for new projects. `@tsconfig/node24`, `@tsconfig/recommended` are domain-specific extensions.
- **[Effect-TS docs](https://effect.website/)** — if the project uses Effect, its docs are the canonical reference; this capability doesn't reproduce them.

## Toolchain consensus

- **Runtime**: a current LTS line, whichever that is when you read this — at the stamp, Node 24 (active LTS) or 22 (maintenance, until 2027-04); Node 26 is Current and enters LTS 2026-10. Anything past its EOL date needs a stated reason (Node 20 went EOL 2026-04). Bun is acceptable for greenfield CLIs / scripts; Deno for security-sensitive contexts. One scheduling change worth knowing because it invalidates the old mental model: from Node 27 (2026-10) there is one major release a year and every line is LTS, so "even-numbered releases are the LTS ones" stops being a rule you can reason from.
- **Package manager**: `pnpm` — fast, strict (no phantom dependencies), monorepo-native via workspaces. `npm` acceptable; `yarn` declining; `bun install` viable for Bun projects.
- **TypeScript**: `typescript@latest` with `"strict": true`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`. Use `tsc --noEmit` for type-checking; pair with a separate bundler for emit (esbuild, swc, rollup, vite, or tsup).
- **Lint + format**: `biome` (Rust-based, fast, single tool) OR `eslint` + `prettier`. Don't run both. Most new projects pick `biome`.
- **Test runner**: `vitest` for new projects (Vite-aligned, ESM-native, jest-compatible API); `jest` for legacy projects.
- **HTTP mocking**: `msw` (Mock Service Worker) — intercepts at the network layer, works in Node tests and browser tests with the same handlers.
- **Validation**: `zod` (most common), `valibot` (smaller bundle), `arktype` (parser-based). Pick one per project.
- **Property testing**: `fast-check` — the ecosystem's equivalent of hypothesis/proptest, with first-class vitest and jest integration.

## ESM-first for new packages

`"type": "module"` in `package.json`; `.mjs` / explicit extensions in imports (`import x from "./x.js"` even when the file is `.ts`). CommonJS is supported but every new package should publish ESM.

## Type-only imports

```typescript
import type { User } from "./types";   // erased at compile time
import { createUser } from "./users";  // runtime import
```

Catches accidental "I only used this as a type, why is it in the bundle?" cases, and prevents circular-import surprises.

## Branded types for IDs

```typescript
type UserId = string & { readonly __brand: "UserId" };
type OrderId = string & { readonly __brand: "OrderId" };

declare const userId: UserId;
declare const orderId: OrderId;
function getUser(id: UserId): User;
getUser(orderId);  // type error — exactly what we want
```

`number` and `string` are far too permissive for IDs. Branded types catch "passed an OrderId where a UserId was expected" at compile time without changing runtime representation.

Same pattern works for: `Email`, `URL`, `ValidatedUserInput`, `EncodedHtml`, `Cents` (vs `Dollars`).

## Schema-first APIs

```typescript
import { z } from "zod";   // zod 4

const UserSchema = z.object({
  id: z.uuid(),
  email: z.email(),
  createdAt: z.coerce.date(),
});

type User = z.infer<typeof UserSchema>;   // source of truth: the schema
```

Do not maintain a separate `interface User` alongside the schema. Inference from the schema *is* the type. Drift is impossible because the type is *derived*. (zod 4 moved the string-format validators to the top level — `z.uuid()`, `z.email()`; the chained `z.string().uuid()` spelling is the deprecated v3 idiom.)

## Built-in fetch

Every supported Node line ships `fetch` natively. Don't add `axios` to a new project unless you need interceptors or progress events. For HTTP retries / timeouts / instrumentation, layer those onto `fetch` directly or use `ky` (a thin wrapper) — not axios's full surface.

## Node-specific recommendations

- **Use `node:` prefix** for stdlib imports: `import { readFile } from "node:fs/promises"`. Prevents shadowing by a same-named npm package.
- **`AbortController`** for cancellation; pair with `fetch` / `setTimeout`.
- **`undici`** is the underlying HTTP client; use it directly when you need pooling control.
- **Streams**: prefer `node:stream/web` (Web Streams) over `node:stream` (Node legacy streams) for new code.

## Monorepo patterns

- **pnpm workspaces** as the base. `turborepo` / `nx` only when build-graph orchestration becomes painful (10+ packages, long CI).
- **Shared `tsconfig.base.json`** referenced via `"extends"` in each package's `tsconfig.json`.
- **`exports` field** in each package's `package.json` to control public surface (modular-by-composition: minimum public surface).

## Security

- **Don't `eval` / `new Function` / `setTimeout(string)`**.
- **`JSON.parse(reviver?)`** is safe; `eval(`(${json})`)` is not.
- **XSS**: render user content through a templating engine that auto-escapes (React, Vue, Lit — all do by default). Manual `innerHTML` requires `DOMPurify` for sanitization.
- **SSRF**: validate URLs before fetching server-side; block `localhost`, `127.0.0.1`, `169.254.169.254` (cloud metadata), private CIDRs.
- **Prototype pollution**: don't merge untrusted JSON into existing objects without `Object.create(null)` or schema validation.
- **Supply chain**: `pnpm audit` / `npm audit` in CI; pin via lockfile; review `package.json` `dependencies` regularly; consider `npm-check-updates` quarterly.
- **`package.json` `overrides`** to force-pin a transitive dep with a CVE without waiting for the upstream patch.

## Testing

- **`vitest`** (or `jest`) with files alongside source: `src/foo.ts` + `src/foo.test.ts`.
- **`@testing-library/react`** (or framework equivalent) for UI tests — tests behavior, not internals.
- **`msw`** for HTTP mocking — same handlers in Node tests and browser tests; mocks the network, not the client library.
- **`playwright`** for E2E. `cypress` works; the community has largely shifted to playwright for speed + multi-browser.
- **Coverage** via vitest's own provider (`@vitest/coverage-v8`, or `@vitest/coverage-istanbul` when you need istanbul's instrumentation); `c8` / `nyc` standalone for non-vitest runners. Don't chase 100%; chase coverage of the logic that matters.

## Property-based testing

Use `fast-check` for any function that takes structured input and has algebraic properties (parsing, normalization, encoding, math). It generates inputs you wouldn't think to write tests for and *shrinks* failures to a minimal counterexample.

```typescript
import { test } from "vitest";
import fc from "fast-check";

test("sorting is idempotent", () => {
  fc.assert(
    fc.property(fc.array(fc.integer()), (xs) => {
      const once = [...xs].sort((a, b) => a - b);
      const twice = [...once].sort((a, b) => a - b);
      expect(twice).toEqual(once);
    }),
  );
});
```

Runs are seeded and the seed is printed on failure, so a counterexample reproduces exactly; pin it with `fc.assert(..., { seed })` when adding the regression test.

## React-specific (when applicable)

- **Functional components + hooks** only in new code.
- **Server components** when the framework supports them (Next.js App Router, React Router 7 — which absorbed Remix) — they remove the boundary between fetch and render.
- **`use client` directive** at the top of files that need browser APIs / state — keep client boundary thin.
- **`useMemo` / `useCallback`** only with a measured cause. They have cost; wrong dependency arrays are bugs.
- **`key` on lists** must be stable + unique. Array index breaks under reorder.
- **`Suspense` + error boundaries** at meaningful UI boundaries, not at the leaf.

## Documentation

- **TSDoc** (`/** ... */` with `@param`, `@returns`, `@throws`, `@example`) is the standard for documenting exported API. Editors surface it on hover. Whether a given export needs one is the comments capability's docstring policy — a `typedoc.json` or an `eslint-plugin-tsdoc` rule settles it; absent both, the value bar does.
- **Types are documentation** — a precise type replaces prose, so a doc comment that restates the signature costs maintenance and adds nothing.
- **`typedoc`** generates an API site from TSDoc comments. Generate from source; don't hand-maintain.
- **README per package** in a monorepo — what the package is, how to install, a minimal example. Keep it to getting-started; deep reference lives in generated docs.
