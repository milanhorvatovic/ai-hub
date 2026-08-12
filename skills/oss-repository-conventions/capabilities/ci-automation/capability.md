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
- **Fork-PR safety is a trust boundary.** A workflow that runs on PRs and exposes secrets or write permission to fork-controlled code is the classic "pwn request". `pull_request` runs fork code but withholds secrets and defaults the token to read-only; `pull_request_target` runs in the base context _with_ secrets, so it must never check out or execute the PR head. Treat any secret-bearing or write-scoped PR job as fork-exposed unless it's gated on `head.repo.full_name == github.repository`.
- Dependency bots (Dependabot/Renovate) and lockfile/SBOM concerns are the dependency-supply-chain capability; here, cover workflow files and action pinning.
- Scaffolding a workflow that _runs_ tests relies on the test config from the testing-quality capability — reference it, don't redefine the suite.
- A workflow's identity, the secret store it reads from (Actions vs Dependabot), and the repo settings its automation depends on are out-of-band **prerequisites**, not workflow YAML — see `../../references/automation-prerequisites.md`; whether they're provisioned is the cross-cutting `automation-prereqs-provisioned` check owned by the automation-baseline capability.

## Languages

Detect per `../../references/language-support.md`. The workflow shell is language-agnostic; per-language support comes from setup actions:

- **First-class:** languages with a maintained setup action — `actions/setup-node`, `actions/setup-python`, `actions/setup-go`, `actions-rust-lang/setup-rust-toolchain`, `swift-actions/setup-swift`, `ruby/setup-ruby`.
- **Recognized:** other stacks — use a generic toolchain step (mise / container) in the job.
- **Unknown:** scaffold the job skeleton with a placeholder toolchain step; never invent a setup action.
- **Compiled vs interpreted:** compiled languages (Swift, Go, Rust, Java, C/C++) need a build/compile step in the job; interpreted languages (Python, JS/TS, Ruby) don't. For the compiled languages CodeQL supports (Swift, Go, Java, C/C++ — not Rust) this build step also drives the CodeQL analysis — see the automation-baseline capability.

## Scan

Sources (catalog: `../../references/convention-files.md`, CI/CD section), citing each:

1. Workflows: `.github/workflows/*.yml` — names, `on:` triggers (push / pull_request / schedule / workflow_dispatch), jobs, matrix.
2. Permissions: top-level / per-job `permissions:`; default is over-privileged when unset on classic tokens.
3. Action pinning: `uses:` lines — pinned to a full commit SHA vs a moving tag/branch.
4. Auth: OIDC (`permissions: id-token: write` + cloud login actions) vs long-lived secrets for deploy/publish.
5. Hygiene: `concurrency:` cancellation, job `timeout-minutes`, reusable/`workflow_call` workflows, scheduled jobs (stale, link-check, Scorecard).
6. Invariant tests: suites in the repo's own tests that parse the workflow files and assert their shape (timeouts, permissions, pins, guard conditions).

## Audit

Checks follow the schema in `../../references/oss-health-rubric.md` (`id` — **severity** [· scorecard: Name]. criterion. why):

- `ci-on-pr` — **should** (→ **must** for code repos) · scorecard: CI-Tests. Fail when no workflow builds/tests on `pull_request`. Changes merge unverified otherwise.
- `least-privilege-token` — **should** · scorecard: Token-Permissions. Fail when workflows don't set minimal `permissions:` (read-only default, elevate per job). Over-privileged tokens widen the blast radius of a compromised action.
- `actions-pinned` — **should** · scorecard: Pinned-Dependencies. Fail when third-party actions use a moving tag/branch instead of a full commit SHA. A retagged action can inject code. Recommend the human half ride the same line as a **trailing** version comment (`uses: owner/action@<sha> # vX.Y.Z`) — dependency bots maintain the trailing form when they bump the pin, while a comment on the line above rots silently until it misdescribes what actually runs.
- `oidc-for-deploy` — **could**. Pass when deploy/publish jobs use OIDC instead of long-lived cloud secrets. Removes a class of leakable credentials. For the workflow's own identity (App vs PAT vs default token), see `../../references/automation-identity.md`.
- `concurrency-and-timeouts` — **could**. Pass when workflows cancel superseded runs and cap job time. Avoids stuck and duplicated runs.
- `scheduled-maintenance` — **could**. Pass when useful scheduled jobs exist (stale triage, link-check, Scorecard). Keeps the repo tended automatically.
- `runner-hardening` — **could**. Pass when CI runners restrict egress / are hardened (e.g. step-security/harden-runner) so a compromised step or dependency can't exfiltrate secrets or tamper with the build. Defense-in-depth on top of least-privilege tokens and SHA-pinned actions.
- `fork-pr-safe` — **should** (→ **must** when a PR-triggered workflow exposes secrets or write scope). Fail when a workflow runs fork-controlled code with secrets or write permission in scope — `pull_request_target` that checks out / runs the PR head, or a secret-bearing PR job not gated on `head.repo.full_name == github.repository` (plus the expected author, e.g. `dependabot[bot]`, for bot-only flows). A fork PR can otherwise exfiltrate secrets or push to the repo (the "pwn request"). The guard conditions must actually **bind** — `&&` outranks `||`, so a condition demoted behind an ungrouped `||` still appears in the expression while gating nothing — and the strongest shape keeps the token-bearing job **checkout-free**, so even a mis-gated run has no fork code to execute. Checkout-free is still not execution-free: on `pull_request` events the workflow _definition_ — including its `uses:` pins — comes from the PR head, so a same-repo bot PR that bumps an action this very job runs executes the PR-selected action code with the secrets in scope. Actions a secret-bearing PR job runs must therefore be excluded from bot updates at the update-bot config level (their pin changes arrive as human PRs), or the job's workflow definition must come from a trusted ref.
- `built-artifact-verified` — **should** (when the repo commits a generated artifact — a bundled `dist/`, generated clients/docs). Fail when CI doesn't rebuild the artifact and fail on drift from the committed copy (a `verify-dist`-style gate), and likewise gate lockfile-vs-manifest and SHA-pin invariants rather than only linting them. A stale or hand-edited generated artifact ships code that doesn't match source; the autonomous-update rebuild step assumes this gate exists.
- `metered-automation-bounded` — **could**. Pass when metered automation (paid API calls, AI review, large matrices) bounds cost — path-excludes, draft-skip, author allowlists, concurrency cancellation, explicit caps. Unbounded metered automation runs up cost and queue time on every push.
- `workflow-invariants-pinned` — **could**. Pass when the repo's own test suite asserts its workflow invariants — every runner-backed job carries a timeout (a job that calls a reusable workflow cannot declare one; its cap lives in the callee), permissions stay on the read-only floor with per-job elevation, pins hold their format, and trust-boundary guard conditions exist where the fork-PR check demands them — so a workflow edit that widens them fails CI like any code change. Convention held only by review erodes one approved edit at a time; a pinned invariant makes the widening a visible, deliberate decision.

## Scaffold

The base composable CI shape (setup action, thin caller, CodeQL) comes from the automation-baseline capability; this capability _hardens_ it. For the ordered end-to-end hardening pass (flow 3), follow `../../references/automation-playbooks.md`. Apply the patterns in `references/scaffold-templates.md`: default `permissions: contents: read` and elevate per job, pin every third-party action to a commit SHA with a trailing `# vX.Y.Z` comment, use OIDC for deploy/publish, and set concurrency cancellation and job timeouts. Scaffold the optional OpenSSF Scorecard workflow from the same file. When a convention deserves a PR gate (pin format, permission floors), the trustworthy shape runs the checker on `pull_request_target` **from the base branch**, fetching only the specific head files it statically parses — as data, never a checkout into the workspace, never executed, per this capability's fork-PR guard — so a PR can't edit its own judge, with the deliberate consequence that the PR _introducing_ the gate goes unjudged by it — the gate's first real run lands on the next PR after the merge. Modify workflows only on confirmation, showing a diff for existing files.

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
