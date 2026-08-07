# Rust — project structure & mechanics

Language-specific *mechanics* for the architecture concepts in `../../../references/architecture.md` (dependency-points-inward, hexagonal, package-by-feature). That file is the *why*; this is the Rust *how*. Load when structuring or restructuring a Rust crate or workspace.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Unit of modularity

- **Module** = a `mod` (a file, a directory with `mod.rs` / a `name.rs` + `name/` dir, or an inline `mod {}`). **Crate** = a compilation unit (one `lib.rs` or `main.rs`). **Workspace** = multiple crates.
- Within a crate, group by **feature/domain** module (`mod orders;`, `mod billing;`), not by layer. Layer within each.
- The crate is also the **strongest boundary** — splitting the domain into its own crate makes "domain may not depend on infra" a compile-time guarantee, not a convention.

## Visibility / boundary enforcement

Rust *enforces* visibility at compile time — the strongest of the four languages here:

- **Private by default.** Items are module-private unless marked `pub`.
- **`pub(crate)`** — visible within the crate, not exported. The workhorse for "internal but cross-module."
- **`pub(super)`** / **`pub(in path)`** — finer-grained scoping.
- **`pub`** — the crate's public API (minimum public surface — modular-by-composition mantra). Re-export the intended API from `lib.rs` with `pub use`; keep everything else `pub(crate)` or private.
- Multi-crate workspace: a crate simply *can't* depend on another unless it's in `[dependencies]` — the dependency direction is enforced by Cargo, not by a linter.

## Ports & adapters

- A **port** is a `trait`. Define it in the domain/application crate or module.
- An **adapter** is a type `impl`ementing the trait in the infrastructure crate/module.

```rust
// application layer — the port it needs
pub trait UserRepository {
    fn get(&self, id: UserId) -> Option<User>;
}

// infrastructure layer — adapter
pub struct PostgresUserRepository { /* pool, etc. */ }
impl UserRepository for PostgresUserRepository {
    fn get(&self, id: UserId) -> Option<User> { /* ... */ }
}
```

The domain depends on the `UserRepository` trait; the Postgres type lives in (and is only imported by) the infrastructure crate.

## Dependency injection

- **Pass values in** — generics (`fn handle<R: UserRepository>(repo: &R)`) for static dispatch (zero-cost, monomorphized), or trait objects (`repo: &dyn UserRepository`) for dynamic dispatch when you need heterogeneity. No DI framework; Rust DI *is* passing arguments.
- The composition root is `main` (binary) or the app constructor — build concrete adapters there (imperative shell — principle 16).
- Prefer generics for hot paths (no vtable); `dyn` when you store mixed implementations or want smaller binaries (see performance.md).

## Layout

Single crate:

```
crate/
├── Cargo.toml
└── src/
    ├── lib.rs                # pub use re-exports the public API
    ├── orders/
    │   ├── mod.rs            # module root
    │   ├── domain.rs         # entities + rules (pure)
    │   ├── service.rs        # use cases; defines trait ports
    │   └── repository.rs     # adapter
    └── billing/
└── tests/                    # integration tests (one binary per file)
```

Workspace (strong layer boundaries):

```
workspace/
├── Cargo.toml                # [workspace] + [workspace.dependencies]
└── crates/
    ├── domain/               # depends on nothing app-specific
    ├── app/                  # depends on domain
    └── infra/                # adapters; depends on domain + app
```

- **Unit tests** in-file (`#[cfg(test)] mod tests`); **integration tests** in `tests/` (each file is its own crate); **doc tests** in `///` comments (best-practices.md).
- **Workspace dependencies** (`[workspace.dependencies]`) keep versions aligned (best-practices.md).

## When not to structure

A small binary or one-off tool is a single `main.rs` with a few functions — no module tree, no traits-as-ports, no workspace (principle 4 / when-NOT-to-layer in the concept file).
