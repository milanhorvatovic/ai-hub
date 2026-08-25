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
| `.githooks/`, `.husky/` | Hook scripts, routinely unlinted. They belong in the inventory whether or not anything activates them — an unlinted script is unlinted either way — but do not assume they run: both need wiring the repository may or may not carry |
| CI `run:` blocks | Multi-line `run:` in a workflow is a shell script living in YAML — when the step's shell is a shell. A `shell:` key can select `pwsh`, `python`, or something else entirely, and the default is not the same on every runner image |
| `Makefile` recipes | Each recipe line is shell, with its own quoting hazards and its own tab-sensitivity — unless the makefile sets `SHELL` to something that is not one |
| Dockerfile `RUN` lines | Shell in the shell form, executed at build time, and frequently the least reviewed lines in the repository — but a `SHELL` directive can change the interpreter, the exec form is not shell at all, and a Windows base image defaults to `cmd` |

**Resolve each location's interpreter before counting it.** Every row above can hold something that is not shell, and treating the location as proof of the language produces a shell audit of a repository that writes its CI steps in PowerShell — a lane that should never have loaded, reporting findings against files it has misread. Read the `shell:` key, the makefile's `SHELL`, the Dockerfile's directive and form; where the interpreter cannot be established, leave the block out and say so rather than assuming the common case.

**Files and embedded shell are reported separately, and only files are in the coverage contract.** `shellcheck` takes paths, so a `run:` block, a recipe, and a `RUN` line cannot be handed to it as they stand — which means a coverage finding against them would be one the scaffold has no prescription able to close, and a report full of those teaches a reader to ignore the section. Embedded shell is reported as an **observation** naming where it lives and roughly how much there is, with one prescription when the volume justifies it: move the block into a script file, which brings it inside the inventory and under the same linting as everything else. Repositories that keep a hundred lines of shell in a workflow step usually did it by accretion, and the observation is how they find out.

Where the inventory finds **no script files at all** — every line of shell embedded — both floor rows are `N/A`, not `gap`. Neither tool can consume a `run:` block, so there is nothing for the repository to have failed to configure and nothing a scaffold could write to close it; grading them would hand a `gap` to a repository whose only available remedy this capability has already framed as an observation. Say the rows are not applicable and why, the same way the typescript lane does for a project with no TypeScript in it.

Report the inventory before the grade. A repository that lints `scripts/*.sh` and has never looked at its hooks is not partially covered — it is uncovered in the place where an error runs on every developer's machine.

The first-line check is the reliable one for the extensionless case: a file whose first line is `#!/bin/sh`, `#!/bin/bash`, `#!/usr/bin/env bash`, or a variant is shell regardless of its name. When reporting these, name them individually rather than as a count — a maintainer recognizes their own scripts and can tell immediately whether the list is right.

## Where the declarations live

| Tool | Config locations |
| --- | --- |
| `shellcheck` | `.shellcheckrc`, per-file `# shellcheck` directives, CLI flags in whatever invokes it |
| `shfmt` | `.editorconfig` — the sections matching the inventory's paths, not `[*.sh]` alone — or flags in the invocation; `shfmt` has no config file of its own |
| dialect | The shebang per file, plus any `shellcheck -s` flag; `sh` and `bash` are graded against different rules |

`shfmt` having no config file matters for the audit: its settings live wherever it is invoked, so establishing them means reading the CI step, the task runner, or the hook — not looking for a dotfile that will never exist. A repository with `shfmt` in CI and no `.editorconfig` is formatting to whatever flags that one call site passes, and a contributor's editor will disagree.

## What the scan reports

1. **The script inventory**, per the table above, with the hidden locations named explicitly.
2. **`shellcheck` presence and severity handling** — whether it runs, and whether its findings fail anything.
3. **Suppression directives** — every `# shellcheck disable=` **in the inventoried script files**, with whether each carries a reason. The scope matters: a search across the whole tree also matches documentation, fenced examples, and prose about suppressions — this skill's own reference carries one as an illustration — and reporting those as undocumented suppressions is a finding about a sentence rather than about a script. Only a directive `shellcheck` would actually apply counts. The floor asks for a one-line reason per suppression, and a bare disable is the thing this row exists to find.
4. **`shfmt` presence and flags** — including whether `.editorconfig` and the invocation agree.
5. **Coverage gaps** — script **files** found by the inventory that the linter's invocation does not reach; embedded shell sits outside this row, per the note above. A `shellcheck scripts/*.sh` step in a repository with hooks and a `bin/` directory covers a fraction of its shell and reports success.

## Audit specifics

- **Undocumented suppressions.** A `# shellcheck disable=SC2086` with no reason is a `gap` against the floor's stated bar, graded per instance rather than in aggregate so the report names the files. A suppression with a reason is a `decision` and is left alone.
- **Coverage under-reach.** Where the invocation's glob does not reach every script file in the inventory, that is a `wiring` finding: the linter runs, and not over the code. This is the most common real defect in this language and the least visible, because the job is green.
- **Dialect declared twice, differently.** A `#!/bin/sh` script linted by an invocation that passes `-s bash`, or a `.shellcheckrc` setting `shell=bash` over a tree of `sh` scripts, is a `conflict`: the shebang says the script must be portable and the linter has been told to allow the constructs that break that promise, so the check most worth having is the one switched off. Compare the declarations — shebang, `-s` flag, `.shellcheckrc` — and grade their disagreement. What this row does **not** do is read the script body looking for bash-only syntax: that is a finding about the code, which `shellcheck` itself reports once it is pointed at the right dialect, and this skill audits whether the tooling is set up rather than what it would say.
- **Tools taken from whatever the runner ships.** `shellcheck` is preinstalled on the common hosted runners, which is why this floor is cheap to adopt and also why its version is the image's. That is a `floating` finding like any other: the image updates, a new check fires, and a pull request goes red without touching a script. `shfmt` is the opposite problem on the same runners — absent, so a job that assumes it fails outright — and since closing that gap means an install step anyway, pinning both costs nothing and is what the scaffold prescribes.
- **Size.** A script well past a few hundred lines, with subcommands and structured output, has outgrown the language. Report it as an observation, never a finding — rewriting a working script is a decision far above a tooling audit, and the floor's own position is that no amount of linting fixes the size problem.

## Scaffold

Templates: `references/scaffold-templates.md` in this directory.

Both scaffold rules specific to shell are about scope rather than content, and they apply to the linter and the formatter alike: **a scaffolded policy covers every path the inventory collects**. The CI step's file list is scaffolded from the inventory the scan produced, not from a glob. A `*.sh` glob is what produced the coverage gap in the first place, and prescribing it again closes the finding on paper while leaving the hooks unlinted. The formatter's configuration is held to the same rule: a section keyed to one of the two extensions the inventory collects leaves the rest on the tool's defaults, which is the same split policy arriving by a different route.
