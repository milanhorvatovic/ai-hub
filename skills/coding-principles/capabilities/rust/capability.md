---
name: coding-principles-rust
description: >
  Rust-specific capability of the coding-principles skill. Loaded when the
  task touches *.rs files or sits in a Cargo.toml context. Covers the
  tooling floor (cargo fmt + clippy -D warnings, MSRV respect), error
  conventions (Result/Option, thiserror for libs vs anyhow for bins),
  ownership and borrowing idioms, unsafe-block SAFETY comments, async
  runtime discipline, Cargo features (additive only), and anti-patterns
  (unwrap in libs, Box<dyn Error>, derive overdose).
allowed-tools: Read Grep
---

# Rust capability

Language-specific rules layered on top of the parent `coding-principles` skill. Apply when editing `*.rs` files.

> **Industry best practices** — Rust API Guidelines reference, edition discipline + MSRV, modern toolchain consensus (cargo fmt/clippy/nextest/machete, cargo-audit, cargo-deny), error-library decision tree (thiserror / anyhow / snafu), `tracing` over `log`, idiomatic patterns (newtype, builder, typestate, sealed traits), async Send+Sync discipline, supply-chain hygiene, and documentation conventions live in `references/best-practices.md` in this directory. Load it alongside this file when the task warrants justifying choices against industry standards.

## Floor

- `cargo fmt` and `cargo clippy -- -D warnings` are the floor. CI should fail on either.
- Edition: prefer the latest the project has adopted (2021 / 2024). Don't mix.
- MSRV (minimum supported Rust version): respect what `Cargo.toml` declares; don't introduce features that raise it without the user's approval.

## Errors

- `Result<T, E>` for fallible operations; `Option<T>` for "absent" values. No sentinel return values.
- `?` for propagation. Bare `.unwrap()` / `.expect()` is allowed only:
  - in tests,
  - in `main()` of small binaries where panic-on-error is the intended UX,
  - when a proven invariant makes the variant unreachable — with a comment stating the invariant.
- Library crates: define a specific error enum with `thiserror`. Do not return `Box<dyn Error>` from library code — callers lose match-ability.
- Application/binary crates: `anyhow::Result` and `?` are fine. Don't mix `anyhow` into a library.

## Ownership and borrowing

- Prefer `&str` for string parameters, `String` for owned returns or struct fields. Don't take `&String` — it's strictly worse.
- Prefer `&[T]` over `&Vec<T>` for slice parameters. Same reason.
- `Clone` is fine when the cost is small (small structs, refcounts, `Arc`) and clarifies ownership. Don't `clone()` to dodge borrow-check errors without understanding why — usually the design needs adjustment.
- Reach for `Arc<Mutex<_>>` only after borrow-check has told you no and the data genuinely is shared mutable state across threads. Most cases want `Arc<T>` (shared read), channels (transfer), or `RwLock` (read-heavy).

## Unsafe

- Every `unsafe` block needs a `// SAFETY:` comment stating the invariants the caller is relying on. No exceptions.
- Encapsulate `unsafe` behind a safe API; don't sprinkle it through call sites.
- If you're writing `unsafe` in application code (not FFI, not a low-level library), the design is probably wrong.

## Idioms

- Iterators over manual loops when clearer. `.collect::<Vec<_>>()` only when you need the allocation.
- `match` over chained `if let` when handling multiple variants.
- `?` on `Option` works in functions returning `Option`. Same for `Result`. Don't mix without `.ok_or(...)?`.
- Use newtypes (`struct UserId(u64);`) instead of passing raw ints when the type carries meaning.
- Implement `Display` for user-facing strings, `Debug` derives for everything else.

## Async

- Pick a runtime (`tokio` is the default; `smol` is the lean alternative — `async-std` is discontinued, so migrate off it rather than onto it). Don't link two runtimes.
- Don't block in async code — no `std::thread::sleep`, no `std::fs` for big reads. Use the runtime's async equivalents or `spawn_blocking`.
- `.await` cancellation is real: a future may be dropped mid-execution. State machines holding locks across await points are landmines.

## Cargo and features

- Features are additive. Enabling a feature must not change behavior in a way that breaks downstream code.
- Default features should be the common case. Crates intended for `no_std` use should have `std` as a default feature, opt-out.
- Workspaces: pin dependency versions in the workspace root; member crates inherit per-dependency with `serde = { workspace = true }` (and `[package]` fields with `version.workspace = true`).

## Anti-patterns

Language-specific anti-patterns live in `references/anti-patterns.md`. Load it for review-mode scans or pre-commit smell checks; the language-agnostic catalog is in `../../references/smells.md`.

## Tests

- Unit tests in the same file (`#[cfg(test)] mod tests`); integration tests in `tests/`.
- `assert_eq!` / `assert_ne!` over plain `assert!` — better failure messages.
- `proptest` or `quickcheck` for properties when the input space is large.
- `cargo test --doc` — doc tests are real tests; keep them passing.

## Verification

- `cargo fmt --check`
- `cargo clippy --all-targets -- -D warnings`
- `cargo test`
- `cargo check` is not enough — `clippy` catches things `check` doesn't.

## Examples by principle

Concrete before/after code for high-leverage principles 2, 5, 15, 16, 19, 21 and the "Make illegal states unrepresentable" mantra lives in `references/examples.md`. Load it when matching patterns at write-time or validating suggested fixes at review-time.

## Performance

Performance idioms (and the "measure first" discipline) live in `references/performance.md`. Load it when working on a hot path or large-data code — not for routine changes.

## Concurrency

Concurrency model, decision matrix, and correctness traps live in `references/concurrency.md`. Load it when the task involves parallelism, async, or shared state.

## Project structure

Language-specific structure mechanics (modularity unit, visibility/boundary enforcement, ports & adapters, dependency injection, layout) live in `references/project-structure.md`. It is the _how_ for this language; `../../references/architecture.md` is the cross-language _why_. Load when structuring or restructuring a project.

## Dependencies

Dependency-management mechanics (version pinning, lockfiles, audit tools, update cadence, minimal footprint) live in `references/dependencies.md`. Default stance: **pin explicit exact versions** for applications/binaries (reproducibility); ranges only for published libraries. Load when adding, updating, or auditing dependencies.

## Cross-cutting references

Concern-specific, language-agnostic references live in `../../references/` — `api-design.md`, `persistence.md`, `observability.md`, `platform-matrix.md`, `resilience.md`, `data-handling.md`, `architecture.md`, `configuration.md`. Load the one matching the concern the code touches (see the table in the root `SKILL.md`). They apply across all language capabilities.
