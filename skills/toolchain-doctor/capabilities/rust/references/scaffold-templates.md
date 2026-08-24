# rust — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established.

## Lints in `Cargo.toml`

The manifest is the first home for lint levels, ahead of crate-root attributes: it is readable without opening source, it inherits across a workspace, and changing a level does not touch a `.rs` file.

Only the clippy floor goes in. An `unsafe_code = "forbid"` line is a tempting thing to add here and does not belong: no floor row asks for it and no finding produces it, so scaffolding it would break the rule that every written change traces to something the audit said — and on a crate with legitimate `unsafe`, it breaks the build instead. It is a policy a maintainer chooses, available on request and never by default.

```toml
[lints.clippy]
all = "deny"
```

In a workspace, declare once at the root and inherit:

```toml
# workspace root
[workspace.lints.clippy]
all = "deny"

# each member
[lints]
workspace = true
```

`pedantic` is deliberately absent from the gated configuration, and it cannot be added back as `"warn"` to make it advisory. The CI step below denies warnings, which promotes every enabled warn-level lint to an error — so a "reading list" set here would gate exactly as hard as `all = "deny"` while claiming not to, and the reliable outcome of hundreds of pedantic findings on an existing crate is that someone switches the whole thing off.

Read the pedantic set with a second, non-gating invocation instead, where the claim and the behaviour match:

```yaml
    - name: clippy pedantic (advisory)
      run: cargo clippy --workspace --all-targets -- -W clippy::pedantic
      continue-on-error: true
```

That step is the one place `continue-on-error` belongs in this template: it is advisory by design and says so, rather than being a gate that quietly cannot fail.

## `rustfmt.toml`

Only scaffold this when the project wants something other than defaults. `rustfmt`'s defaults are good, and an empty config file is a maintenance item that promises a decision nobody made.

```toml
edition = "<the crate's edition>"
```

The `edition` key belongs here even in a minimal config: `rustfmt` formats some constructs differently per edition, and a config that omits it formats against a default that may not be the crate's.

## Declaring the toolchain

```toml
[toolchain]
channel = "<stable, or the exact version the project pins>"
components = ["rustfmt", "clippy"]
```

Listing the components is what makes a fresh checkout able to run the floor's commands. Without it, a contributor whose toolchain was installed without `clippy` gets a missing-component error rather than lint output, which reads like a broken repository rather than a missing component.

## The CI steps

```yaml
check:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@<40-char-sha> # <the version this sha is>
    - uses: <rust setup action>@<40-char-sha> # <the version this sha is>
      with:
        components: rustfmt, clippy
    - run: cargo fmt --all --check
    - run: cargo clippy --workspace --all-targets -- -D warnings
    - run: cargo test --workspace
```

Every element of the `clippy` line is load-bearing, and two of them answer different questions. `--all-targets` brings tests, benches, and examples into scope, which is where a surprising share of a crate's code lives. `--workspace` decides which _packages_ get looked at, and it is the one most often assumed rather than written: without it Cargo lints the default selection, which a workspace declaring `default-members` can narrow to a subset — so a job reading `clippy --all-targets` can look exhaustive and never touch a member. On a single-crate repository the flag is harmless surplus; in a workspace its absence is the gap. `-- -D warnings` is what turns output into a gate; without it the job passes while printing the findings it was added to catch. And `clippy` rather than `check` is the difference between "does this compile" and "is this right" — a pipeline running `cargo check` here is the most common way this floor row goes unmet while looking met.

`cargo fmt --all` and `cargo test --workspace` carry the same package-selection reasoning; the spellings differ because `fmt` predates the `--workspace` flag and kept `--all` as its name for it.

## Testing the MSRV you declare

A `rust-version` nothing builds against is a promise with no evidence. Where the crate declares one, add it to the matrix rather than trusting it:

```yaml
strategy:
  matrix:
    rust: ["<the declared rust-version>", "stable"]
```

Run only the build and test steps on the older toolchain — `clippy` lints move between releases, so pinning lint results to an MSRV toolchain produces failures about the linter's age rather than the code's correctness.
