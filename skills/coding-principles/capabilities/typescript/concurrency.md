# TypeScript / JavaScript — concurrency

JS is single-threaded with an event loop. "Concurrency" is cooperative (async I/O on one thread); "parallelism" requires workers (separate threads/processes with no shared memory by default).

## The model

- **One thread, one event loop.** Async code interleaves at `await` points; it does not run in parallel. CPU-bound work blocks the loop and freezes everything (the server stops responding; the UI stops painting).
- **I/O is where concurrency lives** — network, disk, timers run off-thread and resume your code via callbacks/promises.

## Async concurrency (I/O)

- **Parallelize independent awaits**: `await Promise.all([a(), b()])` over sequential `await a(); await b()`.
- **Don't `await` in a loop** for independent iterations — collect promises, then `Promise.all`. Use `Promise.allSettled` when partial failure is acceptable.
- **Bound concurrency** for large fan-out — `Promise.all` over 10,000 items opens 10,000 connections. Use `p-limit` / a semaphore to cap in-flight work.
- **`AbortController`** for cancellation; pass `signal` to `fetch` and cancellable operations.
- **Always set timeouts** on network calls (parent skill: no un-timed calls in a request path).

## Race conditions still exist

Single-threaded doesn't mean race-free. Interleaving at `await` points causes logical races:

```typescript
// race — two concurrent calls both read, both write; one update is lost
async function increment(id: string) {
  const n = await store.get(id);   // both read 5
  await store.set(id, n + 1);      // both write 6; should be 7
}
```

Fix with atomic operations at the store (DB `UPDATE ... SET n = n + 1`, optimistic locking) — not with application-level locks, which don't compose across instances.

## Parallelism (CPU-bound)

- **Node**: `worker_threads` for CPU-bound work. Workers don't share memory (except `SharedArrayBuffer`); communicate via `postMessage` (structured clone) — large payloads are copy-expensive.
- **Browser**: Web Workers, same model. Keep heavy compute (parsing, image processing, crypto) off the main thread so the UI stays responsive.
- **`child_process`** for shelling out / process-level parallelism.
- Worker pools (`piscina` for Node) for repeated CPU tasks rather than spawning per task.

## When to reach for workers

Only when a profile shows the main thread is CPU-bound (see `performance.md`). Workers add real complexity (serialization boundaries, lifecycle management) — the parent skill's YAGNI applies. Most Node services are I/O-bound and never need them.
