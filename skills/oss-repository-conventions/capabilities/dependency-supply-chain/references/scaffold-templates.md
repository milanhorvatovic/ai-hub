# dependency-supply-chain — scaffold templates

Dependency-automation configs for the `dependency-supply-chain` capability. Add one ecosystem entry per manifest directory. House style uses Dependabot at `.github/dependabot.yaml`.

## Dependabot — `.github/dependabot.yaml`

```yaml
version: 2
updates:
  # GitHub Actions
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
    groups:
      actions:
        patterns: ["*"]
    # If an auto-merge policy job runs on pull_request, bar the actions IT runs
    # from bot updates — a bot PR bumping one executes PR-head code with the App
    # key in scope before any tier logic. Their pins arrive as human PRs.
    ignore:
      - dependency-name: "dependabot/fetch-metadata"
      - dependency-name: "actions/create-github-app-token"

  # One block per package ecosystem present (npm / pip / cargo / gomod / bundler …)
  - package-ecosystem: <npm|pip|cargo|gomod|bundler>
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 10
    groups:
      minor-and-patch:
        update-types: ["minor", "patch"]
```

## Renovate — `renovate.json` (alternative to Dependabot)

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended", ":dependencyDashboard"],
  "schedule": ["before 6am on monday"],
  "packageRules": [
    { "matchUpdateTypes": ["minor", "patch"], "groupName": "non-major" }
  ]
}
```

## Dependency review CI step — add to a PR workflow

```yaml
  dependency-review:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@<sha>                  # v4
      - uses: actions/dependency-review-action@<sha>  # v4
```

## Enable Dependabot alerts (repo setting — propose, don't apply)

```bash
gh api -X PUT repos/{owner}/{repo}/vulnerability-alerts
gh api -X PUT repos/{owner}/{repo}/automated-security-fixes
```

## Autonomous Dependabot recipe

A near-hands-off flow that labels, approves, and merges Dependabot PRs and reconciles dropped events, on a three-tier policy. **This section is the shape and the reasons, not a paste-ready implementation** — the production version is dense with concurrency, TOCTOU, fail-closed, and required-context handling that a trimmed snippet cannot carry honestly. Scaffold the shape below, then adopt a hardened reference implementation rather than growing this inline: a maintained reusable workflow (see the `automation-playbooks.md` autonomous flow), or the fleet's own worked example at [`milanhorvatovic/ai-hub`](https://github.com/milanhorvatovic/ai-hub/blob/main/.github/workflows/dependabot-auto-merge.yaml) with its structural tests. Consuming a pinned reusable workflow — not recopying this YAML — is itself the identity/supply-chain doctrine this skill teaches.

**The three tiers** (one policy workflow classifies each bot PR):

- **Eligible** — patch/minor of an unprivileged dependency, no veto label → the App approves and arms auto-merge; it lands hands-off once required checks pass.
- **Held** — a major, or a privileged dependency → arm auto-merge but never approve, so one human review is the only missing ingredient. This holds only where branch protection **requires an approving review**; without that rule, arming is merging, so leave held PRs unarmed instead.
- **Veto** — a hard-stop label (`security-review-required`) → disarm any armed auto-merge and dismiss any standing bot approval, so the hard stop can't be satisfied by an approval posted before it.

**Prerequisites — the wiring the shape depends on:**

- A **GitHub App token** (`actions/create-github-app-token`, App-only for the review-dismissal filters); the default `GITHUB_TOKEN` triggers no downstream required checks and can't hold the review rule. Stand it up per the capability's automation-prerequisites reference (dual secret stores, PKCS-agnostic key handling, verify with an actored run).
- **Branch protection** with required status checks **and** a required approving review (the checks gate merge on green; the review requirement is what the held tier holds on).
- **The veto/disarm job made a required, always-reporting status context** — a red disarm run only blocks the merge if branch protection waits on it; otherwise the PR lands once unrelated checks pass.
- **The actions the policy job itself runs** (metadata, token-minting) **barred from bot updates** in the Dependabot config — on `pull_request` the workflow definition comes from the PR head, so a bot PR bumping one runs PR-selected code with the App key in scope _before_ any tier logic; their pins arrive as human PRs.
- **The `release:*` labels the flow computes, created first** (`gh label create` fails-nothing on a missing label; `gh pr edit --add-label` fails hard).

**The load-bearing implementation properties** — an adopted reference workflow must have these; a hand-rolled one is not done without them:

- **Author + same-repo guard, not `github.actor`** — match `dependabot[bot]` _or_ `app/dependabot` on an in-repo head, so a maintainer's reopen or an App's `update-branch` re-fire is not skipped.
- **Asymmetric failure posture** — approve/arm fail **open** (warn, leave the PR manual); disarm and dismissal fail **closed** (red unless confirmed), and every fail-closed check reads its own result rather than trusting a command substitution that is empty on failure.
- **Live re-reads** — the event payload is a stale snapshot; re-read the veto label immediately before approving or arming, and dismiss a stale automation approval before arming a held PR.
- **Fail-safe kill switch** — a repo variable that reads as _disabled_ when unset, logged every run; switching it off must also dispatch the reconciler to disarm in-flight PRs, since a variable change fires no event.
- **A reconciler** (cron + `workflow_run` + dispatch) that re-drives stuck PRs, skips veto-labeled ones, and runs in reverse (disarming) while the switch is off.

## Autonomous Renovate (alternative to the recipe above)

Renovate runs its own merge loop, so its autonomous path is config, not workflows — no label/approve/merge/reconcile YAML to maintain.

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["config:recommended"],
  "platformAutomerge": true,
  "packageRules": [
    { "matchUpdateTypes": ["minor", "patch"], "automerge": true },
    { "matchUpdateTypes": ["major"], "automerge": false },
    { "matchDepTypes": ["engines"], "automerge": false }
  ]
}
```

Same prerequisites as the Dependabot recipe: branch protection with required checks (Renovate merges only on green), and a bot identity if the ruleset requires a non-default approver. Security updates still surface for review rather than silent auto-merge.
