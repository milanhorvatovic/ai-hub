---
name: automation-baseline
description: >
  Sets up and audits an OSS repository's bare-minimum, composable automation as
  one coherent baseline across four pillars — a testing toolkit, code scanning
  (CodeQL), autonomous dependency updates (Dependabot), and automated releases
  (changelog + artifacts). It is the entry point for greenfield or leveling-up
  work: it scaffolds composable building blocks (a setup composite action, a
  thin CI caller, a CodeQL workflow) and delegates depth and the proven recipes
  to the per-pillar capabilities. Triggers on "set up CI/automation for this
  repo", "give me the automation baseline", "make automation composable", "the
  bare-minimum CI", or a full-repo audit. For deep single-domain work, use the
  pillar capability directly.
allowed-tools: Bash Read Grep Glob Write Edit
---

# automation-baseline capability

The unifying entry point for repository automation. Rather than one monolithic CI workflow, it lays down a small set of **composable building blocks** and a clear **provide/own boundary**, then defers the depth of each pillar to its own capability. Reads and judges by default; writes building blocks only on confirmation.

## Modes

- **scan** — report which baseline pillars are present and whether CI is composable.
- **audit** — judge the repo against the baseline (rolling up the pillar checks).
- **scaffold** — lay down the composable CI building blocks and point at the pillar recipes.

## The composable building-block model

Automation is assembled from small reusable units, never one big job:

- **setup** — a composite action (`.github/actions/setup/action.yml`): toolchain + dependency install, used by every job after `checkout`.
- **per-concern jobs** — `static` (lint + typecheck), `test`, `coverage` — each `checkout → setup → run`, so they run in parallel and fail independently.
- **thin caller** — `ci.yml` wires the jobs; it contains no logic of its own.
- **scale-up** — when blocks are shared across repos, promote them to reusable workflows (`on: workflow_call`) or org-level composite actions, and have each repo's `ci.yml` call them.

The monolithic `checkout → verify-lockfile → setup → lint → typecheck → test → coverage` job is the anti-pattern this replaces: split it so each concern is a reusable, independently-failing unit.

_How autonomously_ PRs then move to merge is a separate dimension — the autonomy ladder (auto-approve → auto-merge → full flow) owned by the pr-autonomy capability. The baseline gets a repo to "CI gates every PR" (rung L1); raising the rung is a deliberate, separately-guarded step.

## Provide / own boundary

The skill provides the toolkit and wiring; the project owns its domain content.

| Pillar | Baseline this skill scaffolds | The project owns | Depth in |
| --- | --- | --- | --- |
| Testing | runner + coverage wiring, `tests/` layout, per-test-type guidance | the actual unit/integration/acceptance/E2E tests and commands | testing-quality |
| Code scanning | a CodeQL workflow (free for public repos) | query tuning / suppressions | security-policy |
| Dependencies | Dependabot config + the autonomous update→approve→merge recipe | per-ecosystem grouping preferences | dependency-supply-chain |
| Releases | tag/release + changelog & artifact generation | the release prose/highlights (change-narration domain) | release-versioning |

## Inputs & guards

- Not a git repo → stop.
- This capability orchestrates; it does not duplicate per-pillar audits. For deep single-domain work, route to the pillar capability instead.
- Detect the stack first so the building blocks fit (Node, Python, …).
- Workflow hardening (least-privilege `permissions:`, SHA-pinning, OIDC) is the ci-automation capability — scaffold the baseline here, harden there.
- Automation has **out-of-band prerequisites** the workflow YAML alone doesn't establish — bot identity, the Actions/Dependabot secret stores, gating labels, and the repo settings that let auto-merge run. They live in `../../references/automation-prerequisites.md`; this capability checks they're in place and proposes the provisioning commands (never applies), so committed automation doesn't silently no-op.

## Languages

Detect per `../../references/language-support.md`. The composable building blocks (setup action, thin caller, CodeQL) are language-agnostic; per-language specifics are delegated:

- The `setup` action installs the **detected toolchain** (via mise or a language setup action) — see the dev-setup capability.
- The `static` / `test` jobs run the project's commands — see code-style and testing-quality for the per-language tool sets.
- CodeQL covers its supported languages (C/C++, C#, Go, Java/Kotlin, JS/TS, Python, Ruby, Swift); for others (e.g. Rust), skip code scanning rather than fabricate it. Among the **compiled** CodeQL languages (Swift, Go, Java/Kotlin, C/C++) `autobuild` often fails — give them an explicit build step so CodeQL analyzes a real build; the interpreted ones (Python, JS/TS, Ruby) need none.

## Scan

Report presence across the four pillars, citing sources (catalog: `../../references/convention-files.md`):

1. CI: `.github/workflows/*` building/testing on `pull_request`; whether it's composable (composite actions / reusable workflows) or a monolith.
2. Code scanning: a CodeQL workflow (`.github/workflows/codeql*`) or `github/codeql-action` usage.
3. Dependencies: `.github/dependabot.yaml` / Renovate, plus any auto-merge/reconcile automation.
4. Releases: release automation (release-please / semantic-release) and changelog generation.
5. Prerequisites: the provisioning each present automation depends on — identity, the Actions/Dependabot secret stores, gating labels, and the auto-merge repo settings — per `../../references/automation-prerequisites.md` (`gh secret list`, `gh variable list`, `gh label list`, `allow_auto_merge`).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `ci-composable` — **could**. Pass when CI is assembled from reusable building blocks (composite actions / reusable workflows) rather than one monolithic job. Composable CI is maintainable and shareable across repos.
- `automation-prereqs-provisioned` — **should** (when any committed automation reads a secret, variable, label, or auto-merge setting). Fail when an automation references a prerequisite that doesn't exist — a secret only in the wrong store (Actions vs Dependabot), a gating label that was never created, or `allow_auto_merge` left off. Committed automation that's missing its prerequisites silently no-ops or 403s rather than failing loudly. This is the **cross-cutting** prerequisites check, owned here per `../../references/automation-prerequisites.md`; the other automation capabilities point at it rather than re-scoring it (avoid double-counting), the same way pillar checks are scored once via their owner.

Then present a **baseline-readiness roll-up** that aggregates the owning pillars' checks (cite each): testing-quality `tests-run-in-ci`, security-policy code-scanning, dependency-supply-chain `updates-automated`, release-versioning `release-automated`. In a full-repo audit, **score each of those once via its owning pillar** — this capability contributes only `ci-composable` and the cross-cutting `automation-prereqs-provisioned` to the score, to avoid double-counting.

## Scaffold

For a **"set up &lt;automation&gt;" request that spans multiple files** — not a single template — follow the matching ordered flow in `../../references/automation-playbooks.md` (CI baseline, assisted/autonomous dependency updates, CI hardening, releases, PR autonomy). Each playbook chains **detect → prerequisites → artifacts → enable → verify → rollback**, sequencing this capability's building blocks, the prerequisites runbook, and the owning pillar's templates so steps land in the right order (prerequisites before the artifacts that depend on them). This capability is the entry point for that guided setup; it still proposes settings and writes files one-confirmation-at-a-time.

Building blocks live in `references/building-blocks.md` (setup composite action, thin `ci.yml` caller with `static`/`test`/`coverage` jobs, CodeQL workflow) — these are the artifacts for the CI-baseline flow. Write after confirmation, tailored to the stack. Then point the maintainer at the pillar recipes for the rest of the baseline:

- Dependencies: the autonomous recipe in the dependency-supply-chain capability.
- Releases: the changelog + artifacts recipe in the release-versioning capability.
- Testing: the runner/coverage toolkit + per-test-type guidance in the testing-quality capability (the project supplies the tests).
- Hardening: pass the scaffolded workflows through the ci-automation capability (permissions, SHA-pins, OIDC).
- Merge autonomy: choose the rung (auto-approve / auto-merge / full flow) via the pr-autonomy capability, which installs the guardrails for that level.
- Prerequisites: emit the provisioning checklist from `../../references/automation-prerequisites.md` (bot identity, secret stores, gating labels, repo settings) as proposed commands — one surface at a time — so the scaffolded workflows actually run.

## Output

Report per `../../references/output-format.md`: scan emits the four-pillar presence map + composability; audit emits the `ci-composable` and `automation-prereqs-provisioned` findings plus the baseline-readiness roll-up (which pillars meet the baseline and which don't), with a `scaffold` offer for the gaps.

## Edge cases

- **Docs/data repo** — relax testing and the build to a docs/link-check baseline; code scanning may not apply.
- **Existing monolithic CI** — propose decomposing into building blocks incrementally; don't rewrite a working pipeline wholesale without buy-in.
- **Non-GitHub CI** (GitLab, etc.) — the building-block model still applies; translate the templates rather than assuming Actions.
- **Polyglot/monorepo** — building blocks parameterize per package; a single global block may under-fit.

## Anti-patterns

- Don't scaffold a monolithic CI job — emit composable building blocks.
- Don't duplicate the per-pillar audits or recipes — orchestrate and reference them.
- Don't write the project's tests, harden workflows, or author release prose here — those belong to testing-quality, ci-automation, and the change-narration domain respectively.
- Don't double-score pillar checks in the aggregate — they belong to their owning pillar.
