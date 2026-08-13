# pr-autonomy — scaffold templates

Per-rung building blocks. Install a rung's guardrails _before_ its capability. Pin every action to a SHA; mint the App token per job; keep `permissions` minimal.

## Prerequisite (L3+): branch protection with required checks — propose, don't apply

Adapt the payload from `branch-protection.example.json`, shipped in the security-policy capability's references.

```bash
gh api -X PUT repos/{owner}/{repo}/branches/{default}/protection \
  --input branch-protection.json   # require checks + review; block force-push
gh repo edit {owner}/{repo} --enable-auto-merge
```

## Scoped identity (L2+)

For a **plain** required-review count with no bot event that must cascade, **and where the approver did not author the PR** (a bot can't approve its own PR — a Dependabot PR qualifies, a `github-actions[bot]`-authored one needs a distinct App/PAT), the default token is the least-privilege choice — approve with `GITHUB_TOKEN` under `permissions: { pull-requests: write }`, with the repo's "Allow GitHub Actions to create and approve pull requests" setting on. Mint an **App** token instead only when an authored event must trigger a downstream required check, or for truthful attribution (code-owner review is neither — a separate PAT/ruleset remedy):

```yaml
      # App path (cascade / attribution). For a plain review, DROP this step AND
      # set GH_TOKEN: ${{ github.token }} in the L2/L3 steps below (not
      # steps.app-token.outputs.token). Permissions: { pull-requests: write } for the
      # L2 approve; L3 `gh pr merge --auto` also needs contents: write.
      - id: app-token
        uses: actions/create-github-app-token@<sha>   # v3.2.0
        with:
          client-id: ${{ vars.AUTOMATION_CLIENT_ID }}
          private-key: ${{ secrets.AUTOMATION_PRIVATE_KEY }}
```

## Eligibility gate + hard stops (all rungs above L1)

```yaml
      - id: meta
        uses: dependabot/fetch-metadata@<sha>          # v2  (deps); or derive from labels/paths
      - id: gate
        name: Decide eligibility
        run: |
          # ELIGIBLE: bot author AND patch|minor AND path allowlist AND size cap
          # HARD STOP (require human): major | security | breaking | human CI/release/secret edit
          #   | a bump of an action that runs in a secret-bearing/write-scoped job
          #   (an unprivileged action bump may be eligible — see pr-autonomy hard-stops)
          echo "eligible=true" >> "$GITHUB_OUTPUT"     # write false on a hard stop
```

## → L2: auto-approve eligible PRs

```yaml
      - if: steps.gate.outputs.eligible == 'true'
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          PR_URL: ${{ github.event.pull_request.html_url }}
        run: gh pr review --approve "$PR_URL"
```

## → L3: auto-merge on green (native)

```yaml
      - if: steps.gate.outputs.eligible == 'true'
        env:
          GH_TOKEN: ${{ steps.app-token.outputs.token }}
          PR_URL: ${{ github.event.pull_request.html_url }}
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

# escape hatch: gate the flow behind a repo variable — checked in the STEPS, with
# an always-run step logging the resolved state (a skipped job can't report that
# the switch is off, or distinguish off from not-resolving). Gating future steps is
# only half a stop: a variable change fires no event, so an ALREADY-armed PR still
# merges. Pair the flip with a reconciler dispatch whose disabled mode disarms and
# verifies every in-flight PR (see the dependency recipe's reconciler).
jobs:
  autonomy:
    steps:
      - env:
          ENABLED: ${{ vars.AUTONOMY_ENABLED }}
        run: echo "AUTONOMY_ENABLED='${ENABLED:-<unset>}'"   # unset fails safe
      - if: vars.AUTONOMY_ENABLED == 'true'
        run: echo "…the autonomous steps, each gated on the switch…"
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
