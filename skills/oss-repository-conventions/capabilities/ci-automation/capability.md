---
name: ci-automation
description: >
  Scans, audits, and scaffolds a repository's CI and workflow automation —
  GitHub Actions workflows and their triggers, build/test on pull requests, the
  test matrix, least-privilege workflow token permissions, third-party action
  pinning (to a commit SHA), OIDC for deploys, concurrency and timeouts, and
  scheduled maintenance jobs. Audit flags no CI on PRs, over-privileged tokens,
  and unpinned actions; scaffold writes a CI workflow with minimal permissions
  and pinned actions. Dependency bots live in the dependency-supply-chain
  capability. Triggers on "set up CI", "harden my workflows", "pin my actions",
  "do my workflows have least privilege", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# ci-automation capability

Governs the repository's automation layer: do workflows build and test changes,
and are they configured safely (least privilege, pinned actions, OIDC). Reads
and judges by default; writes workflow files only on confirmation.

## Modes

- **scan** — report the workflows, triggers, permissions, and action pinning present.
- **audit** — judge them against `../../references/oss-health-rubric.md` and OpenSSF Scorecard.
- **scaffold** — write a CI workflow after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Workflow secrets and deploy credentials are sensitive — never echo secret values; reason about *configuration*, not contents.
- Dependency bots (Dependabot/Renovate) and lockfile/SBOM concerns are the dependency-supply-chain capability; here, cover workflow files and action pinning.
- Scaffolding a workflow that *runs* tests relies on the test config from the testing-quality capability — reference it, don't redefine the suite.

## Scan

Sources (catalog: `../../references/convention-files.md`, CI/CD section), citing each:

1. Workflows: `.github/workflows/*.yml` — names, `on:` triggers (push / pull_request / schedule / workflow_dispatch), jobs, matrix.
2. Permissions: top-level / per-job `permissions:`; default is over-privileged when unset on classic tokens.
3. Action pinning: `uses:` lines — pinned to a full commit SHA vs a moving tag/branch.
4. Auth: OIDC (`permissions: id-token: write` + cloud login actions) vs long-lived secrets for deploy/publish.
5. Hygiene: `concurrency:` cancellation, job `timeout-minutes`, reusable/`workflow_call` workflows, scheduled jobs (stale, link-check, Scorecard).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md`
(`id` — **severity** [· scorecard: Name]. criterion. why):

- `ci-on-pr` — **should** (→ **must** for code repos) · scorecard: CI-Tests. Fail when no workflow builds/tests on `pull_request`. Changes merge unverified otherwise.
- `least-privilege-token` — **should** · scorecard: Token-Permissions. Fail when workflows don't set minimal `permissions:` (read-only default, elevate per job). Over-privileged tokens widen the blast radius of a compromised action.
- `actions-pinned` — **should** · scorecard: Pinned-Dependencies. Fail when third-party actions use a moving tag/branch instead of a full commit SHA. A retagged action can inject code.
- `oidc-for-deploy` — **could**. Pass when deploy/publish jobs use OIDC instead of long-lived cloud secrets. Removes a class of leakable credentials.
- `concurrency-and-timeouts` — **could**. Pass when workflows cancel superseded runs and cap job time. Avoids stuck and duplicated runs.
- `scheduled-maintenance` — **could**. Pass when useful scheduled jobs exist (stale triage, link-check, Scorecard). Keeps the repo tended automatically.

## Scaffold

Templates live in `references/scaffold-templates.md` (a CI workflow with
least-privilege permissions + SHA-pinned actions; an OpenSSF Scorecard workflow).
Write after confirmation, tailored to the stack and the test command (from the
testing-quality capability). Default `permissions: contents: read`, elevate only
the jobs that need more. Pin every third-party action to a commit SHA with a
trailing `# vX.Y.Z` comment.

## Output

Report per `../../references/output-format.md`: scan emits the workflow inventory (triggers, permissions, pinning) with sources; audit emits severity-tagged (Scorecard-aligned) findings, the domain score, and a `scaffold` offer for each unmet check.

## Edge cases

- **No code to build** (docs/data repo) — relax `ci-on-pr` to a docs/link-check workflow; don't demand a build.
- **First-party / org actions** — SHA-pinning matters most for third-party actions; note the lower risk of `actions/*` but still prefer pinning.
- **Self-hosted runners** — flag added trust/security considerations rather than treating them as equivalent to hosted.
- **`gh` unavailable** — read workflow files directly; required-checks status may be `unknown`.

## Anti-patterns

- Don't echo or commit workflow secrets — reason about config only.
- Don't scaffold a workflow with default-write or unpinned third-party actions.
- Don't duplicate the test suite definition or the dependency-bot config — reference the owning capabilities.
- Don't overwrite an existing workflow without a diff.
