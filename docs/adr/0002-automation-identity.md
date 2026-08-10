# 2. Automation identity

Date: 2026-08-10

## Status

Accepted

## Context

Every workflow acts as some identity, and the choice between the default `GITHUB_TOKEN`, a GitHub App, and a user-owned PAT fails in two ways that produce no error message:

- **A `GITHUB_TOKEN`-authored event triggers nothing.** GitHub suppresses workflow triggers for pushes, PRs, and Releases authored by the default token, to prevent a workflow from re-triggering itself. A branch pushed under it never re-runs the required checks, and the PR simply sits with nothing reported.
- **An App cannot satisfy `require_code_owner_review`.** CODEOWNERS accepts only users and teams, so an App's approval never counts toward a code-owner review no matter how it is permissioned.

Neither rule is written down here. One of them has been rediscovered and applied — the Dependabot workflows act as a human for the approval only a human can give — and the other has not been discovered at all, on the path where missing it costs the most. Four facts fix the shape of the decision:

- **The release PR is the live instance of the first rule.** [#45](https://github.com/milanhorvatovic/ai-hub/pull/45) has been open since 2026-07-13 carrying one status against nine required contexts, because its head commit is authored by `github-actions[bot]`. The single reporter is an app-posted check, which is not subject to the suppression rule; nothing that could gate the release ever starts. It is mergeable only through the ruleset's admin bypass, so the first release of this catalog would publish with no CI having run on it.
- **The branch ruleset requires a code-owner review**, one approval, against a CODEOWNERS that names a single user, and it dismisses stale reviews on push. The second rule therefore binds any automation that approves.
- **Both Dependabot workflows already run on a user PAT.** `dependabot-auto-merge.yaml` approves and arms auto-merge with `CODEOWNER_APPROVER_TOKEN`, and `dependabot-reconciler.yaml` uses the same secret to update branches and re-arm. Both are dormant behind the `DEPENDABOT_AUTOMERGE_ENABLED` variable, and the repository currently holds no Actions secrets, no Dependabot secrets, and no variables at all.
- **One workflow already depends on this rule without stating it.** The reconciler updates a PR's branch and then relies on the resulting `synchronize` event to re-run the policy workflow. That is true because the token is a PAT and would be false under `GITHUB_TOKEN` — a load-bearing property recorded only as a comment inside a shell step.

## Decision

### The rule

| You need | Use | Why |
| --- | --- | --- |
| The default — anything that need not trigger downstream workflows or satisfy code-owner review | **`GITHUB_TOKEN`** | Auto-rotated, no setup, no secret to leak; scope it per job with `permissions:` |
| To **trigger downstream workflows** — a push, PR, or Release that must re-run other workflows — or any scoped, rotatable, non-human automation identity | A **GitHub App**, minting a short-lived token per run with `actions/create-github-app-token` from its `client-id` and private key | App-authored events fire other workflows; the App consumes no seat, is permissioned centrally, and outlives any contributor |
| To **satisfy `require_code_owner_review`**, or otherwise act as a human | A **fine-grained PAT owned by an applicable code owner**, minimum scope | CODEOWNERS accepts only users and teams, so an App's approval does not count — and neither does an arbitrary user's: the token's owner must be a code owner for the changed paths and hold the repository access an approval requires |

The three are complementary rather than alternatives: a flow that both pushes and approves needs an App for the push and a PAT for the approval.

### What each workflow uses today

| Workflow | Identity | Verdict |
| --- | --- | --- |
| `change-intent`, `codeql`, `description-eval`, `lint`, `tests` | `GITHUB_TOKEN`, read-only floor with per-job elevation | Correct — none of them authors an event. `codeql` does write, elevating `security-events: write` to upload findings, which cascades nothing |
| `release-please` (the release-please step) | `GITHUB_TOKEN` | **The one gap.** It pushes the release branch and opens the PR, and those events must re-run the required checks |
| `release-please` (`bundle`, `catalog-publish`, `catalog-preview`) | `GITHUB_TOKEN` | Correct — uploading release assets need not cascade, and `catalog-preview` is the read-only dry run. The `bundle` job lives inside the release workflow precisely so it does not depend on a Release event that the default token cannot produce |
| `dependabot-auto-merge` (approve, arm) | `CODEOWNER_APPROVER_TOKEN`, a user PAT; `GITHUB_TOKEN` for the metadata read | Correct — approving against a single-user CODEOWNERS is the one thing only a human identity can do, and reading update metadata needs nothing more than the default |
| `dependabot-reconciler` (update-branch, re-arm) | `CODEOWNER_APPROVER_TOKEN` | Works, but overloads the human identity for a push an App should make; narrow it when the App exists |

### release-please moves to a GitHub App

One App, installed on this repository, permissioned to Contents: write and Pull requests: write — the two scopes the `release-please` job already elevates to, so the App inherits a proven set rather than a guessed one — with its client ID and private key held as secrets and a token minted per run. The action's `client-id` input is used rather than `app-id`, which upstream still accepts as legacy but no longer recommends.

The wiring is deliberately not part of the ADR's own change: the App does not exist yet, and a workflow that mints a token from absent secrets fails the next release run rather than degrading. The sequence is create the App, add the secrets, then land the workflow change.

### Until the App exists

The release PR can be given a real CI run by closing and reopening it: the `reopened` event is human-authored, so it is not suppressed, and every workflow behind the nine required contexts fires on it — none of them narrows `types` in a way that would exclude it.

Two things bound that workaround. It covers only the head it ran on, and the next merge to `main` makes release-please recompute the PR under the default token, so the new head reports nothing again — the fix has to be reapplied per head until the App lands. And it is a way to obtain the checks, not evidence that they were ever failing: run against the release branch on 2026-08-10 — the suite with every code-sample lane required, `ruff`, Prettier, the title validator against `chore: release main`, and the commit linter against the release commit — all nine pass. What the release path is missing is a run, not a repair.

Merging on the admin bypass instead is a decision to publish without CI, and should be stated as one rather than discovered from a PR page that looks green because it is empty.

## Consequences

- **The bot exemptions survive the identity change without an edit.** The PR-title and commit-style gates waive by shape rather than by name — a login matching `[bot]$` or `-bot$`, an author email matching `[bot]@users.noreply.github.com` — and an App's login and commit email both take that form. The release PR's author changes from `github-actions[bot]` to the App's login, and nothing keyed to the literal string exists to break.
- **The same PAT must live in two stores.** The Actions and Dependabot secret stores are isolated, and a Dependabot-triggered run cannot read Actions secrets. `dependabot-auto-merge` runs on a Dependabot-authored `pull_request` event and needs `CODEOWNER_APPROVER_TOKEN` in the Dependabot store; the reconciler runs on schedule and `workflow_run` and needs the same secret in the Actions store.
- **Checks that finally run will also be dismissed and re-run.** The ruleset dismisses stale approvals on push, and release-please recomputes its PR on every merge to `main`, so once the checks are real each recompute costs both a re-run and a re-approval. The release PR wants merging promptly after it is approved, not held open.
- **The reason `bundle` is a job rather than its own workflow expires.** It was structured that way because a `GITHUB_TOKEN`-created Release does not trigger a `release:`-triggered workflow. An App-created Release does. There is no reason to restructure it, but the constraint is gone and should not be cited as one.
- **Least privilege stays explicit.** The App is scoped to the two permissions above, the PAT to the minimum needed to approve, and every workflow keeps its `permissions:` floor with per-job elevation.
- **One App can back several repositories.** Splitting per repository is justified by blast radius, not by default.

## Alternatives considered

- **A PAT for release-please.** It would trigger the checks, since PAT-authored events are not suppressed, and needs no App. Rejected: it ties the release path to one person's account, expires on a schedule, consumes a seat, and makes every release action read as that human's. The PAT is reserved for the one job an App cannot do.
- **Keep `GITHUB_TOKEN` and accept the admin bypass.** Cheapest, and honest if written down. Rejected because it makes the required-check list a label rather than a guarantee on exactly the pull request that publishes signed artifacts to consumers.
- **A separate workflow, on schedule or dispatch, to run the checks against the release branch.** It would rebuild the check matrix in a second place, and its results would attach to a branch rather than to the PR, so the ruleset would still see nothing.
- **`pull_request_target`.** Does not apply: the problem is not which context the workflow runs in but that no pull-request event is emitted at all.
