# Tooling floors

The bar each covered language is audited against. A floor is the tooling a project needs before its other quality decisions can hold: a linter that runs, a formatter nobody argues with, types checked where the language offers them, and a version story that does not drift. Everything above the floor is preference, and this skill does not grade preference.

These floors are shared with the fleet's coding rulebook and held to it by a test in the repository that ships both. The guarantee is worth stating precisely rather than as "identical", because it is not symmetric: the set of **tools** must match in both directions, so neither side can add or drop one alone, while the **requirements** attached to a tool — the flags that make `cargo clippy` mean `--all-targets -- -D warnings` — are held one way. This skill may ask for more than the rulebook spells out; it can never ask for less. What that leaves unguarded is the rulebook relaxing on its own, in which case this file is the stricter of the two, which is the safe direction to differ in. Where a floor names two tools with _or_, they are genuinely equivalent for the purpose and the repository's existing choice decides — naming both is the point, not indecision.

Each row's **Verify with** column is the command a maintainer runs to confirm the tool is doing its job. The doctor never runs these; it reports whether the repository has arranged for something to run them.

## python

| Tool | Role | Floor | Verify with |
| --- | --- | --- | --- |
| `ruff` | lint and format | Configured for both jobs; warnings treated as errors in CI | `ruff check . && ruff format --check .` |
| `mypy` _or_ `pyright` | static types | One of them covers the code the project ships. The floor's own wording asks for hints on the public surface — module-level functions, class methods, dataclass fields — and that is a property of the source rather than of the configuration, so it is reported and never graded here: this row is satisfied by scope, and annotation completeness is carried beside it as an unassessed fact | `mypy <pkg>` |
| `uv` _or_ `poetry` _or_ `pip-tools` _or_ `hatch` | environment | The project manages its environment with one of them rather than installing into a global interpreter | the project's own lock or sync command |

Language version: target a Python still receiving security fixes, which is a moving line rather than a number this file can hold — read it from the upstream support schedule at audit time, not from memory. A project that deliberately pins below it in `pyproject.toml`, `setup.cfg`, or `python_requires` has made a decision, not left a gap; an _undeclared_ version is a gap, because nothing then holds contributors to the same interpreter. State the version this audit read the schedule as saying, so a reader can tell a current answer from a stale one.

## typescript

| Tool | Role | Floor | Verify with |
| --- | --- | --- | --- |
| `tsc` | typecheck | `tsconfig.json` sets `"strict": true`, and a typecheck runs somewhere other than the bundler | `tsc --noEmit` |
| `eslint` _or_ `biome` | lint | One linter, not two | `eslint .` or `biome check .` |
| `prettier` _or_ `biome` | format | One formatter, not two; `biome` satisfies this row and the one above together | `prettier --check .` or `biome check .` |

Beyond `strict`, the compiler options worth enabling once a project is healthy enough to absorb them are `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `noFallthroughCasesInSwitch`. Their absence is a recommendation, never a gap. New packages should target ESM (`"type": "module"`) unless the project is locked to CommonJS.

The failure this language produces more than any other is two tools claiming the same job — `prettier` formatting alongside `biome`, or `eslint` carrying formatting rules that fight the formatter. Overlap is a finding in its own right; see `diagnosis-grading.md`.

## rust

| Tool | Role | Floor | Verify with |
| --- | --- | --- | --- |
| `cargo fmt` | format | Checked in CI, not merely available, over every workspace member | `cargo fmt --all --check` |
| `cargo clippy` | lint | Runs with warnings denied, over all targets of every selected package | `cargo clippy --workspace --all-targets -- -D warnings` |

The package-selection flags are in the stated commands because they are the spelling that is correct everywhere, not because their absence is itself the defect. What the audit grades is coverage: Cargo's default selection depends on the workspace's shape — a virtual root with no `default-members` already selects every member, while a root that is itself a package selects only that root — so a command without `--workspace` is complete in the first case and leaves members unchecked in the second. Resolve the shape, then grade the members actually reached. Writing the flags is what makes one command right in both, which is why the floor states them and why a scaffold uses them. `cargo check` does not satisfy the lint row: it answers whether the crate compiles, and `clippy` is what catches the things that compile and should not. A CI job running `cargo check` where `clippy` belongs is the most common shape of this gap, and it looks green while checking less than it appears to.

Edition and MSRV are declarations rather than tools: prefer the latest edition the project has adopted, do not mix editions across a workspace, and respect the minimum supported Rust version `Cargo.toml` declares — a config this skill scaffolds never raises it.

## bash

| Tool | Role | Floor | Verify with |
| --- | --- | --- | --- |
| `shellcheck` | lint | The authoritative linter for shell; its warnings are errors unless a script carries a documented `# shellcheck disable=SCXXXX` with a one-line reason | `shellcheck script.sh` |
| `shfmt` | format | Configured with the project's indentation; most projects use `-i 2 -ci` | `shfmt -d -i 2 -ci .` |

The floor has a size limit rather than a third tool: past roughly 200 lines, multiple subcommands, or structured I/O, shell is the wrong language and no amount of linting fixes that. The doctor reports the threshold when it sees a script well past it, as an observation rather than a finding — rewriting a working script is a decision far above a tooling audit's pay grade.

Shell has no manifest, so its scripts hide in places the other languages' tooling never has to look: `scripts/`, `.githooks/`, `bin/`, CI `run:` blocks, and files with no extension whose first line is a shell shebang. A scan that only globs `*.sh` will under-report, which reads as a clean bill of health for a repository that has never linted a hook.
