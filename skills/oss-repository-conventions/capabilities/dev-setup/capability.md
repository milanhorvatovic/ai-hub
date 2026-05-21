---
name: dev-setup
description: >
  Scans, audits, and scaffolds a repository's reproducible development
  environment — toolchain pinning (mise, .tool-versions, .nvmrc, .python-version),
  separately-declared dev/test dependencies, a one-command bootstrap (setup
  script, make target, or mise task), an .env.example for required config, and an
  optional devcontainer. Audit flags an unpinned toolchain and a missing
  bootstrap path; scaffold writes a mise.toml (house style), an .env.example, and
  a setup script. Triggers on "how do I set up the dev env", "pin the toolchain",
  "add a setup script", "make onboarding reproducible", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# dev-setup capability

Governs how reliably a contributor can go from `git clone` to a running, testable checkout: is the toolchain pinned, are dev dependencies declared, and is there a single bootstrap path. Reads and judges by default; writes setup files only on confirmation.

## Modes

- **scan** — report the toolchain pinning, dev deps, and bootstrap path present.
- **audit** — judge reproducibility against `../../references/oss-health-rubric.md`.
- **scaffold** — write mise.toml / .env.example / a setup script after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Detect the stack first (languages, package managers) so recommendations fit; never propose a Node toolchain for a pure-Python repo.
- House style pins toolchains with `mise` — prefer it when the repo is silent, but honor an existing `.tool-versions` / `.nvmrc` rather than churning.
- Running the actual setup is the user's call — propose the command; don't execute installs.

## Languages

Detect per `../../references/language-support.md`. Toolchain-pinning support:

- **First-class:** anything `mise` / `asdf` pins (Python, Node / JS-TS, Go, Rust, Ruby, …) plus per-language version files (`.python-version`, `.nvmrc` / `.node-version`, `rust-toolchain.toml`, `.ruby-version`); Swift via Xcode / `.swift-version`.
- **Recognized:** ecosystems without a mise plugin — document the manual install and version source.
- **Unknown:** document a manual, reproducible setup path; never invent a version manager for the stack.
- **Compiled languages** need a build toolchain pinned, not just a runtime (Xcode for Swift, the Go/Rust toolchain, a JDK for Java/Kotlin).
- **Version currency:** flag a toolchain pinned to an end-of-life release (e.g. Python ≤ 3.8, Node ≤ 16, an unsupported Go/Rust) and recommend a supported version — pinned-but-EOL is reproducibly insecure.

## Scan

Sources (catalog: `../../references/convention-files.md`), citing each:

1. Toolchain pinning: `mise.toml` / `.mise.toml`, `.tool-versions` (asdf), `.nvmrc`, `.node-version`, `.python-version`, `.ruby-version`.
2. Dev dependencies: `requirements-dev.txt` / dev extras in `pyproject.toml`, `devDependencies` in `package.json`, the dev group in `Gemfile` / `go.mod` tool directives.
3. Bootstrap path: `scripts/setup*`, `bin/setup`, a `setup`/`bootstrap` target in `Makefile` / `Justfile`, or `mise` tasks.
4. Config surface: `.env.example` / `.env.sample`; whether the app reads env vars without a documented example.
5. Containerized env: `.devcontainer/` / `devcontainer.json`.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `toolchain-pinned` — **should**. Fail when language/tool versions aren't pinned anywhere. Unpinned toolchains cause "works on my machine" drift between contributors and CI.
- `dev-deps-declared` — **should**. Fail when dev/test dependencies aren't declared separately from runtime deps. Contributors can't install the test toolchain reproducibly.
- `one-command-bootstrap` — **could**. Pass when a single documented command/script takes a clone to runnable. Cuts onboarding from hours to minutes.
- `env-example` — **could** (when the app needs config/secrets). Pass when `.env.example` lists required variables without real values. Documents config without leaking it.
- `devcontainer` — **could**. Pass when a devcontainer offers an instant reproducible env. Optional polish.

CI parity note: the toolchain CI installs should match what's pinned here; flag drift between `mise.toml` and the versions used in workflows (deep CI coverage is the ci-automation capability).

## Scaffold

Templates live in `references/scaffold-templates.md` (mise.toml, .env.example, setup script). Write after confirmation, one file at a time, tailored to the detected stack:

- **`mise.toml`** — pin the languages/tools at the versions the repo already uses (read from existing configs / CI), house style.
- **`.env.example`** — list the env vars the code reads (grep for `os.environ` / `process.env`), with placeholder values.
- **setup script / make target** — install the toolchain, dependencies, and hooks in one command; reference it from CONTRIBUTING.

## Output

Report per `../../references/output-format.md`: scan emits the dev-env inventory with sources; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **Library vs app** — a library may not need `.env.example`; relax it.
- **Existing asdf `.tool-versions`** — don't force a migration to mise; note both work and only flag if neither pins versions.
- **Polyglot/monorepo** — pin per-package toolchains where needed; a single root pin may be insufficient.
- **No package manager** (docs/data repo) — relax dev-deps and bootstrap to `could`.

## Anti-patterns

- Don't run installers or modify the local environment — propose the commands.
- Don't recommend a toolchain for a stack the repo doesn't use.
- Don't churn an existing working pinning scheme just to match house style.
- Don't write an `.env.example` containing real secret values.
