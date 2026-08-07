# TypeScript / JavaScript — performance

Performance idioms for TS/JS (Node and browser). Apply *after* correctness and clarity (KISS + readability outrank micro-optimization — measure first). These matter on hot paths, large data, and bundle-size-sensitive frontends.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Measure before optimizing

- Node: `node --prof` + `--prof-process`, `clinic.js`, or `0x` for flamegraphs.
- Browser: Chrome DevTools Performance panel; Lighthouse for page-load metrics.
- React: the Profiler in React DevTools for render cost.
- Optimize the measured hot spot. "No premature optimization" is the default.

## Algorithmic / data structures

- `Map` over a plain object for dynamic-key dictionaries — better for frequent add/delete, any-typed keys, and iteration order guarantees.
- `Set` for membership and dedup; `array.includes` in a loop is O(n²).
- Avoid repeatedly spreading arrays/objects in loops — `[...acc, x]` per iteration is O(n²); push to an array or use a single spread at the end.

```typescript
// slow — O(n²): new array each iteration
const result = items.reduce((acc, x) => [...acc, transform(x)], [] as T[]);
```

```typescript
// fast — O(n): mutate a local, or just map
const result = items.map(transform);
```

## Async performance

- **Parallelize independent awaits**: `await Promise.all([a(), b()])`, not sequential `await a(); await b()`.
- **Don't `await` in a loop** when the iterations are independent — collect promises and `Promise.all`. Use `Promise.allSettled` when partial failure is acceptable; bound concurrency (e.g. `p-limit`) when the work is large.
- **Stream large responses** rather than buffering the whole body.

## Memory

- Avoid accidental retention: closures capturing large objects, listeners not removed, growing module-level caches.
- For large numeric data, typed arrays (`Float64Array`, `Uint8Array`) over `number[]`.
- Streams (`node:stream/web`) over reading whole files/responses into memory.

## Frontend / bundle size

- **Bundle size is a performance budget.** Measure with `source-map-explorer` / the bundler's analyzer.
- **Code-split** by route; lazy-load heavy components (`React.lazy`, dynamic `import()`).
- **Tree-shaking** requires ESM and side-effect-free modules (`"sideEffects": false` in `package.json` when true).
- Prefer small focused dependencies; a date library should not be 70KB. Check before adding.
- **Avoid re-renders** (React): stable props, `useMemo`/`useCallback` *only when measured* (they have cost — see `../capability.md` React notes), `key` stability.

## V8 / engine notes

- Monomorphic code (consistent object shapes) is faster than polymorphic — don't add/remove properties to make objects different "hidden classes" in a hot path.
- Don't micro-tune for V8 internals speculatively; a better algorithm and smaller bundle beat hidden-class tricks almost always.

## Don't reach for these reflexively

- Manual loop optimization rarely beats `map`/`filter`/`reduce` clarity unless profiled.
- Web Workers / worker threads add real complexity — justify with a profile (see `concurrency.md`).
