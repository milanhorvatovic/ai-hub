# Python — concurrency

Python's concurrency story is shaped by the GIL. Picking the right model is the most consequential decision; getting it wrong means code that's concurrent on paper but serial in practice.

## The decision matrix

| Workload                              | Use                                            | Why                                                            |
| ------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------- |
| I/O-bound, many connections           | `asyncio`                                      | One thread, cooperative; scales to thousands of sockets       |
| I/O-bound, blocking libraries         | `threading` / `ThreadPoolExecutor`            | GIL releases during I/O; threads overlap the waits            |
| CPU-bound                             | `multiprocessing` / `ProcessPoolExecutor`     | Separate processes sidestep the GIL; true parallelism         |
| CPU-bound, numeric                    | `numpy` / native extension                     | The hot kernel runs outside the GIL in C                      |

The trap: **threads do not speed up CPU-bound Python** — the GIL serializes bytecode execution. Threads help only when the work *waits* (network, disk, subprocess).

## asyncio (I/O concurrency)

- `async def` only where there's real I/O concurrency to exploit (parent skill: don't async-ify CPU code).
- **`asyncio.TaskGroup`** (3.11+) for structured fan-out — propagates cancellation when one task fails. Prefer over bare `gather`.
- **`asyncio.timeout`** (3.11+) for deadlines.
- **Never block the event loop** — no `time.sleep`, no synchronous `requests`, no big synchronous file reads. Use `asyncio.sleep`, `httpx`/`aiohttp`, `aiofiles`, or offload blocking calls with `asyncio.to_thread`.
- Don't mix sync and async in one layer without a clear boundary.

## threading (I/O with blocking libs)

- `concurrent.futures.ThreadPoolExecutor` for "run these blocking I/O calls concurrently."
- Shared mutable state needs a `threading.Lock` / `queue.Queue`. Prefer message-passing (`queue.Queue`) over shared-state-plus-locks.
- The GIL makes *some* operations atomic, but don't rely on it — `+=` on a shared int is not atomic.

## multiprocessing (CPU parallelism)

- `ProcessPoolExecutor` for CPU-bound fan-out.
- Data crosses process boundaries by pickling — large payloads are expensive to ship; pass references (file paths, DB keys) not big objects.
- Processes don't share memory; use `multiprocessing.Queue` / shared memory (`multiprocessing.shared_memory`) deliberately.
- Watch the fork-vs-spawn start method — `spawn` (default on macOS/Windows) re-imports the module; guard entry points with `if __name__ == "__main__":`.

## Determinism and testing

- Inject the clock and any shared resources (principle 16) so concurrent code is testable.
- Concurrency bugs are timing-dependent — make critical sections small, prefer immutable data (immutability mantra) and message-passing over shared mutable state.

## The free-threaded build

Python's free-threaded (no-GIL) build is officially supported since 3.14 (PEP 779; 3.13 shipped it as experimental). It changes the CPU-bound calculus, but it's a separate build — don't assume it in code that must run on standard CPython, which keeps the GIL.
