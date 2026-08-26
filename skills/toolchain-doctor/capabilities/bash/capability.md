---
name: bash
description: >
  Examines a repository's shell tooling and prescribes what is missing — finds
  the shell scripts other audits miss (hooks, bin directories, extensionless
  files with a shell shebang, CI run blocks), reads .shellcheckrc, .editorconfig,
  and shfmt flags, establishes whether anything lints them, grades the distance
  to the bash floor (shellcheck gating on warnings, not errors alone; shfmt for
  format), and
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
| `*.bats` | Bats tests are shell and are routinely left out of a shell audit, because a test suite reads as somebody else's concern. They also carry no shebang — the runner supplies the interpreter — so a scan looking for one skips them twice over |
| Extensionless files with a shell shebang | `bin/deploy`, `scripts/release` — invisible to an extension glob, and usually the most consequential scripts in the repository |
| `.githooks/`, `.husky/` | Hook scripts, routinely unlinted. They belong in the inventory whether or not anything activates them — an unlinted script is unlinted either way — but do not assume they run: both need wiring the repository may or may not carry. A husky hook is ordinarily written without a shebang because husky runs it with `sh`, so it is collected on that evidence; `.husky/_/` is husky's own generated wrapper and is not the repository's code. A `.githooks/` file without a shebang is a different case: nothing here establishes what interprets it, so it is reported with its interpreter unestablished rather than classified |
| CI `run:` blocks | Multi-line `run:` in a workflow is a shell script living in YAML — when the step's shell is a shell. A `shell:` key can select `pwsh`, `python`, or something else entirely, and the default is not the same on every runner image |
| `Makefile` recipes | Each recipe line is shell, with its own quoting hazards and its own tab-sensitivity — when `SHELL` names a shell, or is unset on a Unix build. An unset `SHELL` is not portable proof: GNU Make runs recipes through `COMSPEC` on Windows, so a Windows-only makefile runs under `cmd` rather than a shell — the same trap the Dockerfile row's Windows image carries |
| Dockerfile `RUN` lines | Shell in the shell form, executed at build time, and frequently the least reviewed lines in the repository — but a `SHELL` directive can change the interpreter, the exec form is not shell at all, and a Windows base image defaults to `cmd` |

**Resolve each location's interpreter before counting it.** Every row above can hold something that is not shell, and treating the location as proof of the language produces a shell audit of a repository that writes its CI steps in PowerShell — a lane that should never have loaded, reporting findings against files it has misread. Read the `shell:` key, the makefile's `SHELL`, the Dockerfile's directive and form; where the interpreter cannot be established, leave the block out and say so rather than assuming the common case.

**Files and embedded shell close by different routes.** `shellcheck` reads a path or standard input — the sample lane in this repository lints by piping to `shellcheck -`, and `actionlint` does exactly that for a workflow's `run:` steps — so embedded shell is lintable, not beyond the tool's reach. What it is not is reachable by the setup this floor prescribes, a CI step running `shellcheck` over the inventory's script files, because that step is handed paths and a `run:` block is not one. So embedded shell is reported with its own remedy rather than folded into the file coverage: name where it lives and roughly how much there is, and prescribe the fix that brings it under the setup everything else uses — move the block into a script file — or, where it stays inline, a linter that reads it in place, `actionlint` for workflow steps. Repositories that keep a hundred lines of shell in a workflow step usually did it by accretion, and the report is how they find out.

Where the inventory finds **no script files at all** — every line of shell embedded — the shell is still in scope and still unlinted, so the `shellcheck` row is a `gap`, not `N/A`. Stage 0 routed the repository here because it has shell worth auditing; answering "not applicable" would take that back and hand a green report to a repository whose shell nothing checks. The prescription is the one the observation already carries: move the blocks into script files, at which point the standard step covers them, or adopt `actionlint` to lint the workflow steps where they are. The `shfmt` row is the one that is genuinely `N/A` here, and for a reason that does not apply to the linter: formatting a `run:` block means rewriting it inside its YAML, which no audit can prescribe as a step, so there is nothing for the repository to have failed to configure. Say that row is not applicable and why, the way the typescript lane does for a project with no TypeScript in it.

Report the inventory before the grade. A repository that lints `scripts/*.sh` and has never looked at its hooks is not partially covered — it is uncovered in the place where an error runs on every developer's machine.

The first-line check is the reliable one for the extensionless case: a file whose first line is `#!/bin/sh`, `#!/bin/bash`, `#!/usr/bin/env bash`, or a variant is shell regardless of its name. Read that first line without following a symlink, per the mode-wide path-safety rule in `../../references/modes.md`: a tracked link can point outside the checkout, so skip links by their git mode before the read, the way the scaffold's discovery does before handing a path to a linter. When reporting these, name them individually rather than as a count — a maintainer recognizes their own scripts and can tell immediately whether the list is right.

## Where the declarations live

| Tool | Config locations |
| --- | --- |
| `shellcheck` | `.shellcheckrc`, per-file `# shellcheck` directives, CLI flags in whatever invokes it |
| `shfmt` | `.editorconfig` — the sections matching the inventory's paths, not `[*.sh]` alone — or flags in the invocation; `shfmt` has no config file of its own |
| dialect | The shebang per file, plus any `shellcheck -s` flag; `sh` and `bash` are graded against different rules |

`shfmt` having no config file matters for the audit: its settings live wherever it is invoked, so establishing them means reading the CI step, the task runner, or the hook — not looking for a dotfile that will never exist. A repository with `shfmt` in CI and no `.editorconfig` is formatting to whatever flags that one call site passes, and a contributor's editor will disagree.

## What the scan reports

1. **The script inventory**, per the table above, with the hidden locations named explicitly.
2. **`shellcheck` presence and severity handling** — whether it runs, whether its findings fail anything, and at which severity threshold, read against the floor's line rather than as a free choice: the floor is that errors and warnings both gate, so a `--severity=error` or a `severity=error` in `.shellcheckrc` is a fact this row records because it drops a tier the floor requires.
3. **Suppression directives, per-file and global.** Every `# shellcheck disable=` **in the inventoried script files**, with whether each carries a reason. The scope matters: a search across the whole tree also matches documentation, fenced examples, and prose about suppressions — this skill's own reference carries one as an illustration — and reporting those as undocumented suppressions is a finding about a sentence rather than about a script. Only a directive `shellcheck` would actually apply counts. The floor asks for a one-line reason per suppression, and a bare disable is the thing this row exists to find. A suppression can also be **global** rather than per-file, and those hide from a per-file search: a `disable=` line in `.shellcheckrc`, or an `--exclude=SCXXXX` on the invocation, turns a check off for every script at once, with no site to carry the reason the floor asks for. Read both from the `shellcheck` config locations the declarations table names, because a check silenced everywhere is a wider hole than one silenced on a line.
4. **`shfmt` presence and flags** — including whether `.editorconfig` and the invocation agree.
5. **Coverage gaps** — script **files** found by the inventory that the linter's invocation does not reach; embedded shell sits outside this row, per the note above. A `shellcheck scripts/*.sh` step in a repository with hooks and a `bin/` directory covers a fraction of its shell and reports success.

## Audit specifics

- **Undocumented suppressions.** A `# shellcheck disable=SC2086` with no reason is a `wiring` finding, graded per instance rather than in aggregate so the report names the files: `shellcheck` is present and running, and one check it should apply is switched off without the reason the floor requires, so what runs cannot fail on that line. That is partial coverage, not absence — reserving `gap` for a floor row nothing satisfies keeps the report honest to the grade it cites, and a linter that runs everywhere but one silenced line is not the same state as no linter at all. A suppression with a reason is what the floor asked for, so it is neither a finding nor a grade — it is reported among the scan's facts and left alone. A **global** suppression — a `disable=` in `.shellcheckrc` or an `--exclude=` on the invocation — is the same `wiring` finding one scope wider: the check is off for every script rather than one line, and the floor's per-suppression reason has no site to live at, so grade it once against the config that carries it. Worse than a per-file bare disable, not better, because it hides from a per-file search and covers more.
- **Severity raised above the floor's line.** `shellcheck --severity=error`, or a `severity=error` in `.shellcheckrc`, gates on errors and never lets a warning fail the job — and the floor is that warnings gate as well. That is a `wiring` finding on its own axis: the linter runs, and a whole tier of what it should catch cannot fail, which is the same partial coverage as a suppressed check a severity wider. Grade it separately from whether the exit status is swallowed, because the two are independent — a job that blocks on every error it emits is still below the floor for the warnings it filtered out, and one that never blocks is below it whatever severity it selected. Only the tiers _above_ the floor are the repository's free choice: reporting `info` and `style` too is a stricter bar than the floor asks, and no finding.
- **Coverage under-reach.** Where the invocation's glob does not reach every script file in the inventory, that is a `wiring` finding: the linter runs, and not over the code. This is the most common real defect in this language and the least visible, because the job is green.
- **Dialect declared twice, differently.** A `#!/bin/sh` script linted by an invocation that passes `-s bash`, or a `.shellcheckrc` setting `shell=bash` over a tree of `sh` scripts, is a `conflict`: the shebang says the script must be portable and the linter has been told to allow the constructs that break that promise, so the check most worth having is the one switched off. Compare the declarations — shebang, `-s` flag, `.shellcheckrc` — and grade their disagreement. What this row does **not** do is read the script body looking for bash-only syntax: that is a finding about the code, which `shellcheck` itself reports once it is pointed at the right dialect, and this skill audits whether the tooling is set up rather than what it would say.
- **Tools taken from whatever the runner ships.** `shellcheck` is preinstalled on the common hosted runners, which is why this floor is cheap to adopt and also why its version is the image's. That is a `floating` finding like any other: the image updates, a new check fires, and a pull request goes red without touching a script. `shfmt` is the opposite problem on the same runners — absent, so a job that assumes it fails outright — and since closing that gap means an install step anyway, pinning both costs nothing and is what the scaffold prescribes.
- **Size.** A script well past a few hundred lines, with subcommands and structured output, has outgrown the language. Report it as an observation, never a finding — rewriting a working script is a decision far above a tooling audit, and the floor's own position is that no amount of linting fixes the size problem.

## Scaffold

Templates: `references/scaffold-templates.md` in this directory.

Both scaffold rules specific to shell are about scope rather than content, and they apply to the linter and the formatter alike: **a scaffolded policy covers every path the inventory collects**. The CI step's file list is scaffolded from the inventory the scan produced, not from a glob. A `*.sh` glob is what produced the coverage gap in the first place, and prescribing it again closes the finding on paper while leaving the hooks unlinted. The formatter's configuration is held to the same rule: a section keyed to one of the two extensions the inventory collects leaves the rest on the tool's defaults, which is the same split policy arriving by a different route.
