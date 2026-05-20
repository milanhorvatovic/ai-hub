# Rust — performance

Performance idioms for Rust. Rust is already fast by default; these are the practices that keep it fast and the traps that quietly slow it down. Apply *after* correctness and clarity — measure before micro-optimizing.

## Measure before optimizing

- `cargo flamegraph` for CPU profiles; `perf` on Linux; `samply` cross-platform.
- `criterion` for statistically rigorous benchmarks (the stable replacement for unstable `#[bench]`).
- `cargo build --release` — never benchmark or profile a debug build; the difference is often 10-100×.

## Allocation discipline

The most common avoidable cost is unnecessary allocation.

```rust
// allocates a String per call even though the caller only reads it
fn label(id: u64) -> String { format!("id-{id}") }
```

```rust
// borrow when the caller doesn't need ownership; allocate only when required
fn write_label(out: &mut String, id: u64) { use std::fmt::Write; let _ = write!(out, "id-{id}"); }
```

- `&str` parameters over `String`; `&[T]` over `&Vec<T>` (see `../capability.md`).
- Avoid `.clone()` to dodge the borrow checker — usually the design needs adjustment, not a clone.
- `.collect::<Vec<_>>()` only when you need the materialized collection; otherwise keep the iterator lazy.
- Reuse buffers across iterations (`Vec::clear` + refill) instead of allocating a fresh one each loop.

## Iterators are zero-cost

- Iterator chains (`.iter().filter().map().sum()`) compile to the same code as a hand-written loop — use them for clarity without a performance penalty.
- They fuse: no intermediate collections are created between adapters unless you `.collect()`.
- `for x in &vec` (borrow) vs `for x in vec` (move) — pick based on whether you need ownership, not performance; both are optimal.

## Choosing pointer types

- `Box<T>` — single owner, heap allocation. Cheapest smart pointer.
- `Rc<T>` / `Arc<T>` — shared ownership; `Arc` is atomic (thread-safe) and slightly costlier. Don't reach for `Arc` in single-threaded code.
- `Cow<str>` — borrow when you can, own only when you must mutate. Good for "usually borrowed, occasionally modified" APIs.

## Parallelism

- **`rayon`** for data parallelism — `par_iter()` turns a sequential iterator parallel with near-zero code change. The first reach for CPU-bound work over large collections.
- Channels (`std::sync::mpsc`, `crossbeam`) for message passing; `Arc<Mutex<_>>` only when genuinely shared mutable state (see `../capability.md`).
- See `concurrency.md` for the full model.

## Const / compile-time

- `const` / `const fn` for values computable at compile time.
- Monomorphization makes generics zero-cost at runtime (at the price of compile time + binary size); `dyn Trait` trades a vtable indirection for smaller binaries — pick per call site.

## Don't reach for these reflexively

- `unsafe` for performance is almost never justified in application code; the safe version is usually as fast and the `unsafe` version is a future CVE (see `best-practices.md` security).
- SIMD intrinsics, custom allocators, `#[inline(always)]` — all real tools, all profile-driven. Don't apply speculatively.
- The compiler optimizes aggressively in release mode; trust it before hand-tuning.
