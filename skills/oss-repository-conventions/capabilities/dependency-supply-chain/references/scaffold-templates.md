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

A near-hands-off mechanism that labels, approves, and merges Dependabot PRs, with a reconciler to catch dropped events. Three workflows plus a token.

**Prerequisites**

- A **GitHub App token** (`actions/create-github-app-token`) or a bot PAT — the default `GITHUB_TOKEN` cannot approve PRs or trigger the downstream required checks.
- **Branch protection** on `main` with required status checks (so auto-merge only lands green PRs).

**a) Label by update type — `.github/workflows/dependabot-release-label.yaml`** (on `pull_request: [opened, reopened]`)

```yaml
permissions: { contents: read, pull-requests: write }
jobs:
  add-release-label:
    if: github.actor == 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - uses: dependabot/fetch-metadata@<sha>   # v2  -> outputs.update-type
      - run: gh pr edit "$PR" --add-label "release:${LABEL}"   # map update-type -> label
```

**b) Approve + auto-merge safe updates — `.github/workflows/dependabot-auto-merge.yaml`** (on `pull_request`)

```yaml
permissions: { contents: read, pull-requests: read }
jobs:
  # For a built artifact (e.g. dist/), rebuild and commit it as the bot first.
  auto-merge:
    if: github.actor == 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - uses: dependabot/fetch-metadata@<sha>   # v2
      - name: Approve and enable auto-merge for patch/minor
        if: contains(fromJSON('["version-update:semver-patch","version-update:semver-minor"]'), steps.meta.outputs.update-type)
        env: { GH_TOKEN: ${{ steps.app-token.outputs.token }} }
        run: |
          gh pr review --approve "$PR_URL"
          gh pr merge --squash --auto "$PR_URL"
      # Major and security-flagged PRs are intentionally left for human review.
```

**c) Reconciler — `.github/workflows/dependabot-reconciler.yaml`** (on `schedule: hourly cron` + `workflow_run` + `workflow_dispatch`)

```yaml
permissions: { contents: read, pull-requests: read }
jobs:
  reconcile:
    runs-on: ubuntu-latest
    steps:
      - name: Re-drive open Dependabot PRs (catch dropped events)
        run: |
          # for each open dependabot PR: re-apply label, re-enable auto-merge,
          # update-branch if behind. The hourly cron backstops missed webhooks.
```

Pin every action to a SHA; mint the bot token per job; never auto-merge major or security-flagged updates unattended.
