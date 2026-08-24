# Mode contracts

Three modes, one contract each. A capability names which stages it runs and what it reads; it never redefines what a mode is allowed to do.

## Stage 0 — language detection (whole-repo runs only)

When the request names a language, skip this: route to that capability and scan only its sources. When the request names none — "audit this repo's tooling" — establish which languages the repository actually contains before loading anything, and report which capabilities ran.

Detection is manifest-first, extension-second, because a manifest is a declaration and an extension is a guess:

| Language | Manifest evidence | Extension evidence |
| --- | --- | --- |
| python | `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements*.txt`, `Pipfile` | `*.py` |
| typescript | `package.json`, `tsconfig*.json`, `deno.json` | `*.ts`, `*.tsx`, `*.mts`, `*.cts` |
| rust | `Cargo.toml` | `*.rs` |
| bash | none — shell has no manifest | `*.sh`, `*.bash`, plus extensionless files whose first line is a shell shebang |

A language with manifest evidence is present. A language with extension evidence alone is present too, and worth naming as such in the report — a repository with twelve `.py` files and no `pyproject.toml` is exactly the case where the audit has something to say. A language with neither is absent, and the report says which languages were looked for, not only which were found: a reader cannot tell "no Rust here" from "Rust was never checked" unless the report distinguishes them.

Exclude vendored and generated trees from the count — `node_modules`, `vendor`, `target`, `dist`, `build`, `.venv`, `venv`, and anything the repository's own ignore file excludes. A repository is not a Rust project because a dependency vendored one.

## scan — what is declared, and does it run

Read-only. Produces facts, never judgments.

1. **Locate the declarations.** Each capability lists the files that can carry its language's tooling config, in precedence order. Read them; do not infer from the presence of a tool's cache directory or lockfile alone, and never probe the machine for an installed binary — an installed tool the repo does not declare is not the repo's tooling.
2. **Record what each declares.** Tool, the file it was found in, and the settings that matter to the floor — not a dump of every option.
3. **Establish CI wiring separately.** Per `ci-detection.md`. Configuration and execution are two facts and are reported as two facts.
4. **Report absences as absences.** A floor tool with no declaration is reported `(not declared)`, and a declaration the scan could not resolve is `(unknown — <reason>)`. Never let a tool the scan failed to reach appear identical to a tool the repository does not use.

Every reported fact cites the file it came from, with a line number where the file is long enough that the citation would otherwise be a scavenger hunt.

## audit — how far from the floor

Read-only. Consumes the scan's facts and grades them against `tooling-floors.md` using the vocabulary in `diagnosis-grading.md`.

1. **Grade each floor row** for the language: satisfied, gap, or unknown, and where a row is satisfied by a non-floor tool the repo has chosen deliberately, say so and grade it satisfied.
2. **Grade the wiring** — a declared tool CI never runs is its own finding, and typically the most valuable one in the report.
3. **Grade the internal contradictions** — two tools claiming one job, a version pinned in one file and floated in another, a config disabling the rule its own CI step exists to enforce.
4. **Name the prescription with each finding.** A finding without a concrete next step is an observation; this skill's whole purpose is the next step.
5. **Record the opt-outs.** A repository that declared its way out of a floor row gets that recorded as a decision, not re-litigated.

The audit never blocks anything and never speaks as though it could. See `diagnosis-grading.md` for why every grade here is advisory and what that costs when a finding is genuinely serious.

## scaffold — write the fix

The only mode that writes, and it writes one file per confirmation.

1. **Trace to a finding.** Every scaffolded file closes a specific audit finding. A scaffold with no finding behind it is the skill deciding what the repository should want, which is the failure mode the consent model exists to prevent.
2. **Draft from the capability's own scaffold templates** — each language capability carries them beside its capability file — filled in against what the scan found: the repository's declared language version, its existing tool choices, its CI shape.
3. **Show the whole file, then ask.** Full content, its path, and — when the path exists — a diff of what changing it would lose. One confirmation, one file. Never a batch, never a silent overwrite.
4. **Never install, and never imply an install happened.** The output is a file plus, where relevant, the command the user runs to make the tool available. That command is shown for the user to run; the skill does not run it.
5. **Re-audit after.** A scaffolded repository should audit clean on the rows the scaffold addressed. When it does not, the prescription disagreed with the diagnosis, and the diagnosis is the one to trust.

Scaffolded configs inherit rather than impose: the repository's declared language version, its indentation, its existing lint rule set where one exists. A scaffold that raises a project's minimum language version as a side effect has changed something nobody asked it to change.
