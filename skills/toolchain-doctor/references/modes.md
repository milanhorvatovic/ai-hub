# Mode contracts

Three modes, one contract each. A capability names which stages it runs and what it reads; it never redefines what a mode is allowed to do.

## Stage 0 — language detection (whole-repo runs only)

When the request names a language, skip this: route to that capability and scan only its sources. When the request names none — "audit this repo's tooling" — establish which languages the repository actually contains before loading anything, and report which capabilities ran.

Detection is manifest-first, extension-second, because a manifest is a declaration and an extension is a guess:

| Language | Manifest evidence | Extension evidence |
| --- | --- | --- |
| python | `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt`, `Pipfile` | `*.py` |
| typescript | `package.json`, `tsconfig*.json` | `*.ts`, `*.tsx`, `*.mts`, `*.cts`, and the JavaScript forms `*.js`, `*.jsx`, `*.mjs`, `*.cjs` |
| rust | `Cargo.toml` | `*.rs` |
| bash | none — shell has no manifest | `*.sh`, `*.bash`, `*.bats`, extensionless files whose first line is a shell shebang, tracked `.husky/` hooks other than the generated `.husky/_/` wrappers — husky supplies the interpreter, so its hooks carry neither shebang nor extension and an evidence rule reading only those two would skip a repository whose shell is all hooks — and embedded shell **whose interpreter resolves to a shell**: a multi-line `run:` block whose step does not select another shell, a `Makefile` recipe where `SHELL` has not been reassigned, a Dockerfile `RUN` in shell form on an image whose default is one |

The JavaScript extensions sit on the typescript row because that lane covers both. Leaving them off would report a JavaScript-only repository with no manifest as containing no language this skill knows, which is the one repository shape most likely to have no tooling at all. Routing them there carries an obligation, though: the rows that are TypeScript's alone — `strict`, the compiler as a typecheck — do not apply to a project with no TypeScript in it, and grading them would hand a working JavaScript repository two `gap` findings for not being a different language. Mark those rows `N/A` and say why; the lint and format rows apply unchanged.

**Deno is out of scope, and detection says so rather than guessing.** A `deno.json` or `deno.jsonc` — both are standard, and recognizing only the first sends an ordinary Deno project down the extension rule into the wrong lane — is a signal this skill recognizes and refuses: Deno ships its own checker, linter, and formatter, none of which the typescript lane's floor or declaration scan knows, so routing a Deno project there would produce a page of `gap` findings against a toolchain that is complete and built in. Report it as a language present and unsupported, per the router's degrade rule, rather than auditing it against the wrong floor.

The refusal covers the project the file governs, not the repository that contains it. A monorepo with one Deno package beside several ordinary ones is a shape this skill can audit almost all of, and treating a `deno.json` anywhere as a repository-wide answer would leave the Node packages unexamined for a reason that has nothing to do with them — a whole tree skipped by a file in a sibling directory. Resolve each project from its own manifest, refuse the Deno-rooted ones by name, and route the rest. Say which were skipped and which were audited, so the report is not read as covering everything it found.

`*.bats` is on that row because Bats test files carry no shebang — the runner supplies the interpreter — so a repository whose only shell is its test suite would otherwise reach no lane, and both shell tools recognize the extension.

The interpreter qualifier on that row is not a detail deferred to the capability. A `run:` block can select `pwsh` or `python`, a makefile can point `SHELL` elsewhere, and a Windows base image defaults to `cmd` — so counting the location rather than the language routes a repository with no shell at all into the shell lane, which then audits files it has misread. Resolve it here, at the point the routing decision is made, and count only what resolves to a shell.

Embedded shell is on the bash row for the same reason, and it is the case detection would otherwise miss most often: plenty of repositories contain no shell file at all and a great deal of shell, all of it inside workflow `run:` blocks and Dockerfiles. A stage-0 rule that only globs files routes that repository to no lane, and the capability built to find exactly those locations never gets loaded.

**A `package.json` is not by itself proof of a JavaScript project.** It is the one manifest that repositories in every language keep for reasons unrelated to their own source — a pinned markdown formatter, a link checker, a docs site — and treating its presence as the language would route a Python or Rust repository into the typescript lane and hand it lint, format, and compiler gaps for source it does not contain. Require corroboration: source files in the language, or manifest fields that describe a codebase rather than a toolbox (`main`, `exports`, `types`, a build script, a `tsconfig.json`). Where the only JavaScript is a handful of helper scripts serving another language's tooling, say that and move on. The repository shipping this skill is exactly that case, which is why the rule is stated rather than assumed.

**A `requirements*.txt` is the same trap in the other language**, and the rule that catches one has to catch both or it is a rule about `package.json`. A docs build pins Sphinx, a pipeline pins `pre-commit`, a Rust repository pins the linter its release job calls — none of that makes the repository Python, and routing it into the lane hands it a missing linter, a missing type checker, and an undeclared interpreter for source it does not have. Require the same corroboration: `*.py` files that are the repository's own, or manifest fields describing a codebase rather than a toolbox. `pyproject.toml` carrying only a `[tool.*]` section for another language's helper scripts is the same shape and is read the same way; a `[project]` table is a codebase and settles it.

A language with manifest evidence is present. A language with extension evidence alone is present too, and worth naming as such in the report — a repository with twelve `.py` files and no `pyproject.toml` is exactly the case where the audit has something to say. A language with neither is absent, and the report says which languages were looked for, not only which were found: a reader cannot tell "no Rust here" from "Rust was never checked" unless the report distinguishes them.

Exclude vendored and generated trees from the count — `node_modules`, `vendor`, `target`, `dist`, `build`, `.venv`, `venv`, and untracked content the repository's own ignore file excludes. A repository is not a Rust project because a dependency vendored one.

**Tracked source stays, whatever the ignore file says about it.** Ignore rules govern what git picks up next, not what a repository has already committed, and a tracked file matching one was added with `-f` by somebody who meant it. Dropping it here is worse than dropping it anywhere later, because stage 0 decides which lanes load at all: a repository whose only shell is a tracked, ignored script would never reach the capability whose inventory is written to keep it. The two rules have to agree, and this is the direction they agree in.

## scan — what is declared, and does it run

Read-only. Produces facts, never judgments.

1. **Locate the declarations.** Each capability lists the files that can carry its language's tooling config, in precedence order. Read them; do not infer from the presence of a tool's cache directory or lockfile alone, and never probe the machine for an installed binary — an installed tool the repo does not declare is not the repo's tooling.
2. **Record what each declares.** Tool, the file it was found in, and the settings that matter to the floor — not a dump of every option.
3. **Establish CI wiring separately.** Per `ci-detection.md`. Configuration and execution are two facts and are reported as two facts.
4. **Report absences as absences.** A floor tool with no declaration is reported `(not declared)`, and a declaration the scan could not resolve is `(unknown — <reason>)`. Never let a tool the scan failed to reach appear identical to a tool the repository does not use.

Every reported fact cites the file it came from, with a line number where the file is long enough that the citation would otherwise be a scavenger hunt.

## audit — how far from the floor

Read-only. Consumes the scan's facts and grades them against `tooling-floors.md` using the vocabulary in `diagnosis-grading.md`.

1. **Grade each floor row** for the language. A row either needs nothing said about it — it is satisfied, which is a state and not a grade — or it carries one of the grades `diagnosis-grading.md` defines, and the enumeration here stays open to all of them rather than naming a convenient few: `gap` where nothing satisfies it, `unknown` where detection could not reach, `decision` where the repository declined it deliberately, and the rest as they apply. An abbreviated list is how a row that deserves `decision` gets filed as satisfied. Where a row is satisfied by a non-floor tool the repo chose deliberately, say so; that is still satisfied, and the note is what keeps the report honest about how.
2. **Grade the wiring** — a declared tool CI never runs is its own finding, and typically the most valuable one in the report.
3. **Grade the version fixity** — for each tool that does run, whether anything decides which version runs. Only two things do: an **exact** pin, or a tracked lock file that resolves one. A range is not a pin — `>=0.5` and `^9` both resolve whatever matches on the day of the install, so a repository can declare a dependency, install it, and still get a different linter next week; declaring a package fixes _which_ tool runs, never _which version_ of it. A pinned container or a task runner that resolves an exact version counts, on the same test. Anything else is `floating`. Grade the tool, not the language: an interpreter or toolchain version belongs to the floor row that declares it.
4. **Grade the internal contradictions** — two tools claiming one job, a version pinned in one file and floated in another, a config disabling the rule its own CI step exists to enforce.
5. **Name the prescription with each finding.** A finding without a concrete next step is an observation; this skill's whole purpose is the next step.
6. **Record the opt-outs.** A repository that declared its way out of a floor row gets that recorded as a decision, not re-litigated.

The audit never blocks anything and never speaks as though it could. See `diagnosis-grading.md` for why every grade here is advisory and what that costs when a finding is genuinely serious.

## scaffold — write the fix

The only mode that writes, and it writes one file per confirmation.

1. **Trace to a finding.** Every scaffolded file closes a specific audit finding. A scaffold with no finding behind it is the skill deciding what the repository should want, which is the failure mode the consent model exists to prevent.
2. **Draft from the capability's own scaffold templates** — each language capability carries them beside its capability file — filled in against what the scan found: the repository's declared language version, its existing tool choices, its CI shape.
3. **Show the whole file, then ask.** Full content, its path, and — when the path exists — a diff of what changing it would lose. One confirmation, one file. Never a batch, never a silent overwrite.
4. **Never install, and never imply an install happened.** The output is a file plus, where relevant, the command the user runs to make the tool available. That command is shown for the user to run; the skill does not run it.
5. **Re-audit after.** A scaffolded repository should audit clean on the rows the scaffold addressed. When it does not, the prescription disagreed with the diagnosis, and the diagnosis is the one to trust.

Scaffolded configs inherit rather than impose: the repository's declared language version, its indentation, its existing lint rule set where one exists. A scaffold that raises a project's minimum language version as a side effect has changed something nobody asked it to change.
