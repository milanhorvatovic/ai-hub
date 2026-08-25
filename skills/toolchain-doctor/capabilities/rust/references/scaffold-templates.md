# rust — scaffold templates

Shapes to fill in from what the scan found. Placeholders in angle brackets are values the scan already established.

## Lints in `Cargo.toml` — on request only

**Nothing here is scaffolded by default.** The floor's lint row is satisfied by the CI command below, which already denies warnings; no audit rule produces a missing-manifest-lints finding, so writing a lint table would add a standing policy that traces to nothing the report said. That is the same reason an `unsafe_code = "forbid"` line does not belong — and there it also breaks a crate that legitimately uses `unsafe`.

Where a maintainer asks for lint levels in the manifest, this is the shape. The manifest is the better home than crate-root attributes: it is readable without opening source, it inherits across a workspace, and changing a level does not touch a `.rs` file.

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

Where a maintainer asks to read the pedantic set, a second non-gating invocation is the shape where the claim and the behaviour match — offered on the same terms as the lint table above, never written by default:

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
on:
  pull_request:
  push:
    branches: [<the default branch>]

permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<40-char-sha> # <the version this sha is>
      - uses: <rust setup action>@<40-char-sha> # <the version this sha is>
        with:
          components: rustfmt, clippy
      - run: cargo fmt --all --check
      - run: cargo clippy --workspace --all-targets -- -D warnings
```

The trigger and the permission floor are part of the scaffold, not context around it. A bare job fragment dropped into a push-only workflow still grades `wiring` on the next audit — it runs, and not where review happens — so a scaffold that omitted `on: pull_request` would not close the finding it was written for. And a job that runs repository code inherits whatever token permissions the repository defaults to, which on an older repository is write; `contents: read` is the floor, raised only for a scope the job demonstrably needs.

Every element of the `clippy` line is load-bearing, and two of them answer different questions. `--all-targets` brings tests, benches, and examples into scope, which is where a surprising share of a crate's code lives. `--workspace` decides which _packages_ get looked at, and it is written here because it is correct in every workspace shape rather than because omitting it is always wrong: Cargo's default selection is every member from a virtual root with no `default-members`, and the root package alone from a root that is itself a package. A job without the flag is therefore complete in one shape and blind to its members in the other. The audit grades the members reached rather than the flag's presence — a scaffold that spells it out simply cannot land on the wrong side of that. `-- -D warnings` is what turns output into a gate; without it the job passes while printing the findings it was added to catch. And `clippy` rather than `check` is the difference between "does this compile" and "is this right" — a pipeline running `cargo check` here is the most common way this floor row goes unmet while looking met.

`cargo fmt --all` carries the same package-selection reasoning as clippy's `--workspace`; the spellings differ because `fmt` predates that flag and kept `--all` as its name for it.

There is no test step here, deliberately. Testing is not a row of the tooling floor and no audit finding produces it, so adding one would be the scaffold deciding what the project should run rather than closing something the report named. Where a repository already has a test command, it stays when this template is adapted — the rule is that the doctor does not introduce one.

## Testing the MSRV you declare

A `rust-version` nothing builds against is a promise with no evidence. Where the crate declares one, add it to the matrix rather than trusting it:

```yaml
strategy:
  matrix:
    rust: ["<the declared rust-version>", "stable"]
steps:
  - uses: actions/checkout@<40-char-sha> # <the version this sha is>
  - uses: <rust setup action>@<40-char-sha> # <the version this sha is>
    with:
      toolchain: ${{ matrix.rust }}
```

The matrix value has to reach the setup action's toolchain input, which is the step this snippet exists for. A matrix that names two toolchains while the setup step installs its default gives two jobs on the same compiler — the older version is never built, and the audit would read the matrix as evidence the declared MSRV is exercised when nothing installed it.

Run whatever build or test commands the project already has on the older toolchain, and not the lint steps above — `clippy` lints move between releases, so holding lint results to an MSRV toolchain produces failures about the linter's age rather than the code's correctness.
