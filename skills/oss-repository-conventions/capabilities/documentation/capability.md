---
name: documentation
description: >
  Scans, audits, and scaffolds a repository's documentation surface — the README
  (what-it-is / install / usage / status badges), a docs site for non-trivial
  projects, architecture decision records, runnable examples, and agent-
  instruction files (AGENTS.md, CLAUDE.md, .github/copilot-instructions.md).
  Audit treats a missing or skeletal README as a must and flags absent usage
  examples; scaffold writes a README skeleton, an AGENTS.md, and an ADR template.
  Triggers on "improve the README", "set up docs", "add examples", "record an
  architecture decision", "set up agent instructions", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# documentation capability

Governs whether someone can understand and use the project: is the README sufficient, are there examples, and — for non-trivial projects — a docs site and recorded decisions. Reads and judges by default; writes documentation scaffolds only on confirmation.

## Modes

- **scan** — report the documentation surface present.
- **audit** — judge it against `../../references/oss-health-rubric.md`.
- **scaffold** — write a README skeleton / AGENTS.md / ADR template after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Scaffold produces _structure and skeletons_, not finished prose — fill headings from the repo's reality and leave clearly-marked placeholders for the maintainer's words.
- Detect project type (library / CLI / app / service) so the README and examples fit.
- An existing substantial README → audit and suggest gaps; don't replace without a diff.

## Scan

Sources (catalog: `../../references/convention-files.md`, Documentation + Agent sections), citing each:

1. README: `README.md` / `.rst` — sections present (description, install, usage, configuration, license link), status badges.
2. Docs site: `docs/`, `mkdocs.yml`, `docusaurus.config.js`, Sphinx `conf.py`, `book.toml`.
3. Decisions: ADRs under `docs/adr/` / `docs/decisions/`.
4. Examples: an `examples/` tree or runnable snippets in the README.
5. Agent-instruction files: `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.github/instructions/`, `.cursor/rules/`.
6. Citation: `CITATION.cff` at repo root (GitHub renders a "Cite this repository" button from it).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `readme-present` — **must**. Fail when there's no README. It's the first and often only thing a visitor reads; without it the project is unusable to newcomers.
- `readme-complete` — **should**. Fail when the README lacks what-it-is, install, or usage. A title-only README doesn't let anyone adopt the project.
- `examples-present` — **could** (→ **should** for libraries). Pass when runnable usage examples exist. Examples are how most people learn an API.
- `agent-instructions` — **could**. Pass when agent-instruction files exist (house style: `AGENTS.md` canonical, `CLAUDE.md` / `.github/copilot-instructions.md` as pointers). Sets the repo up for agent contributors.
- `docs-site` — **could** (non-trivial projects). Pass when a docs site exists beyond the README. Scales documentation past one file.
- `adrs` — **could** (non-trivial projects). Pass when significant decisions are recorded. Preserves the "why" behind the architecture.
- `citation-cff` — **could** (→ **should** for academic / citable software). Pass when a valid `CITATION.cff` exists, giving users a correct, machine-readable citation (GitHub surfaces a "Cite this repository" button).

## Scaffold

Templates live in `references/scaffold-templates.md` (README skeleton, AGENTS.md, ADR). Write after confirmation, tailored to the project type:

- **README** — fill the structure from the repo (name, real install/usage commands, license link); leave prose placeholders, don't invent feature claims.
- **AGENTS.md** — house style canonical agent-instruction file; point `CLAUDE.md` / `.github/copilot-instructions.md` at it rather than duplicating.
- **ADR** — seed `docs/adr/0001-record-architecture-decisions.md` and a template for future entries.

## Output

Report per `../../references/output-format.md`: scan emits the documentation inventory (README sections, docs site, examples, agent files) with sources; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **Library vs app** — examples and API docs weigh more for a library; a service may need runbooks instead.
- **Monorepo** — a root README plus per-package READMEs is normal; flag packages with none.
- **Existing rich docs** — audit for gaps (e.g. missing usage) rather than proposing wholesale rewrites.
- **Generated docs** — note when API docs are generated so they aren't hand-edited.

## Anti-patterns

- Don't write finished prose or invent feature claims — scaffold structure with placeholders.
- Don't duplicate agent instructions across files — one canonical source, the rest point to it.
- Don't replace a substantial README without a diff.
- Don't conflate this with the change-narration domain — it shapes repo docs, not commit/PR/release prose.
