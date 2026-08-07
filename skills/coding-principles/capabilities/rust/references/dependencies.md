# Rust — dependency management

Language-specific dependency mechanics. The cross-language principles (semver, lockfile discipline, audit, minimal footprint) are thin; the mechanics differ per ecosystem. Load when adding, updating, or auditing Cargo dependencies.

> **The tools named below were last checked 2026-08.** The mechanics do not decay; the tools do. How to read a stamped file is stated once under "Currency" in `../../../SKILL.md`.

## Pinning stance — pin explicit exact versions (default), mind the caret gotcha

**The Cargo gotcha**: a bare version is an *implicit caret*. `serde = "1.0.197"` means `^1.0.197` (`>=1.0.197, <2.0.0`) — it is **not** a pin. To truly pin, use `=`:

```toml
# Cargo.toml — bare version is NOT a pin (implicit caret)
serde = "1.0.197"      # actually ^1.0.197 — floats within 1.x

# exact pin (the preferred default for applications/binaries)
serde = "=1.0.197"
tokio = { version = "=1.40.0", features = ["full"] }
```

- **Applications / binaries**: prefer exact `=` pins in `Cargo.toml`, *and* commit `Cargo.lock`. `Cargo.lock` already pins the full transitive tree for binaries — the `=` pins make the manifest itself explicit too.
- **`Cargo.lock` commit rule**: commit it for **binaries** (reproducible builds); by Cargo convention do **not** commit it for **libraries** (let consumers resolve). This is the standard; this skill's pin-exact default applies to the binary case.

**Exception (ecosystem constraint, not style): published libraries.** A library must **not** use `=` pins — exact pins in a library force the whole dependency graph to one version and make the crate nearly unusable alongside others. Libraries use caret (the default bare version) so the ecosystem can unify versions. So: `=` pins + committed lock for binaries; caret + no committed lock for published libraries. Surface this when the crate is a library.

## Toolchain

- **`cargo add serde@=1.0.197`** to add a pinned dep; `cargo update` to bump within constraints (review the lockfile diff).
- **`cargo-audit`** — RUSTSEC advisory check against the locked tree. CI floor.
- **`cargo-deny`** — advisories + license policy + banned/duplicate crates, via `deny.toml`. CI floor.
- **`cargo-machete`** — find unused dependencies; prune them.

## Version syntax

- `=1.2.3` — exact pin (preferred default for binaries).
- `1.2.3` / `^1.2.3` — caret, implicit on bare versions (`>=1.2.3, <2.0.0`). The right choice for libraries.
- `~1.2.3` — tilde (`>=1.2.3, <1.3.0`).
- `*` — never.

## Update cadence

- Renovate / Dependabot to detect; **review every bump** and the resulting `Cargo.lock` diff. Run `cargo test` + `cargo audit`.
- `cargo update -p crate@version` for a targeted bump rather than updating everything at once.

## Minimal footprint

- Rust compile times and binary size scale with the dependency tree. Before adding: is it maintained, does it pull a heavy transitive tree (`cargo tree`), could a small piece of std or a tiny focused crate do?
- Watch feature flags — enable only the features you use (`default-features = false` + explicit features) to cut the tree.

## Principle alignment

- **Reproducibility** — `=` pins + committed `Cargo.lock` (for binaries) = deterministic builds (this skill's default); the caret gotcha is the trap that silently defeats it.
- **No dead code** (principle 20) — `cargo-machete` prunes unused deps.
- **Security** (principle 13) — `cargo-audit` / `cargo-deny` against the locked tree.
