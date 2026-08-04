---
name: contributing
description: >
  Scans, audits, and scaffolds a repository's contribution on-ramp — the
  CONTRIBUTING guide, the developer-certificate-of-origin (DCO) or CLA and
  sign-off policy, dev-environment setup pointers, the PR/review process, and
  newcomer affordances like good-first-issue labels. Audit flags a missing or
  thin CONTRIBUTING and an undocumented sign-off requirement; scaffold writes a
  CONTRIBUTING.md tailored to the repo's actual setup and test commands.
  Triggers on "add a contributing guide", "how do people contribute", "do we
  require sign-off / a CLA", "onboarding for contributors", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# contributing capability

Governs how a newcomer goes from interested to merged: is the process written down, is the legal contribution basis (DCO/CLA) clear, and can someone get a dev environment running. Reads and judges by default; writes `CONTRIBUTING.md` only on confirmation.

## Modes

- **scan** — report the contribution files and policies present.
- **audit** — judge the on-ramp against `../../references/oss-health-rubric.md`.
- **scaffold** — write `CONTRIBUTING.md` after confirmation, tailored to the repo.

## Inputs & guards

- Not a git repo → stop.
- A substantive `CONTRIBUTING` already exists and the user asked to scan/audit → report it; propose edits only when asked.
- DCO vs CLA is a maintainer policy decision — never assert one; detect what's configured and, for scaffold, ask which the repo uses.

## Scan

Sources (catalog: `../../references/convention-files.md`), citing each:

1. Guide: `CONTRIBUTING.md` / `.rst` / `.txt` at root, `docs/`, or `.github/`.
2. Legal basis: a DCO bot (`.github/workflows/*dco*`, the DCO app), `Signed-off-by` trailers in `git log`, or a CLA (`.github/workflows/*cla*`, a CLA-assistant config).
3. Setup pointers: does the guide reference the real dev setup (deep coverage lives in the dev-setup capability) and the real test command.
4. Newcomer affordances: `good first issue` / `help wanted` labels via `gh label list` when `gh` is available.
5. Commit convention: a `.commitlintrc*` / `commitlint.config.*` / `.czrc` / commitizen config, or a convention stated in the guide (e.g. Conventional Commits).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `contributing-present` — **should** · scorecard: Contributors. Fail when there's no `CONTRIBUTING`. Without it, contributors guess the process and PRs arrive in the wrong shape.
- `setup-and-test-documented` — **should**. Fail when the guide doesn't say how to install deps and run tests (or the commands it lists don't match the repo). A contributor can't verify their change otherwise.
- `contribution-basis-clear` — **should**. Fail when sign-off/DCO or a CLA is enforced in CI but undocumented, or claimed in docs but unenforced. Contributors must know the legal terms up front.
- `pr-process-documented` — **could**. Pass when the guide explains branch/PR expectations and review flow. Sets expectations and reduces churn.
- `newcomer-labels` — **could**. Pass when `good first issue` / `help wanted` labels exist. Lowers the barrier to a first contribution.
- `commit-convention-declared` — **could**. Pass when the repo declares a commit-message convention (e.g. Conventional Commits via commitlint/commitizen, or stated in CONTRIBUTING). Report only what's declared — authoring or validating individual commit messages is the change-narration domain and out of scope here.

## Scaffold

`CONTRIBUTING.md` — write after confirmation from `references/scaffold-templates.md`. Fill it from the repo's reality, not placeholders: the actual setup steps (defer detail to the dev-setup capability), the actual test command, and the maintainer's chosen contribution basis (ask DCO vs CLA vs neither). House style keeps `CONTRIBUTING.md` at repo root.

If the repo enforces sign-off, document the `git commit -s` requirement and what `Signed-off-by` attests (the DCO) — but never add sign-off trailers to anyone's commits here; that's a change-narration concern.

## Output

Report per `../../references/output-format.md`: scan emits the on-ramp inventory with sources; audit emits severity-tagged findings, the domain score, and a `scaffold` offer for each unmet `should`.

## Edge cases

- **Org-level `.github`** — a contributing guide may live in the org's `.github` repo and apply fleet-wide; detect and don't duplicate.
- **Monorepo** — note per-package contribution differences; the root guide covers the common path.
- **Docs-only / personal repo** — relax `setup-and-test-documented` when there's nothing to build or test.

## Anti-patterns

- Don't choose DCO vs CLA for the maintainer — detect and ask.
- Don't add `Signed-off-by` or any trailer to commits — only document the policy.
- Don't write a guide whose setup/test commands you didn't verify against the repo.
- Don't overwrite an existing `CONTRIBUTING` without showing a diff.
