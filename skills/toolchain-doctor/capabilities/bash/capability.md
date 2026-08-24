---
name: bash
description: >
  Examines a repository's shell tooling and prescribes what is missing — finds
  the shell scripts other audits miss (hooks, bin directories, extensionless
  files with a shell shebang, CI run blocks), reads .shellcheckrc, .editorconfig,
  and shfmt flags, establishes whether anything lints them, grades the distance
  to the bash floor (shellcheck as an error-level linter, shfmt for format), and
  scaffolds configs and CI steps on confirmation. Never installs anything.
  Triggers on "lint our shell scripts", "set up shellcheck", "what shfmt
  flags", "our git hooks aren't checked", or a repository whose scripts have
  never been linted.
allowed-tools: Bash Read Grep Glob Write
---

# bash capability

Audits a repository's shell tooling. Modes and their contracts come from `../../references/modes.md`; the bar is the bash section of `../../references/tooling-floors.md`; grades are `../../references/diagnosis-grading.md`.

## Finding the scripts

This is the step that distinguishes a useful shell audit from a decorative one, and it comes before any config lookup. Shell has no manifest, so its files hide:

| Location | Why it is missed |
| --- | --- |
| `*.sh`, `*.bash` | Found by everyone; the easy case |
| Extensionless files with a shell shebang | `bin/deploy`, `scripts/release` — invisible to an extension glob, and usually the most consequential scripts in the repository |
| `.githooks/`, `.husky/` | Hooks are scripts, run on every commit, and routinely unlinted |
| CI `run:` blocks | Multi-line `run:` in a workflow is a shell script living in YAML; linting it needs the block extracted first |
| `Makefile` recipes | Each recipe line is shell, with its own quoting hazards and its own tab-sensitivity |
| Dockerfile `RUN` lines | Shell, executed at build time, and frequently the least reviewed lines in the repository |

Report the inventory before the grade. A repository that lints `scripts/*.sh` and has never looked at its hooks is not partially covered — it is uncovered in the place where an error runs on every developer's machine.

The first-line check is the reliable one for the extensionless case: a file whose first line is `#!/bin/sh`, `#!/bin/bash`, `#!/usr/bin/env bash`, or a variant is shell regardless of its name. When reporting these, name them individually rather than as a count — a maintainer recognizes their own scripts and can tell immediately whether the list is right.

## Where the declarations live

| Tool | Config locations |
| --- | --- |
| `shellcheck` | `.shellcheckrc`, per-file `# shellcheck` directives, CLI flags in whatever invokes it |
| `shfmt` | `.editorconfig` (`[*.sh]` section), or flags in the invocation — `shfmt` has no config file of its own |
| dialect | The shebang per file, plus any `shellcheck -s` flag; `sh` and `bash` are graded against different rules |

`shfmt` having no config file matters for the audit: its settings live wherever it is invoked, so establishing them means reading the CI step, the task runner, or the hook — not looking for a dotfile that will never exist. A repository with `shfmt` in CI and no `.editorconfig` is formatting to whatever flags that one call site passes, and a contributor's editor will disagree.

## What the scan reports

1. **The script inventory**, per the table above, with the hidden locations named explicitly.
2. **`shellcheck` presence and severity handling** — whether it runs, and whether its findings fail anything.
3. **Suppression directives** — every `# shellcheck disable=` in the tree, with whether each carries a reason. The floor asks for a one-line reason per suppression, and a bare disable is the thing this row exists to find.
4. **`shfmt` presence and flags** — including whether `.editorconfig` and the invocation agree.
5. **Coverage gaps** — scripts found by the inventory that the linter's invocation does not reach. A `shellcheck scripts/*.sh` step in a repository with hooks and a `bin/` directory covers a fraction of its shell and reports success.

## Audit specifics

- **Undocumented suppressions.** A `# shellcheck disable=SC2086` with no reason is a `gap` against the floor's stated bar, graded per instance rather than in aggregate so the report names the files. A suppression with a reason is a `decision` and is left alone.
- **Coverage under-reach.** Where the invocation's glob does not reach the inventory, that is a `wiring` finding: the linter runs, and not over the code. This is the most common real defect in this language and the least visible, because the job is green.
- **Dialect mismatch.** A script with a `#!/bin/sh` shebang using bash-only constructs is a genuine portability bug that `shellcheck -s sh` catches and a bash-dialect run does not. Report the mismatch; the fix is usually the shebang rather than the code.
- **Tools taken from whatever the runner ships.** `shellcheck` is preinstalled on the common hosted runners, which is why this floor is cheap to adopt and also why its version is the image's. That makes it a `floating` finding whenever the repository depends on the result being stable: the image updates, a new check fires, and a pull request goes red without touching a script. The fix is small — a pinned action or an explicit version in the install step — and worth proposing only where the repository has actually been bitten, since the alternative is pinning a linter to keep it from finding things.
- **Size.** A script well past a few hundred lines, with subcommands and structured output, has outgrown the language. Report it as an observation, never a finding — rewriting a working script is a decision far above a tooling audit, and the floor's own position is that no amount of linting fixes the size problem.

## Scaffold

Templates: `references/scaffold-templates.md` in this directory.

The scaffold rule specific to shell is about scope rather than content: the CI step's file list is scaffolded from the inventory the scan produced, not from a glob. A `*.sh` glob is what produced the coverage gap in the first place, and prescribing it again closes the finding on paper while leaving the hooks unlinted.
