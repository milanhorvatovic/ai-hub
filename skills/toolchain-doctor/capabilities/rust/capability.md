---
name: rust
description: >
  Examines a Rust crate or workspace's tooling and prescribes what is missing —
  reads Cargo.toml for edition and rust-version, rustfmt.toml, clippy.toml, and
  lint tables; establishes whether CI runs clippy with warnings denied rather
  than a bare cargo check; grades the distance to the rust floor (cargo fmt
  checked in CI, clippy over all targets at deny-warnings); and scaffolds
  configs and CI steps on confirmation. Never raises a declared MSRV and never
  installs a toolchain. Triggers on "set up clippy", "should CI fail on
  warnings", "what belongs in rustfmt.toml", "do we need cargo-deny", or a
  crate whose CI runs cargo check where clippy belongs.
allowed-tools: Bash Read Grep Glob Write
---

# rust capability

Audits a Rust crate or workspace's toolchain configuration. Modes and their contracts come from `../../references/modes.md`; the bar is the rust section of `../../references/tooling-floors.md`; grades are `../../references/diagnosis-grading.md`.

## Where the declarations live

| Tool | Config locations |
| --- | --- |
| `cargo fmt` | `rustfmt.toml`, `.rustfmt.toml` — absence means defaults, which are a legitimate choice |
| `cargo clippy` | `clippy.toml`, `.clippy.toml`, plus `[lints.clippy]` in `Cargo.toml` and `#![deny(clippy::…)]` attributes at crate roots |
| toolchain | `rust-toolchain.toml`, `rust-toolchain` |
| edition and MSRV | `Cargo.toml` `[package] edition` and `rust-version`; per-member in a workspace, and `[workspace.package]` for inherited values |
| supply chain | `deny.toml` (`cargo-deny`), `audit.toml` (`cargo-audit`) — above the floor, reported when present |

A workspace complicates every row: values can be inherited with `edition.workspace = true`, and a member that opts out is a real difference rather than an oversight. Resolve inheritance before grading, and report per-member differences as facts — a workspace where one member sits on an older edition usually has a reason, and the audit's job is to surface it, not to flatten it.

## What the scan reports

1. **Format check in CI** — not whether `rustfmt` exists, which it always does, but whether anything runs `cargo fmt --check`, **and over which packages**. This is the row most often missing, because the tool is available on every developer's machine and nothing notices when it stops being run; and where it is present in a workspace, `--check` without `--all` can cover the root package alone. Resolve the members it reaches and report the omitted crates, the same way the lint row does — the scaffold prescribes `--all` for exactly this reason, and a scan that graded any `cargo fmt --check` as complete would contradict it.
2. **Lint invocation** — the exact command CI runs. `cargo check`, `cargo clippy`, `cargo clippy -- -D warnings`, and `cargo clippy --all-targets -- -D warnings` are four different levels of coverage and are reported as what they are.
3. **Where lints are configured** — `Cargo.toml` `[lints]`, a `clippy.toml`, or crate-root attributes. Report the split as a fact; it is a `drift` finding only when two of them set a different level for the **same** lint, because that is the case where the effective rule is not what one of the files says. The three locations do different jobs — `clippy.toml` holds thresholds, `[lints]` holds levels, a crate attribute holds a local exception someone wrote a reason for — so a repository using all three is usually organized rather than confused, and grading the arrangement instead of the contradiction produces a finding with no fix behind it.
4. **Edition and MSRV** — declared, inherited, or absent, per member.
5. **Toolchain pinning** — whether a `rust-toolchain.toml` exists and what channel it names. A crate pinned to `nightly` for a reason is a decision; one pinned to `nightly` with no nightly-only feature in sight is worth a question.

## Audit specifics

Three checks carry most of this language's value:

- **`cargo check` standing in for `clippy`.** The floor's lint row is not satisfied by `cargo check`: it answers whether the crate compiles, and `clippy` is what catches what compiles and should not. A CI job running `check` where `clippy` belongs is green, fast, and checks materially less than a reader assumes — grade the lint row a `gap` and say exactly this in the prescription.
- **`clippy` without `-D warnings`.** Warnings that do not fail anything accumulate until nobody reads the output. The row is graded `wiring` rather than `gap`: the tool runs, and its result is discarded.
- **`--all-targets` omitted.** A default `cargo clippy` skips tests, benches, and examples. Test code is code, and a lint gate that exempts the test suite exempts a large share of most crates. This is a `wiring` finding, the same grade the package-selection and shell-coverage cases take: the tool runs, and it runs over less than the report implies. Naming the grade matters more here than the wording, because a check stated without one leaves the choice between `gap` and `wiring` to whoever reads it next.
- **Package selection mistaken for target selection.** `--all-targets` widens which _targets_ of the selected packages are linted; it does not widen which packages are selected. In a workspace the selection comes from `--workspace`, `-p`, or, when neither is given, Cargo's default — and that default is not one rule. A **virtual** workspace, whose root manifest declares no package of its own, defaults to every member. A **non-virtual** one, where the root is itself a package, defaults to the root package alone. `default-members`, where present, overrides both.

So the case worth checking first is the ordinary root-package workspace that sets no `default-members` at all: `cargo clippy --all-targets` there lints the root and nothing else, and a rule keyed to `default-members` being present would miss it. Read the workspace's shape, then the selection flags, then the target flags — three facts, not one — and grade the lint row against the members actually covered. Members left uncovered are a `wiring` finding naming them, not a satisfied row.

- **Lints riding a floating toolchain.** `cargo fmt` and `cargo clippy` ship with the toolchain, so their version is the channel's. A crate on `stable` therefore takes new lints the day they release, and a green pull request can redden on a change nobody made. Unlike the other languages this is the ecosystem's own default and usually a `decision` rather than a `floating` finding — the audit's job is to say it out loud, once, so a team that keeps hitting it knows the lever exists and that pinning the channel costs them the new lints.

A declared MSRV satisfies its row and carries no grade — the floor asks the project to declare one and respect it, so declaring it is compliance rather than a decline. Report the value among the scan's facts. What the audit does say is when CI does not test it: a `rust-version` nobody builds against is a promise with no evidence behind it. That is a `wiring` finding — the declaration exists and nothing exercises it — and the prescription is a CI matrix entry rather than a change to the declaration.

## Scaffold

Templates: `references/scaffold-templates.md` in this directory.

Two constraints specific to this language. A scaffolded config never raises the declared `rust-version` — if a lint or a config key the template uses requires a newer toolchain than the crate promises, say so and let the user choose. And a scaffold never adds `#![deny(…)]` at a crate root when `Cargo.toml` can express the same thing under `[lints]`: the manifest is readable, inheritable across a workspace, and does not require editing source files to change a lint level.
