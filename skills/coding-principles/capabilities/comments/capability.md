---
name: coding-principles-comments
description: >
  Cross-language comments capability of the coding-principles skill, loaded
  within tasks the parent router already covers (it never widens the skill's
  own trigger rules): when the task touches any comment-bearing file —
  source, config, workflow, infra, shell, migration, test, or markdown —
  when a plan document mentions comments, docstrings, or annotations, or
  just-in-time when about to write any comment. Carries the comment-value rubric behind principle 21
  (clear, direct, meaningful), the value → content decision gates composed
  with principle 7, docstring policy with per-toolchain convention detection,
  the AI-narration marker policy with its override clause, and per-file-type
  quick rules backed by deep references. Review mode inverts the same rubric.
allowed-tools: Read Grep
---

# Comments capability

Single source of truth for _when, what, and how_ to comment, across every file type a coding task touches. It operationalizes principle 21 (value gate) and principle 7 (content gate) as ordered checks on each comment about to be written or modified — full principle prose in `../../references/principles.md`.

> **Deep references** — per-format rules with worked examples and the multi-line comment forms live in `references/by-file-type.md`; catalogued symptoms in `references/anti-patterns.md`; industry anchors (Ousterhout, Atwood, docstring style guides) in `references/best-practices.md`. Load them as the work calls for them; this file alone covers routine authoring.

## When to use this capability

Three trigger tiers — all scoped to tasks the parent router has already triggered; this capability never overrides the skill's docs-only / config-only skip:

1. **Default load** — the task writes or edits a comment-bearing file (list below).
2. **Planning extension** — the task authors a plan document, ADR, or work spec that mentions comments, docstrings, or annotations; the rubric shapes what the plan promises before any code exists.
3. **Just-in-time** — the router's "while editing" checklist fires: you are about to write any comment at all.

Comment-bearing files:

```
.py .pyi .ts .tsx .mts .cts .js .jsx .mjs .cjs .rs .go .rb .erb .java .kt .swift .scala
.c .cc .cpp .cxx .h .hpp .hxx .m .mm .cs .fs .clj .cljs .ex .exs .elm .ml .mli .hs
.sh .bash .zsh .fish .ksh .ps1
.yaml .yml .toml .ini .conf .properties .env .json5 .jsonc
.tf .tfvars .hcl .nix .pkr.hcl
.ipynb
Dockerfile Containerfile docker-compose*.yml compose*.yml
Makefile *.mk justfile Taskfile.yml
.gitlab-ci.yml .github/workflows/*.{yml,yaml} .circleci/config.yml .drone.yml
.md .mdx .rst .adoc
```

Pure `.json` is excluded: the format has no native comment syntax, so there is nothing to govern — N/A, not a violation.

Out of scope: commit messages, PR descriptions, branch names, and release notes are change narration, a different concern this skill is silent on (see the parent SKILL.md scope boundaries).

## Precedence

The rubric below is the default, not an absolute. Defer, in order:

1. Project agent-instruction files (`CLAUDE.md`, `AGENTS.md`) — their declared comment conventions win outright.
2. Project contributor docs (`CONTRIBUTING.md`).
3. Toolchain config (pydocstyle / interrogate / ESLint jsdoc rules / rustdoc lints — detection table below).
4. This capability's default: the value bar, why-not-what, no AI-narration markers.

A stricter or looser rule at any higher layer replaces the default. The same chain governs docstring policy and the AI-marker policy.

## The comment-value rubric

A comment meets the bar when it is **clear** (understandable without the diff, review thread, or session that produced it), **direct** (says the thing plainly, in as few words as carry it), and **meaningful** — it adds information the code cannot express:

- **Hidden invariant** the type system cannot state.
- **Surprising behavior** a careful reader would not predict.
- **Intentional deviation** from convention, with the rationale stated.
- **Non-obvious workaround** with a durable anchor (CVE, upstream bug ID, vendor doc URL, RFC).
- **Security-critical assumption** — e.g. "caller has already validated X; do not re-check".
- **Performance-critical decision** backed by profiler evidence.

One category is enough; a comment does not need two reasons to live. The rubric guides, it does not ban: a comment failing the bar is revised into one that carries meaning, or removed when there is none to carry — never reflex-deleted when a rewrite would save the load-bearing part.

**Durable anchors only.** An anchor must be followable a year later: issue-tracker URLs, ADR file paths, `CONTRIBUTING.md` section anchors, stable wiki pages qualify; Slack permalinks, chat messages, screenshots, and "discussed in standup" do not. Anchoring a _persistent external constraint_ ("works around CPython gh-101234") is not the change narration principle 7 forbids ("added for #123", "fix for the X flow") — the first documents the code as it is, the second narrates how it got there and belongs in the commit message.

## Decision tree

1. If the text is change narration — it references this PR, ticket, session, or reviewer — move the content to the commit message; do not write the comment.
2. If it is an AI-narration marker → delete before commit (marker policy below; check its override clause first).
3. **Value gate (principle 21):** if it carries none of the six meaning categories → revise until it does, or remove it.
4. **Content gate (principle 7):** if it carries value but spends words restating the _what_ → cut to the _why_; the code already says the what.
5. **Clarity check:** if a reader without this session's context would not understand it as written, or it hedges → rewrite plainly, in as few words as carry it.
6. If it is a multi-line block mixing load-bearing content with noise → apply the partial-failure rule below.
7. If it is still standing, it earned its place. Write it and move on.

## Multi-line comments: partial failure

When a docstring or block comment mixes useful content (one invariant, one anchored workaround) with restated-signature prose or narration: extract the load-bearing item, rewrite as the smallest comment that carries it, delete the rest. Do not delete the whole block because most of it is noise; do not keep the whole block because part of it is fine. The comment forms this covers per language are listed in `references/by-file-type.md`.

## Docstring policy

Defer to the project's declared convention first. Signals that a project demands docstrings:

| Language | Signals |
| --- | --- |
| Python | `pyproject.toml` `[tool.pydocstyle]` / `[tool.interrogate]` / `[tool.ruff.lint.pydocstyle]` (D-rules); `setup.cfg [pydocstyle]`; `.pydocstyle`; `tox.ini [pydocstyle]`; darglint config |
| TypeScript / JavaScript | `.eslintrc*` with `eslint-plugin-jsdoc` / `eslint-plugin-tsdoc`; `typedoc.json`; `tsconfig.json` `"declaration": true` (weak — exported-API docs likely welcome, not required) |
| Rust | `Cargo.toml [lints]` `missing_docs`; `#![deny(missing_docs)]` / `#![warn(missing_docs)]` in `lib.rs` |
| Go | `.golangci.yml` with revive's `exported` rule; staticcheck `ST1000`, `ST1020`–`ST1022` |
| Ruby | `.rubocop.yml` `Style/Documentation` |
| Java | `checkstyle.xml` `JavadocMethod`; `maven-javadoc-plugin` |
| C# / .NET | `.editorconfig` `dotnet_diagnostic.SA1600`; `<GenerateDocumentationFile>true</GenerateDocumentationFile>` |
| Cross-language | `docs/` with sphinx `conf.py` / `mkdocs.yml` / typedoc config; `.readthedocs.yaml`; explicit expectations in `CONTRIBUTING.md` / agent-instruction files |

An enforcing signal — a lint rule (pydocstyle / jsdoc rules / `missing_docs` / `Style/Documentation` / `SA1600`) — means the project demands docstrings: follow its convention and style. A tooling-presence signal (typedoc, sphinx / mkdocs, `declaration: true`) indicates the public surface is expected to be documented, not a mandate: favor docstrings on exported API and judge the rest by the value bar. No signal → the value bar decides case by case: write a docstring where it carries contract, invariants, or surprises the signature cannot; never restate the signature; trivial private helpers under ~5 lines usually need none.

## AI-narration markers

**Override clause first.** The ban below is a default repo-policy stance, not an imposed rule. When a project's agent-instruction files or `CONTRIBUTING.md` mandate AI attribution, or a legal/compliance regime requires AI disclosure, or a community project explicitly wants transparency markers — that declaration wins.

Absent an override:

- **Banned — agent-authored narration.** `# Generated by AI`, `# Claude added`, `// copilot suggested`, `# AI-generated`, `# placeholder — replace later`, `# TODO: human review`, `// FIXME: AI` — any comment existing primarily to attribute or apologize for an agent's authorship. Delete before commit; authorship context belongs in the commit message, never in tree.
- **Allowed — machine-codegen banners.** `// Code generated by protoc. DO NOT EDIT.`, `// @generated`, `# AUTO-GENERATED FILE — DO NOT MODIFY`. These mark deterministic, regenerable tool output; AI-narration markers are contextual and agent-authored. The distinction is regenerability, not wording.
- **Allowed with rationale — mechanical suppressions.** `# noqa: E501`, `// eslint-disable-next-line`, `# type: ignore[arg-type]`, `// @ts-expect-error`, `# pylint: disable=…`. Bare directive → _should_-level smell; with a reason (`# noqa: E501  # URL too long to break`) → earned.
- **Hybrid forms split.** `# noqa  # claude said it's fine` → keep the directive with a real rationale, strip the narration.

The ban applies to comment-position text only — `password = "placeholder"` as a string literal is code, not commentary.

## Per-file-type quick rules

Deep rules with worked examples: `references/by-file-type.md`. The one-line versions:

- **Source code** — the rubric as written; docstrings per the policy above.
- **Configs** (YAML/TOML/INI/.env) — comment the surprising values: magic numbers, unit traps, deviations from defaults. Self-describing keys carry themselves.
- **Workflows** (CI pipelines) — name steps well instead of narrating them; comment only non-obvious ordering constraints, workarounds, pinned-version rationale.
- **Infra** (Dockerfile, Terraform, k8s) — comment cross-resource invariants and ordering constraints, not what each directive does.
- **Shell** — comment the non-obvious flag, trap, or portability constraint; not each pipeline stage.
- **Migrations** — state the irreversible step and the invariant the data must hold; skip narrating DDL.
- **Tests** — test names carry intent; no arrange/act/assert dividers; explain mock or fixture shape only when the _why_ is non-obvious.
- **Markdown** — two flavors: _documentary_ snippets (teaching) may carry didactic comments — the comment is the why; _copy-paste executable_ snippets are treated as a standalone file of that language, full rubric. AI markers, restating prose, and bare TODOs stay banned in both.

## Review-mode mirror

The same rubric inverted is a finding source for review tasks: a comment failing the value gate anchors to principle 21 (_should_), a value-passing comment failing the content gate anchors to principle 7 (_could_). Phrase and triage findings per the parent skill's review capability; this file only supplies the anchors and the rubric.

## Scope: new comments, not archaeology

This capability governs new authoring and modifications. Existing comments are in scope only when they sit inside the current change (same diff hunk, within ±3 lines of changed lines), when the user or a repo instruction file explicitly asks for a comment audit, or when a project mandate declares a stricter sweep. Default scope is the smallest viable — matching principle 1.

## Anti-patterns in applying this capability

- **Over-deletion.** Stripping comments that pass the bar is a worse failure than leaving a weak one — the rubric protects good comments as much as it removes noise.
- **Justification bloat.** Do not replace a failing comment with a longer comment defending itself. Revise toward fewer, denser words or remove.
- **Surface creep.** Do not apply this rubric to commit messages or PR text; that is change narration with its own rules.
- **Two-reason gold-plating.** One meaning category suffices; do not demand more.
- **Archaeology.** Do not rewrite untouched comments beyond the adjacency rule above.

## Edge cases

- **Generated code** — the rubric applies to the generator, not its output (parent skill edge case).
- **Legal / license / SPDX headers** — always allowed where file or project convention requires them.
- **Schema-doc comments consumed by tooling** — OpenAPI / JSON Schema annotations that tooling renders are API documentation, not commentary; keep them.
- **Descriptive values are not comments.** YAML `description:` strings and similar are data; only syntactic comments (`#`, `//`, `<!-- -->`, docstrings, `--`) are governed here.
- **Notebooks (`.ipynb`)** — code cells follow their language's rules, markdown cells the markdown rules, raw cells the format they hold.
