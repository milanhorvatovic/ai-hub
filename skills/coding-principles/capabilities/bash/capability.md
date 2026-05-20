---
name: coding-principles-bash
description: >
  Bash-specific capability of the coding-principles skill. Loaded when the
  task touches *.sh / *.bash files or scripts with a #!/usr/bin/env bash
  shebang. Covers the safety floor (set -euo pipefail, IFS), quoting and
  expansion rules, function/return conventions, file and process handling,
  arrays, anti-patterns (useless cat, eval, parsing ls, etc.), and the
  tooling floor (shellcheck, shfmt). Extends the parent skill; does not
  override its principles.
---

# Bash capability

Language-specific rules layered on top of the parent `coding-principles` skill. Apply when editing `*.sh` / `*.bash` files or shebangs `#!/usr/bin/env bash`.

> **Industry best practices** — external standards (Google Shell Style Guide), modern toolchain consensus (shellcheck, shfmt, bats-core), exit-code conventions (sysexits.h), 12-factor CLI discipline, single-instance locking, and security hardening live in `best-practices.md` in this directory. Load it alongside this file when the task warrants justifying choices against industry standards.

## Safety floor

Every script starts with:

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

- `-e` exit on error; `-u` unset-var error; `-o pipefail` failed step in a pipe fails the pipe.
- Set `IFS` explicitly so word splitting is predictable.
- Use `#!/usr/bin/env bash`, not `#!/bin/bash` (macOS ships bash 3.x at `/bin/bash`).

If a script must keep running past errors in one block, scope the relaxation:

```bash
set +e
risky_thing
rc=$?
set -e
```

## Quoting and expansion

- Quote every variable expansion: `"$var"`, `"${arr[@]}"`. Unquoted = word-splitting bugs.
- Use `${var:-default}` for fallbacks, not `if [ -z ]` chains.
- Prefer `[[ ... ]]` over `[ ... ]` — supports `&&`, `||`, regex `=~`, no word-splitting on the LHS.
- Arithmetic: `$(( ... ))`, not `expr`.

## Functions and return values

- Functions return data via stdout, status via exit code. Do not "return a string" — capture with `$(fn)`.
- Use `local` for every variable inside a function; otherwise it leaks globally.
- Validate args early: `[[ $# -ge 2 ]] || { echo "usage: ..." >&2; exit 2; }`.

## File and process handling

- Never parse `ls`. Use globs, `find -print0 | xargs -0`, or `mapfile -t arr < <(...)`.
- Use `mktemp` for temp files; `trap 'rm -rf "$tmp"' EXIT` for cleanup.
- Prefer process substitution `<(cmd)` over temp files when you can.

## Arrays

- Lists go in arrays, not space-separated strings. Use `arr=(a b c)`, expand as `"${arr[@]}"`.
- Associative arrays (`declare -A`) need bash 4+; gate with version check if portability matters.

## Anti-patterns

Language-specific anti-patterns live in `anti-patterns.md` (sibling). Load it for review-mode scans or pre-commit smell checks; the language-agnostic catalog is in `../../references/smells.md`.

## Tooling

- `shellcheck` is the authoritative linter. Treat its warnings as errors unless the script has a documented `# shellcheck disable=SCXXXX` with a one-line reason.
- `shfmt` for formatting (most projects: `shfmt -i 2 -ci`).
- For complex scripts (>200 lines, multiple subcommands, structured I/O), switch to Python or Go. Bash is the wrong tool past a certain size.

## Verification

Before declaring done:

- Run `shellcheck script.sh`.
- Run the script with `bash -x script.sh` once on the happy path.
- Test at least one error path (missing arg, missing file).

## Examples by principle

Concrete before/after code for high-leverage principles lives in `examples.md` (sibling). Load it when matching patterns at write-time or validating suggested fixes at review-time.

## Performance

Performance idioms (and the "measure first" discipline) live in `performance.md` (sibling). Load it when working on a hot path or large-data code — not for routine changes.

## Concurrency

Concurrency model, decision matrix, and correctness traps live in `concurrency.md` (sibling). Load it when the task involves parallelism, async, or shared state.

## Project structure

Language-specific structure mechanics (modularity unit, visibility/boundary enforcement, ports & adapters, dependency injection, layout) live in `project-structure.md` (sibling). It is the *how* for this language; `../../references/architecture.md` is the cross-language *why*. Load when structuring or restructuring a project.

## Dependencies

Dependency-management mechanics (version pinning, lockfiles, audit tools, update cadence, minimal footprint) live in `dependencies.md` (sibling). Default stance: **pin explicit exact versions** for applications/binaries (reproducibility); ranges only for published libraries. Load when adding, updating, or auditing dependencies.

## Cross-cutting references

Concern-specific, language-agnostic references live in `../../references/` — `api-design.md`, `persistence.md`, `observability.md`, `platform-matrix.md`, `resilience.md`, `data-handling.md`, `architecture.md`, `configuration.md`. Load the one matching the concern the code touches (see the table in the root `SKILL.md`). They apply across all language capabilities.
