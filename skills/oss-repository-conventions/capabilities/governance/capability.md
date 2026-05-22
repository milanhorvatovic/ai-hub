---
name: governance
description: >
  Scans, audits, and scaffolds how a repository is owned and governed — the
  CODEOWNERS review-routing map, who the maintainers are (MAINTAINERS / OWNERS /
  AUTHORS), and the decision-making process (GOVERNANCE). Audit flags missing or
  invalid CODEOWNERS and, for multi-maintainer projects, an undocumented
  decision model; scaffold writes CODEOWNERS, MAINTAINERS, and GOVERNANCE
  tailored to the repo. Triggers on "who owns this code", "set up CODEOWNERS",
  "who are the maintainers", "how are decisions made", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# governance capability

Governs ownership and decision-making: are reviews routed to the right people, is it clear who maintains the project, and — as it grows — how decisions get made. Reads and judges by default; writes governance files only on confirmation.

## Modes

- **scan** — report the ownership and governance files present.
- **audit** — judge them against `../../references/oss-health-rubric.md`.
- **scaffold** — write CODEOWNERS / MAINTAINERS / GOVERNANCE after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Owners/maintainers are real people or teams — never invent handles. For scaffold, derive candidates from `git shortlog -sne` and confirm with the maintainer.
- Solo/personal repo → governance and a decision model are `could`, not `should`; don't push process a one-person project doesn't need.

## Scan

Sources (catalog: `../../references/convention-files.md`), citing each:

1. Review routing: `.github/CODEOWNERS`, `CODEOWNERS`, or `docs/CODEOWNERS`.
2. Maintainers: `MAINTAINERS` / `MAINTAINERS.md`, `OWNERS`, `AUTHORS`, `CONTRIBUTORS`.
3. Decision model: `GOVERNANCE.md`.
4. Reality check: `git shortlog -sne | head` for the de-facto maintainer set, to compare against what's declared.

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `codeowners-present` — **should** (→ **could** for solo repos). Fail when there's no CODEOWNERS on a multi-contributor repo. Without it, review assignment is ad hoc and gaps go unreviewed.
- `codeowners-valid` — **should** (when CODEOWNERS exists). Fail on syntax errors, patterns matching nothing, or owners that don't exist/lack access. An invalid CODEOWNERS silently stops routing reviews.
- `maintainers-listed` — **could**. Pass when MAINTAINERS/OWNERS (or GOVERNANCE) names who is responsible. Matters as the project outgrows a single author.
- `governance-documented` — **could** (→ **should** for multi-maintainer projects). Pass when the decision/escalation process is written down. Prevents stalls and disputes once more than one maintainer is involved.

Validate CODEOWNERS with `gh api repos/{owner}/{repo}/codeowners/errors` when `gh` is available; otherwise do a static syntax/glob check.

## Scaffold

Templates live in `references/scaffold-templates.md` (CODEOWNERS, MAINTAINERS, GOVERNANCE). Write after confirmation, one file at a time:

- **CODEOWNERS** — derive ownership from the directory structure and the de-facto owners (`git shortlog`); confirm handles/teams. House style: `.github/CODEOWNERS`.
- **MAINTAINERS** — list current maintainers with contact and area; confirm the set.
- **GOVERNANCE** — only when the maintainer wants a written model; pick a lightweight model (BDFL / maintainer-council / consensus) and fill it in.

## Output

Report per `../../references/output-format.md`: scan emits the ownership inventory and the declared-vs-actual maintainer comparison; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **Solo repo** — relax CODEOWNERS/governance to `could`; still note that a single point of failure exists.
- **Org `.github` defaults** — org-level CODEOWNERS/governance may apply; detect and don't duplicate.
- **Monorepo** — CODEOWNERS should be path-scoped per area; a single root owner is a smell to flag.
- **Stale maintainers** — if declared maintainers no longer appear in recent history, flag the drift rather than rewriting silently.

## Anti-patterns

- Don't invent owner handles or teams — derive and confirm.
- Don't claim CODEOWNERS is valid without checking it resolves (gh codeowners/errors or a static check).
- Don't impose a heavyweight governance model on a solo or tiny project.
- Don't overwrite ownership files without confirmation and a diff.
