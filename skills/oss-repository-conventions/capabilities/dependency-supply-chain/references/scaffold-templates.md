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

**b) Tiered approve + auto-merge — `.github/workflows/dependabot-auto-merge.yaml`** (on `pull_request: [opened, reopened, synchronize, labeled]`)

```yaml
permissions: { contents: read, pull-requests: read }
jobs:
  # For a built artifact (e.g. dist/): rebuild, then commit it AS THE APP via the
  # GraphQL createCommitOnBranch mutation — that lands a Verified commit and the
  # resulting `synchronize` re-triggers required checks. A plain `git push` with
  # GITHUB_TOKEN lands Unverified AND is anti-loop-suppressed, so checks never
  # re-run and the PR strands. A `built-artifact-verified` CI gate (ci-automation)
  # backstops a missed rebuild.
  auto-merge:
    # Kill switch fails safe: unset reads as disabled. Log the resolved state in a
    # real setup so deliberately-off is distinguishable from not-resolving.
    if: >-
      github.event.action != 'labeled' && github.actor == 'dependabot[bot]'
      && vars.DEPENDABOT_AUTOMERGE_ENABLED == 'true'
    runs-on: ubuntu-latest
    steps:
      - id: app-token
        uses: actions/create-github-app-token@<sha>   # v2
        with:
          client-id: ${{ vars.AUTOMATION_CLIENT_ID }}
          private-key: ${{ secrets.AUTOMATION_PRIVATE_KEY }}
      - id: meta
        uses: dependabot/fetch-metadata@<sha>   # v2
      # ELIGIBLE tier: patch/minor of an unprivileged dependency, no veto label ->
      # approve + arm. Fail open: if this step can't run, the PR waits for a human.
      - name: Approve and arm eligible updates
        if: >-
          contains(fromJSON('["version-update:semver-patch","version-update:semver-minor"]'), steps.meta.outputs.update-type)
          && !contains(steps.meta.outputs.dependency-names, '<privileged-dependency>')
          && !contains(github.event.pull_request.labels.*.name, 'security-review-required')
        env: { GH_TOKEN: ${{ steps.app-token.outputs.token }} }
        run: |
          gh pr review --approve "$PR_URL"
          gh pr merge --squash --auto "$PR_URL"
      # HELD tier: majors, and dependencies the automation itself runs on -> arm
      # but never approve, so one human review is the ingredient that completes it.
      - name: Arm held updates without approving
        if: >-
          !contains(fromJSON('["version-update:semver-patch","version-update:semver-minor"]'), steps.meta.outputs.update-type)
          || contains(steps.meta.outputs.dependency-names, '<privileged-dependency>')
        env: { GH_TOKEN: ${{ steps.app-token.outputs.token }} }
        run: gh pr merge --squash --auto "$PR_URL"

  # VETO tier: a hard-stop label applied after arming must disarm, and the disarm
  # fails CLOSED — exit red unless auto-merge is confirmed off.
  disarm-on-veto:
    if: >-
      github.event.action == 'labeled'
      && github.event.label.name == 'security-review-required'
      && github.actor != 'dependabot[bot]'
    runs-on: ubuntu-latest
    steps:
      - id: app-token
        uses: actions/create-github-app-token@<sha>   # v2
        with:
          client-id: ${{ vars.AUTOMATION_CLIENT_ID }}
          private-key: ${{ secrets.AUTOMATION_PRIVATE_KEY }}
      - name: Disable auto-merge and verify it took
        env: { GH_TOKEN: ${{ steps.app-token.outputs.token }} }
        run: |
          gh pr merge --disable-auto "$PR_URL" || true
          test "$(gh pr view "$PR_URL" --json autoMergeRequest --jq '.autoMergeRequest == null')" = "true"
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
