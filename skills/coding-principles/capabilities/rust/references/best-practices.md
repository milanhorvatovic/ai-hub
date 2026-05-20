# Rust — industry best practices

External standards, modern toolchain consensus, idiomatic patterns, error/async/supply-chain conventions. Complements the principle-anchored content in `../capability.md`.

## External standards

- **[Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)** — the canonical external standard for public APIs. Naming, predictability, flexibility, type safety, dependability, debuggability, future-proofing, necessities — each section has concrete checklists. Cite these when designing a public crate API.
- **[The Rust Book](https://doc.rust-lang.org/book/)** + **[Rust by Example](https://doc.rust-lang.org/rust-by-example/)** — pedagogical canon; useful references when explaining choices.
- **[Rust RFCs](https://github.com/rust-lang/rfcs)** — the language design history; cite when explaining why a feature exists as it does.

## Edition

- **2024** is current; **2021** still common. Don't mix editions within a crate. Workspace members can have different editions but it's friction — pick one for new projects.
- **MSRV** (Minimum Supported Rust Version) declared in `Cargo.toml`:
  ```toml
  [package]
  rust-version = "1.75"
  ```
  Enforce in CI with a matrix that runs against MSRV + `stable` + `nightly`. Bumping MSRV is a semver-relevant change for libraries.

## Toolchain consensus

- **`rustup`** with the stable channel; `cargo` for everything (build, test, doc, publish).
- **`cargo fmt`** — non-negotiable. CI must fail on `cargo fmt --check`.
- **`cargo clippy -- -D warnings`** — CI floor. Treat clippy warnings as errors. Specific lints can be allowed per-call-site with a comment explaining why.
- **`cargo test`** — runs unit + integration + doc tests.
- **`cargo doc`** — generate API docs. Add `#![warn(missing_docs)]` for libraries; treat missing-doc warnings as a soft failure in CI.
- **`cargo nextest`** — faster test runner with better output; drop-in for `cargo test`.
- **`cargo machete`** — find unused dependencies. Run periodically.
- **`cargo expand`** — expand macros to see generated code; useful when debugging derive issues.

## Error handling decision tree

Pick *one* error strategy per crate; do not mix.

| Crate type      | Strategy                                        | Why                                                                |
| --------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| Library         | `thiserror` + named error enum                  | Callers can match on variants; types document the failure modes    |
| Application/bin | `anyhow::Result<T>` + `?` everywhere            | Ergonomic propagation; opaque is fine because the user is the end  |
| Heavy context   | `snafu` or hand-rolled                          | When errors need rich location/context that thiserror doesn't fit  |
| FFI / `no_std`  | Hand-rolled enum with `#[non_exhaustive]`       | No allocator dependency                                            |

**Never** `Box<dyn Error>` in library APIs — callers lose matchability. **Never** `anyhow` in a library — it leaks `anyhow::Error` into your public surface.

## Logging and tracing

- **`tracing`** over `log` for new projects — structured fields, spans, async-aware. The ecosystem has converged.
- **`tracing-subscriber`** with `EnvFilter` for runtime log-level control.
- **Spans** at meaningful boundaries (request, job, transaction); fields for IDs you'll want to search on.
- Avoid `println!` / `eprintln!` in library code — they bypass the user's chosen logger.

## Idiomatic patterns

- **Newtype** for IDs: `struct UserId(u64);`. Catches "passed an OrderId where a UserId was expected" at compile time; same runtime cost as the raw type.
- **Builder pattern** for structs with many optional fields. Crates: `bon` (modern, derive-based) or `derive_builder`.
- **Typestate** for protocols (a value can only call certain methods when it's in a particular state): `enum Connection<S> { ... }` with `S: ConnectionState`.
- **Sealed traits** for closed hierarchies — `pub trait Foo: private::Sealed { ... }`. Lets the crate define all impls.
- **`From` / `TryFrom` / `Into` / `AsRef`** — implement these conventionally so callers don't have to wrap arguments. Follow Rust API Guidelines C-CONV.

## Async

- **Pick one runtime**: `tokio` (default for most domains) or `async-std` / `smol` (smaller, fewer features). Don't link two.
- **`Send + Sync` discipline**: a future passed to `tokio::spawn` must be `Send + 'static`. Holding a non-Send guard across an `await` produces hard-to-read errors — restructure.
- **Cancellation safety**: `.await` points can drop the future at any time. State machines holding locks or mid-write data across `.await` are footguns. Make critical sections small and synchronous.
- **`tokio::select!`** for racing futures; remember the not-selected branches are dropped.
- **`pin_project`** when you need to manually project pins; otherwise let `async fn` / `Pin<Box<dyn Future>>` handle it.

## Supply chain

- **`cargo-audit`** in CI — checks dependencies against RUSTSEC advisories.
- **`cargo-deny`** in CI — license enforcement, denied crates, advisory checks. Configure via `deny.toml`.
- **`Cargo.lock`** committed for binaries; **not committed** for libraries (Cargo's default).
- **Workspace dependencies** to keep versions aligned across a workspace:
  ```toml
  [workspace.dependencies]
  serde = "1"
  tokio = { version = "1", features = ["full"] }
  ```
  Members opt in with `serde = { workspace = true }`.

## Documentation

- **`cargo doc --open`** during development.
- **Doc tests** are real tests — `cargo test --doc` runs them. Keep them passing.
- **`#![warn(missing_docs)]`** for libraries; the warnings list undocumented public items.
- **Examples** in `examples/` directory — buildable, runnable demonstrations of the public API.

## Security

- **`unsafe` blocks** require a `// SAFETY:` comment naming the invariants the caller is relying on. Sprinkling `unsafe` without justification is a hard `must`-level violation in code review.
- **Validate untrusted input** at the boundary (`serde` + `#[serde(deny_unknown_fields)]`, custom deserializers, parser combinators). Never propagate untrusted bytes inward.
- **Time-of-check vs time-of-use**: file system races, atomic operations on paths. Use `openat2` (Linux) or appropriate platform primitives when security-relevant.
- **Constant-time comparison** for secrets via `subtle::ConstantTimeEq`; never `==` on tokens or password hashes.
- **`RUSTSEC` advisories** — `cargo audit` flags known-vulnerable dependencies; fix or pin around them.

## Testing

- **Unit tests in the same file** (`#[cfg(test)] mod tests { ... }`); integration tests in `tests/`.
- **Doc tests** for examples that show up in `cargo doc`.
- **`proptest`** for property-based testing of pure logic.
- **`criterion`** for benchmarks — statistically rigorous, vs the unstable `#[bench]`.
- **`insta`** for snapshot testing of complex outputs (serialized data, error messages).
- **`mockall`** or hand-rolled fakes — prefer hand-rolled when the seam is small; mockall when many traits need mocking and the boilerplate would dominate.
