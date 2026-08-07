# Rust — concurrency

Rust's type system makes data races a compile error: `Send` (safe to move across threads) and `Sync` (safe to share by reference across threads) are enforced by the borrow checker. "Fearless concurrency" means the compiler rejects the bugs other languages ship.

> **The crates named below were last checked 2026-08.** The concurrency model does not decay; the runtimes and libraries do — this file is where a discontinued runtime went unnoticed once. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## The decision matrix

| Workload | Use |
| --- | --- |
| CPU-bound, data parallel | `rayon` (`par_iter`) |
| I/O-bound, async | `tokio` (or `smol` when the dependency tree matters) |
| Message passing | channels (`std::sync::mpsc`, `crossbeam`, `tokio::sync::mpsc`) |
| Shared read | `Arc<T>` |
| Shared mutable (genuinely needed) | `Arc<Mutex<T>>` / `Arc<RwLock<T>>` |

## Data parallelism — rayon

The first reach for CPU-bound work over collections:

```rust
use rayon::prelude::*;
let sums: Vec<u64> = chunks.par_iter().map(expensive_compute).collect();
```

Near-zero code change from a sequential iterator; rayon handles the thread pool and work-stealing. Don't hand-roll a thread pool for data parallelism.

## Async — tokio

- **Pick one runtime.** Don't link two. `tokio` is the default.
- **`Send + 'static`**: a future passed to `tokio::spawn` must be `Send` and own its data. Holding a non-`Send` value (e.g. `Rc`, a `MutexGuard`) across `.await` produces hard-to-read errors — restructure so the non-`Send` value is dropped before the await.
- **Don't block the runtime** — no `std::thread::sleep`, no `std::fs` for big reads, no CPU-heavy loops in an async task. Use `tokio::time::sleep`, `tokio::fs`, or `tokio::task::spawn_blocking` for blocking/CPU work.
- **Cancellation safety**: a future can be dropped at any `.await`. A state machine holding a lock or mid-write data across an await point is a footgun — keep critical sections small and synchronous.
- **`tokio::select!`** to race futures; remember the un-selected branches are dropped (cancellation).

## Shared state

- **`Arc<T>`** for shared read-only data across threads.
- **`Arc<Mutex<T>>`** only when the data is genuinely shared _and_ mutable across threads (parent skill: reach for it only after the borrow checker says no). `RwLock` for read-heavy access.
- **Channels over shared state** when you can — message passing avoids whole classes of lock bugs. `crossbeam` channels for sync, `tokio::sync::mpsc` for async.
- **Hold locks briefly.** A lock held across an `.await` (async) or a long computation (sync) serializes everything waiting on it; in async it can deadlock if the awaited work needs the same lock.

## Atomics

- `std::sync::atomic` (`AtomicUsize`, `AtomicBool`) for simple shared counters/flags — cheaper than a `Mutex`.
- Memory ordering (`Relaxed` / `Acquire` / `Release` / `SeqCst`) matters; default to `SeqCst` unless you understand the weaker orderings.

## Why this is easier in Rust

The compiler enforces what other languages leave to discipline: you cannot share a non-`Sync` type across threads, cannot send a non-`Send` type, cannot mutate shared data without synchronization. A data race is a compile error, not a production incident. Lean on the type system — if it complains, the design has a real concurrency bug, not a false positive.
