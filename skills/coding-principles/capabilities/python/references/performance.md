# Python — performance

Performance idioms for Python. Apply *after* correctness and clarity (KISS + readability outrank micro-optimization — measure first). These matter on hot paths and large data, not on code that runs occasionally.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Profile before optimizing

- `cProfile` + `snakeviz` for where time goes; `py-spy` for sampling a running process without instrumentation; `memray` / `tracemalloc` for memory.
- Optimize the measured hot spot, not the imagined one. The parent skill's "no premature optimization" is the default.

## Algorithmic first

- `set` / `dict` membership is O(1); `list` membership is O(n). A `in big_list` in a loop is a classic O(n²).
- Use the right container: `collections.deque` for queues, `heapq` for priority, `bisect` for sorted insertion.
- `collections.Counter`, `defaultdict` over hand-rolled counting.

## Hot-loop idioms

```python
# slow — repeated attribute lookup + global lookup per iteration
import math
def norm(points):
    out = []
    for p in points:
        out.append(math.sqrt(p.x**2 + p.y**2))
    return out
```

```python
# fast — bind the lookup once; comprehension avoids append overhead
from math import sqrt
def norm(points):
    return [sqrt(p.x**2 + p.y**2) for p in points]
```

- Bind frequently-used methods/functions to locals before a hot loop (`_sqrt = math.sqrt`).
- Comprehensions and generator expressions are faster than `for`+`append`.
- Avoid recomputing invariants inside loops.

## Memory

- **Generators** for large sequences you iterate once — `(f(x) for x in xs)` doesn't materialize the list.
- **`__slots__`** on classes you instantiate by the million — removes the per-instance `__dict__`, large memory win.
- **`array` / `numpy`** for large numeric data — a `list` of a million floats is far heavier than a `numpy` array.
- Stream large files (`for line in f`) instead of `f.read()`.

## Caching

- `functools.lru_cache` / `functools.cache` (3.9+) for pure functions with repeated inputs. Only when measured — caching has memory cost and only helps with repetition.
- `functools.cached_property` for expensive instance-level derived values (mind the single-source-of-truth principle).

## The GIL and CPU-bound work

- Threads do **not** speed up CPU-bound Python (the GIL serializes bytecode). Threads help I/O-bound work only.
- CPU-bound parallelism: `multiprocessing` / `concurrent.futures.ProcessPoolExecutor`, or push the hot kernel into `numpy` / a C extension / Cython / Rust (PyO3). See `concurrency.md`.
- The free-threaded build changes this (officially supported since 3.14, PEP 779), but it's a separate build — don't assume it unless the deployment explicitly runs it; standard CPython keeps the GIL.

## Don't reach for these reflexively

- Micro-optimizations (loop unrolling, exotic builtins) rarely beat a better algorithm or `numpy`.
- C extensions / Cython / Rust bindings are a real cost in build complexity — justify with a profile, not a hunch.
