---
name: ci-automation
description: >
  Scans, audits, and scaffolds a repository's CI and workflow automation —
  GitHub Actions workflows and their triggers, build/test on pull requests, the
  test matrix, least-privilege workflow token permissions, third-party action
  pinning (to a commit SHA), OIDC for deploys, concurrency and timeouts, and
  scheduled maintenance jobs. Audit flags no CI on PRs, over-privileged tokens,
  and unpinned actions; scaffold hardens workflows with least-privilege
  permissions and SHA-pinned actions and adds a Scorecard workflow (the base
  composable CI shape comes from the automation baseline). Dependency bots live
  in the dependency-supply-chain capability. Triggers on "harden my workflows",
  "pin my actions", "do my workflows have least privilege", "lock down CI
  permissions", or a full-repo audit.
allowed-tools: Bash Read Grep Glob Write
---

# ci-automation capability

Governs the repository's automation layer: do workflows build and test changes, and are they configured safely (least privilege, pinned actions, OIDC). Reads and judges by default; writes workflow files only on confirmation.

## Modes

- **scan** — report the workflows, triggers, permissions, and action pinning present.
- **audit** — judge them against `../../references/oss-health-rubric.md` and OpenSSF Scorecard.
- **scaffold** — write a CI workflow after confirmation.

## Inputs & guards

- Not a git repo → stop.
- Workflow secrets and deploy credentials are sensitive — never echo secret values; reason about _configuration_, not contents.
- Dependency bots (Dependabot/Renovate) and lockfile/SBOM concerns are the dependency-supply-chain capability; here, cover workflow files and action pinning.
- Scaffolding a workflow that _runs_ tests relies on the test config from the testing-quality capability — reference it, don't redefine the suite.
- A workflow's identity, the secret store it reads from (Actions vs Dependabot), and the repo settings its automation depends on are out-of-band **prerequisites**, not workflow YAML — see `../../references/automation-prerequisites.md`; whether they're provisioned is the cross-cutting `automation-prereqs-provisioned` check owned by the automation-baseline capability.

## Languages

Detect per `../../references/language-support.md`. The workflow shell is language-agnostic; per-language support comes from setup actions:

- **First-class:** languages with a maintained setup action — `actions/setup-node`, `actions/setup-python`, `actions/setup-go`, `actions-rust-lang/setup-rust-toolchain`, `swift-actions/setup-swift`, `ruby/setup-ruby`.
- **Recognized:** other stacks — use a generic toolchain step (mise / container) in the job.
- **Unknown:** scaffold the job skeleton with a placeholder toolchain step; never invent a setup action.
- **Compiled vs interpreted:** compiled languages (Swift, Go, Rust, Java, C/C++) need a build/compile step in the job; interpreted languages (Python, JS/TS, Ruby) don't. This also drives the CodeQL build — see the automation-baseline capability.

## Scan

Sources (catalog: `../../references/convention-files.md`, CI/CD section), citing each:

1. Workflows: `.github/workflows/*.yml` — names, `on:` triggers (push / pull_request / schedule / workflow_dispatch), jobs, matrix.
2. Permissions: top-level / per-job `permissions:`; default is over-privileged when unset on classic tokens.
3. Action pinning: `uses:` lines — pinned to a full commit SHA vs a moving tag/branch.
4. Auth: OIDC (`permissions: id-token: write` + cloud login actions) vs long-lived secrets for deploy/publish.
5. Hygiene: `concurrency:` cancellation, job `timeout-minutes`, reusable/`workflow_call` workflows, scheduled jobs (stale, link-check, Scorecard).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `ci-on-pr` — **should** (→ **must** for code repos) · scorecard: CI-Tests. Fail when no workflow builds/tests on `pull_request`. Changes merge unverified otherwise.
- `least-privilege-token` — **should** · scorecard: Token-Permissions. Fail when workflows don't set minimal `permissions:` (read-only default, elevate per job). Over-privileged tokens widen the blast radius of a compromised action.
- `actions-pinned` — **should** · scorecard: Pinned-Dependencies. Fail when third-party actions use a moving tag/branch instead of a full commit SHA. A retagged action can inject code.
- `oidc-for-deploy` — **could**. Pass when deploy/publish jobs use OIDC instead of long-lived cloud secrets. Removes a class of leakable credentials. For the workflow's own identity (App vs PAT vs default token), see `../../references/automation-identity.md`.
- `concurrency-and-timeouts` — **could**. Pass when workflows cancel superseded runs and cap job time. Avoids stuck and duplicated runs.
- `scheduled-maintenance` — **could**. Pass when useful scheduled jobs exist (stale triage, link-check, Scorecard). Keeps the repo tended automatically.
- `runner-hardening` — **could**. Pass when CI runners restrict egress / are hardened (e.g. step-security/harden-runner) so a compromised step or dependency can't exfiltrate secrets or tamper with the build. Defense-in-depth on top of least-privilege tokens and SHA-pinned actions.

## Scaffold

The base composable CI shape (setup action, thin caller, CodeQL) comes from the automation-baseline capability; this capability _hardens_ it. Apply the patterns in `references/scaffold-templates.md`: default `permissions: contents: read` and elevate per job, pin every third-party action to a commit SHA with a trailing `# vX.Y.Z` comment, use OIDC for deploy/publish, and set concurrency cancellation and job timeouts. Scaffold the optional OpenSSF Scorecard workflow from the same file. Modify workflows only on confirmation, showing a diff for existing files.

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
