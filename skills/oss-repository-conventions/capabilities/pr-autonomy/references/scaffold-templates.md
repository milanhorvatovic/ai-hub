# pr-autonomy — scaffold snippets

Per-rung building blocks. Install a rung's guardrails _before_ its capability. Pin every action to a SHA; mint the App token per job; keep `permissions` minimal.

## Prerequisite (L3+): branch protection with required checks — propose, don't apply

```bash
gh api -X PUT repos/{owner}/{repo}/branches/{default}/protection \
  --input branch-protection.json   # require checks + review; block force-push
gh repo edit {owner}/{repo} --enable-auto-merge
```

## Scoped identity (L2+): mint a least-privilege App token

```yaml
      - id: app-token
        uses: actions/create-github-app-token@<sha>   # v2
        with:
          app-id: ${{ vars.AUTOMATION_APP_ID }}
          private-key: ${{ secrets.AUTOMATION_APP_KEY }}
      # use steps.app-token.outputs.token for gh review/merge — NOT GITHUB_TOKEN
```

## Eligibility gate + hard stops (all rungs above L1)

```yaml
      - id: meta
        uses: dependabot/fetch-metadata@<sha>          # v2  (deps); or derive from labels/paths
      - name: Decide eligibility
        run: |
          # ELIGIBLE: bot author AND patch|minor AND path allowlist AND size cap
          # HARD STOP (require human): major | security | breaking | touches CI/release/secrets
```

## → L2: auto-approve eligible PRs

```yaml
      - if: steps.meta.outputs.eligible == 'true'
        env: { GH_TOKEN: ${{ steps.app-token.outputs.token }} }
        run: gh pr review --approve "$PR_URL"
```

## → L3: auto-merge on green (native)

```yaml
      - if: steps.meta.outputs.eligible == 'true'
        env: { GH_TOKEN: ${{ steps.app-token.outputs.token }} }
        run: gh pr merge --squash --auto "$PR_URL"   # lands only when required checks pass
```

Third-party alternative — `.mergify.yml`:

```yaml
pull_request_rules:
  - name: auto-merge patch/minor deps on green
    conditions: ["author=dependabot[bot]", "check-success=ci", "label=release:patch"]
    actions: { queue: { method: squash } }
```

## Concurrency control (L3+)

Serialize per PR so the flow can't race itself; run the reconciler as a singleton.

```yaml
# auto-merge.yml — one in-flight run per PR
concurrency:
  group: auto-merge-pr-${{ github.event.pull_request.number }}
  cancel-in-progress: true

# reconciler.yml — never two reconcile passes at once; don't cancel a pass mid-flight
concurrency:
  group: dependabot-reconciler
  cancel-in-progress: false
```

## → L4: reconciler + escape hatch

```yaml
# reconciler.yml — on: { schedule: [{cron: "0 * * * *"}], workflow_run: {...}, workflow_dispatch: }
#   re-apply labels, re-enable auto-merge, update-branch if behind; the cron backstops dropped events.
#   `workflow_run` is required because a GITHUB_TOKEN-driven merge's push:main is anti-loop-suppressed
#   (see automation-identity.md) — so a push:main trigger alone would miss it.

# escape hatch: gate the whole flow behind a repo variable
on: ...
jobs:
  autonomy:
    if: vars.AUTONOMY_ENABLED == 'true'   # flip to 'false' to stop everything
    ...
  # also: a step that disables auto-merge when a security review is requested
```

## Observability: fail loud, don't warn-and-pass (L4)

An unrecoverable autonomous action must turn the run red so it's noticed; optionally raise an alert.

```yaml
      - name: Reconcile (fail the run on an unrecoverable state)
        run: |
          if ! reconcile_all; then
            echo "::error::Reconciler could not drive PR #$PR to a known state"
            exit 1                      # red run — not a silent warning
          fi
      - name: Notify on failure
        if: failure()
        run: gh issue create --title "Autonomy reconciler failed on $(date -u +%F)" --label automation
        # or post to Slack/Teams via a webhook secret
```

## Merge queue (alternative to the BEHIND/update-branch dance, L3+)

For high-traffic repos, enable a merge queue in the branch ruleset (`branch-protection.md`) and target it instead of an immediate squash:

```yaml
      - run: gh pr merge --auto --squash "$PR_URL"   # with a merge queue configured, this queues the PR;
                                                      # the queue re-tests against latest base before landing
```
