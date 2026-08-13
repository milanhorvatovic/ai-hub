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

A near-hands-off mechanism that labels, approves, and merges Dependabot PRs, with a reconciler to catch dropped events. Three workflows plus a token.

**Prerequisites**

- A **GitHub App token** (`actions/create-github-app-token`); the default `GITHUB_TOKEN` triggers no downstream required checks and approves only behind the off-by-default Actions-can-approve setting. This recipe is written **App-only** — its review-dismissal steps filter on `user.type == "Bot"`; on the bot-PAT alternative the automation's reviews are `User`, so replace those filters with `select(.user.login == "<automation-account>")` throughout.
- **Branch protection** on `main` with required status checks **and at least one required approving review** — the checks make auto-merge land only green PRs, and the review requirement is what makes the held tier hold anything. Without it, arming a held PR is merging it: leave held updates unarmed instead.
- **The `disarm-on-veto` job made a required status context** — a red disarm run only _blocks_ the armed merge if branch protection waits on it; otherwise the PR still lands once the unrelated required checks pass. Make the veto job always report (run unconditionally, succeed when there is nothing to disarm) and add its context to the required set.
- **The policy job's own actions barred from bot updates** in the Dependabot config (`ignore:` entries for the metadata and token-minting actions): on `pull_request` events the workflow definition comes from the PR head, so a bot PR bumping one of these executes the PR-selected action code with the App key in scope **before** any tier logic runs — their pin changes must arrive as human PRs.
- **Every label the workflows compute, created first** — the labeler derives `release:patch` / `release:minor` / `release:major`, and `gh pr edit --add-label` fails on a label that does not exist: `for t in patch minor major; do gh label create "release:$t"; done` (matching the no-space form the workflow writes).

**a) Label by update type — `.github/workflows/dependabot-release-label.yaml`** (on `pull_request: [opened, reopened, synchronize]` — `synchronize` because an App's `update-branch` re-fires it)

```yaml
permissions: { contents: read, pull-requests: read }   # writes go through the App token; keep the default token on the read-only floor
jobs:
  add-release-label:
    # Gate on the PR's AUTHOR and an in-repo head, not github.actor: a maintainer's
    # reopen or an App's update-branch re-fires these events on Dependabot's PR,
    # and an actor gate would skip exactly those re-runs.
    if: >-
      (github.event.pull_request.user.login == 'dependabot[bot]'
      || github.event.pull_request.user.login == 'app/dependabot')
      && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      # Dependabot-triggered runs get a READ-ONLY GITHUB_TOKEN regardless of the
      # permissions block — labeling needs the App token, minted from the
      # Dependabot secret store this run reads.
      - id: app-token
        uses: actions/create-github-app-token@<sha>   # v3.2.0
        with:
          client-id: ${{ vars.AUTOMATION_CLIENT_ID }}
          private-key: ${{ secrets.AUTOMATION_PRIVATE_KEY }}
      - id: meta
        uses: dependabot/fetch-metadata@<sha>   # v2  -> outputs.update-type
      - env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          PR_URL: ${{ github.event.pull_request.html_url }}
          UPDATE_TYPE: ${{ steps.meta.outputs.update-type }}
        # update-type is "version-update:semver-{patch,minor,major}"; the label is
        # its last word. Remove any stale release:* first — synchronize re-fires
        # this, and --add-label alone would let a PR accumulate two release labels.
        run: |
          gh pr edit "$PR_URL" --remove-label release:patch --remove-label release:minor --remove-label release:major || true
          gh pr edit "$PR_URL" --add-label "release:${UPDATE_TYPE##*semver-}"
```

**b) Tiered approve + auto-merge — `.github/workflows/dependabot-auto-merge.yaml`** (on `pull_request: [opened, reopened, synchronize, labeled, unlabeled]` — `unlabeled` so removing the veto re-runs the required disarm context, which otherwise stays red on the head)

```yaml
permissions: { contents: read, pull-requests: read }
# Serialize per PR so a VETO event cancels an in-flight arming run instead of
# racing it (stale-snapshot TOCTOU). Routine label events (the release label lands
# seconds after opening) must NOT cancel — they'd kill the arming run and their
# own replacement skips the job; newer code snapshots may cancel older ones.
concurrency:
  group: dependabot-auto-merge-${{ github.event.pull_request.number }}
  cancel-in-progress: ${{ github.event.action != 'labeled' || github.event.label.name == 'security-review-required' }}
jobs:
  # For a built artifact (e.g. dist/): rebuild, then commit it AS THE APP via the
  # GraphQL createCommitOnBranch mutation — that lands a Verified commit and the
  # resulting `synchronize` re-triggers required checks. A plain `git push` with
  # GITHUB_TOKEN lands Unverified AND is anti-loop-suppressed, so checks never
  # re-run and the PR strands. A `built-artifact-verified` CI gate (ci-automation)
  # backstops a missed rebuild.
  auto-merge:
    # Author + in-repo head, not github.actor (see the label job). The kill switch
    # is NOT in this if: a skipped job can't log its state, and the off position
    # must still be observable — the tier steps gate on it instead.
    if: >-
      github.event.action != 'labeled'
      && (github.event.pull_request.user.login == 'dependabot[bot]'
      || github.event.pull_request.user.login == 'app/dependabot')
      && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      # Fail-safe switch, observably: unset reads as disabled, and every run logs
      # the resolved state so deliberately-off is distinguishable from a variable
      # that isn't resolving. Switching off stops new arming only — the reconciler
      # disarms anything already armed (see c).
      - name: Report kill-switch state
        # Block-style env on purpose: an unquoted ${{ }} inside a { } flow mapping
        # is invalid YAML — the expression's braces end the mapping early.
        env:
          ENABLED: ${{ vars.DEPENDABOT_AUTOMERGE_ENABLED }}
        run: echo "DEPENDABOT_AUTOMERGE_ENABLED='${ENABLED:-<unset>}'"
      - id: app-token
        if: vars.DEPENDABOT_AUTOMERGE_ENABLED == 'true'
        uses: actions/create-github-app-token@<sha>   # v3.2.0
        with:
          client-id: ${{ vars.AUTOMATION_CLIENT_ID }}
          private-key: ${{ secrets.AUTOMATION_PRIVATE_KEY }}
      - id: meta
        if: vars.DEPENDABOT_AUTOMERGE_ENABLED == 'true'
        uses: dependabot/fetch-metadata@<sha>   # v2
      # ELIGIBLE tier: patch/minor of an unprivileged dependency, no veto label ->
      # approve + arm. Both mutations fail OPEN — warn and stop, leaving a manual
      # PR — and labels are RE-READ live first (the event payload is a stale
      # snapshot; a veto applied since must win).
      - name: Approve and arm eligible updates
        if: >-
          vars.DEPENDABOT_AUTOMERGE_ENABLED == 'true'
          && contains(fromJSON('["version-update:semver-patch","version-update:semver-minor"]'), steps.meta.outputs.update-type)
          && !contains(steps.meta.outputs.dependency-names, '<privileged-dependency>')
          && !contains(github.event.pull_request.labels.*.name, 'security-review-required')
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          PR_URL: ${{ github.event.pull_request.html_url }}
        run: |
          gh pr view "$PR_URL" --json labels --jq 'any(.labels[]; .name == "security-review-required")' | grep -qx false \
            || { echo "::warning::veto label present on live read; skipping"; exit 0; }
          gh pr review --approve "$PR_URL" \
            || { echo "::warning::approve failed; leaving for human review"; exit 0; }
          gh pr merge --squash --auto "$PR_URL" \
            || echo "::warning::arming failed; PR stays manual"
      # HELD tier: majors and privileged-but-not-in-this-job dependencies -> arm
      # but never approve, so one human review is the ingredient that completes
      # it. ONLY valid with a required-approving-review branch rule (see the
      # prerequisites) — with no review rule, arming is merging. Same live veto
      # re-read; and a stale AUTOMATION approval from an earlier eligible run
      # (before a policy change reclassified this PR as held) is dismissed first,
      # or --auto merges on it with no human in the loop.
      - name: Arm held updates without approving
        if: >-
          vars.DEPENDABOT_AUTOMERGE_ENABLED == 'true'
          && (!contains(fromJSON('["version-update:semver-patch","version-update:semver-minor"]'), steps.meta.outputs.update-type)
          || contains(steps.meta.outputs.dependency-names, '<privileged-dependency>'))
          && !contains(github.event.pull_request.labels.*.name, 'security-review-required')
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          PR_URL: ${{ github.event.pull_request.html_url }}
          PR: ${{ github.event.pull_request.number }}
        run: |
          gh pr view "$PR_URL" --json labels --jq 'any(.labels[]; .name == "security-review-required")' | grep -qx false \
            || { echo "::warning::veto label present on live read; skipping"; exit 0; }
          # Dismiss any prior App approval so "held == never approved" survives an
          # eligible->held reclassification, then VERIFY none remain — arming with a
          # stale approval still standing would merge without a human.
          gh api --paginate "repos/${{ github.repository }}/pulls/$PR/reviews" \
            --jq '.[] | select(.user.type == "Bot" and .state == "APPROVED") | .id' \
          | while read -r id; do
              gh api -X PUT "repos/${{ github.repository }}/pulls/$PR/reviews/$id/dismissals" \
                -f message="held: needs human review"
            done
          remaining="$(gh api --paginate "repos/${{ github.repository }}/pulls/$PR/reviews" \
            --jq '.[] | select(.user.type == "Bot" and .state == "APPROVED") | .id')"
          [ -z "$remaining" ] || { echo "::warning::a bot approval survived dismissal; not arming"; exit 0; }
          gh pr merge --squash --auto "$PR_URL" || echo "::warning::arming failed; PR stays manual"

  # VETO tier: a hard-stop label disarms, whoever applied it (Dependabot can label
  # its own PRs, so no actor exclusion). This job runs on EVERY bot-PR event and
  # branches on the CURRENT labels rather than gating on `action == labeled`: if it
  # gated on the label event alone, a later synchronize/reopened while the label
  # persists would skip it, and a skipped required context replaces its own red
  # result on the new head while auto-merge is still armed. Always-report also lets
  # it serve as the required disarm context (see prerequisites). The disarm itself
  # fails CLOSED — exit red unless auto-merge is confirmed off.
  disarm-on-veto:
    if: >-
      (github.event.pull_request.user.login == 'dependabot[bot]'
      || github.event.pull_request.user.login == 'app/dependabot')
      && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - id: app-token
        uses: actions/create-github-app-token@<sha>   # v3.2.0
        with:
          client-id: ${{ vars.AUTOMATION_CLIENT_ID }}
          private-key: ${{ secrets.AUTOMATION_PRIVATE_KEY }}
      - name: Disarm on veto, dismiss the bot approval, verify both took
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          PR_URL: ${{ github.event.pull_request.html_url }}
          PR: ${{ github.event.pull_request.number }}
        run: |
          # Read the label live off the current head. Distinguish "read failed"
          # from "no veto": a failed read fails CLOSED (exit red), not skip — only a
          # confirmed absence of the label exits green.
          label_state="$(gh pr view "$PR_URL" --json labels --jq 'any(.labels[]; .name == "security-review-required")')" || { echo "::error::could not read labels; failing closed"; exit 1; }
          [ "$label_state" = "true" ] || { echo "no veto label on the current head; nothing to disarm"; exit 0; }
          gh pr merge --disable-auto "$PR_URL" || true
          test "$(gh pr view "$PR_URL" --json autoMergeRequest --jq '.autoMergeRequest == null')" = "true"
          # A pre-veto bot approval still satisfies the review rule — a human could
          # merge on its strength. Dismiss ALL of them (paginated: an older approval
          # can sit past page one), then VERIFY none remain — the verify carries the
          # fail-closed guarantee, since a failed substitution feeds a loop nothing
          # and exits green.
          gh api --paginate "repos/${{ github.repository }}/pulls/$PR/reviews" \
            --jq '.[] | select(.user.type == "Bot" and .state == "APPROVED") | .id' \
          | while read -r id; do
              gh api -X PUT "repos/${{ github.repository }}/pulls/$PR/reviews/$id/dismissals" \
                -f message="security-review-required"
            done
          # Capture in two steps: a failed substitution is empty too, and `test -z`
          # on it would pass and paint this fail-closed job green without checking.
          remaining="$(gh api --paginate "repos/${{ github.repository }}/pulls/$PR/reviews" \
            --jq '.[] | select(.user.type == "Bot" and .state == "APPROVED") | .id')"
          test -z "$remaining"
```

**c) Reconciler — `.github/workflows/dependabot-reconciler.yaml`** (on `schedule: hourly cron` + `workflow_run` + `workflow_dispatch`)

```yaml
permissions: { contents: read, pull-requests: read }
jobs:
  reconcile:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Re-drive open Dependabot PRs (catch dropped events)
        run: |
          # for each open dependabot PR: SKIP any PR carrying a veto label (the
          # reconciler must never re-arm what the disarm job stopped). With the
          # kill switch OFF, run in reverse: disarm still-armed bot PRs instead
          # of arming. A variable change fires no event, so the stop procedure is
          # two steps: flip the variable, then DISPATCH this workflow — that pass,
          # not the flip, is what stops in-flight PRs; the cron is only a backstop.
          # Otherwise re-apply label, re-enable auto-merge, update-branch if
          # behind. The hourly cron backstops missed webhooks.
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
