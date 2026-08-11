# 2. Automation identity

Date: 2026-08-11

## Status

Accepted

## Context

Every workflow acts as some identity, and the choice between the default `GITHUB_TOKEN`, a GitHub App, and a user-owned PAT fails in two ways that produce no error message:

- **A `GITHUB_TOKEN`-authored event triggers almost nothing.** GitHub suppresses workflow triggers for events authored by the default token — pushes, pull requests, and Releases among them — to prevent a workflow from re-triggering itself, with `workflow_dispatch` and `repository_dispatch` the documented exceptions that do start a run. So a branch pushed under it never re-runs the required checks and the PR simply sits with nothing reported, while automation that only needs to kick off a dispatch needs no other identity.
- **An App cannot satisfy `require_code_owner_review`.** CODEOWNERS accepts only users and teams, so an App's approval never counts toward a code-owner review no matter how it is permissioned.

Neither rule surfaces as an error, which is why both are written down here. The facts that fixed the shape of the decision:

- **The release PR was the live instance of the first rule.** [#45](https://github.com/milanhorvatovic/ai-hub/pull/45) sat open from 2026-07-13 carrying one status against nine required contexts, because release-please pushed it with the default token. The credential that pushes is what decides, not the author recorded on the commit: `github-actions[bot]` in the author column is a symptom, and the same commit starts runs when an App or a PAT pushes it. Debugging a PR with no checks therefore means asking which token pushed, not who the commit says wrote it. Left that way, the PR was mergeable only through the ruleset's admin bypass, so the first release of this catalog would have published with no CI having run on it.
- **The branch ruleset requires one approving review and dismisses stale reviews on push**, against a CODEOWNERS that names a single user. It required a code-owner review as well until this decision retired that rule: the maintainer's own PRs merge through the admin bypass, so in practice the requirement bound only bot-authored PRs — and there, the second platform rule turns it into a demand that automation hold a human's standing credential.
- **Both Dependabot workflows mutate PR state.** `dependabot-auto-merge.yaml` approves and arms auto-merge, and `dependabot-reconciler.yaml` updates branches and re-arms, so both need an identity whose approvals count and whose events fire workflows. Both are dormant behind the `DEPENDABOT_AUTOMERGE_ENABLED` variable until the credentials and settings they need are provisioned.
- **The reconciler depends on the suppression rule from the other side.** It updates a PR's branch and then relies on the resulting `synchronize` event to re-run the policy workflow — true for an App token or a PAT, false under `GITHUB_TOKEN`, and the reason the reconciler can never fall back to the default token.

## Decision

### The rule

| You need | Use | Why |
| --- | --- | --- |
| The default — anything that need not trigger downstream workflows or satisfy code-owner review | **`GITHUB_TOKEN`** | Auto-rotated, no setup, no secret to leak; scope it per job with `permissions:` |
| To **trigger downstream workflows** — a push, PR, review, or Release that must re-run or unblock other gates — or any scoped, rotatable, non-human automation identity | A **GitHub App**, minting a short-lived token per run with `actions/create-github-app-token` from its `client-id` and private key | App-authored events fire other workflows and App approvals count toward a required review count; the App consumes no seat, is permissioned centrally, and outlives any contributor |
| To **satisfy `require_code_owner_review`**, or otherwise act as a specific human | A **fine-grained PAT owned by that human**, minimum scope | CODEOWNERS accepts only users and teams, so an App's approval never counts as a code-owner review — the token's owner must be a code owner for the changed paths and hold the repository access an approval requires |

The three are complementary rather than alternatives, and this repository exercises only the first two: rather than hold a standing human credential for the one rule an App cannot satisfy, the ruleset retired that rule.

### What each workflow uses today

| Workflow | Identity | Verdict |
| --- | --- | --- |
| `action-pins`, `change-intent`, `codeql`, `description-eval`, `lint`, `scorecard`, `tests` | `GITHUB_TOKEN`, read-only floor with per-job elevation | Correct — none of them authors an event. `codeql` does write, elevating `security-events: write` to upload findings, which cascades nothing; `scorecard` elevates the same scope for its SARIF upload plus `id-token: write`, an OIDC proof of repository identity for publishing to the public Scorecard API — a grant on the OIDC provider's side, not on this repository, and it starts nothing here either |
| `release-please` (the release-please step) | The `oss-release-bot` App, a token minted per run from `OSS_RELEASE_BOT_CLIENT_ID` and `OSS_RELEASE_BOT_PRIVATE_KEY` | Correct — it pushes the release branch and opens the PR, and those App-authored events re-run the required checks |
| `release-please` (`bundle`, `catalog-publish`, `catalog-preview`) | `GITHUB_TOKEN` | Correct — uploading release assets need not cascade, and `catalog-preview` is the read-only dry run. The `bundle` job lives inside the release workflow precisely so it does not depend on a Release event that the default token cannot produce |
| `dependabot-auto-merge` (approve, arm, disarm) | The `oss-automation-bot` App, a token minted per run from `OSS_AUTOMATION_BOT_CLIENT_ID` and `OSS_AUTOMATION_BOT_PRIVATE_KEY` in the Dependabot secret store; `GITHUB_TOKEN` for the metadata read | Correct — the App's approval satisfies the one-review requirement, its events fire workflows, and reading update metadata needs nothing more than the default |
| `dependabot-reconciler` (update-branch, re-arm) | The `oss-automation-bot` App, the same `OSS_AUTOMATION_BOT_CLIENT_ID` and `OSS_AUTOMATION_BOT_PRIVATE_KEY` pair read from the Actions secret store | Correct — a push an App should make, and the `synchronize` events it causes re-run the policy workflow |

### release-please acts as the oss-release-bot App

One App, installed on this repository, permissioned to Contents: write and Pull requests: write — the two scopes the `release-please` job used to elevate the default token to, so the App inherits a proven set rather than a guessed one — with its client ID and private key held as `OSS_RELEASE_BOT_CLIENT_ID` and `OSS_RELEASE_BOT_PRIVATE_KEY` in the Actions secret store and a token minted per run with `actions/create-github-app-token`. The action's `client-id` input is used rather than `app-id`, which upstream still accepts as legacy but no longer recommends. The job itself keeps the read-only floor: the App token carries the write access, so nothing elevates the default token.

A workflow that mints a token from absent secrets fails the next release run rather than degrading, so the provisioning order is fixed: install the App and add the two secrets before this wiring's first run on `main`.

### The Dependabot flow acts as the oss-automation-bot App, and the ruleset lets it

A second App, installed on this repository with the same Contents: write and Pull requests: write set, approves eligible Dependabot updates, arms squash auto-merge, disarms on a veto label, and reconciles dropped events. Its client ID and private key live as `OSS_AUTOMATION_BOT_CLIENT_ID` and `OSS_AUTOMATION_BOT_PRIVATE_KEY` in **both** secret stores: the policy workflow runs on Dependabot-authored `pull_request` events and reads the Dependabot store, while the reconciler runs on schedule, push, and `workflow_run` and reads the Actions store. Two Apps rather than one keeps the release credential and the approval credential separately revocable.

An App's approval can never satisfy `require_code_owner_review`, so the Default branch ruleset drops that requirement and keeps everything else: one approving review, the required status checks, stale-review dismissal, and thread resolution. What the code-owner rule was protecting survives it — the maintainer's own PRs merge through the admin bypass either way, so the rule bound only bot PRs, and for those the policy workflow's eligibility gate refuses to approve major and privileged-action updates, which therefore still wait for the one human review the ruleset does require.

## Consequences

- **The bot exemptions survive the identity change without an edit.** The PR-title and commit-style gates waive by shape rather than by name — a login matching `[bot]$` or `-bot$`, an author email matching `[bot]@users.noreply.github.com` — and an App's login and commit email both take that form, so nothing keyed to a literal string exists to break. What the change does **not** do is relabel the pull request that already exists: authorship is fixed at creation, so [#45](https://github.com/milanhorvatovic/ai-hub/pull/45) keeps `github-actions[bot]` as its author even once release-please updates it under the App, and it ends up carrying both identities — a bot-shaped author with App-authored commits. Only a release PR opened after the switch has the App as its author. Both states are waived, which is the argument for matching shape rather than maintaining a list of names.
- **The automation App's credentials must live in two stores.** The Actions and Dependabot secret stores are isolated, and a Dependabot-triggered run cannot read Actions secrets. `dependabot-auto-merge` runs on a Dependabot-authored `pull_request` event and reads `OSS_AUTOMATION_BOT_CLIENT_ID` and `OSS_AUTOMATION_BOT_PRIVATE_KEY` from the Dependabot store; the reconciler runs on schedule and `workflow_run` and reads the same pair from the Actions store.
- **Every recompute of the release PR dismisses and re-runs its approval and checks.** The ruleset dismisses stale approvals on push, and release-please recomputes its PR on every merge to `main`, so each recompute costs both a re-run and a re-approval. The release PR wants merging promptly after it is approved, not held open.
- **The reason `bundle` is a job rather than its own workflow expires.** It was structured that way because a `GITHUB_TOKEN`-created Release does not trigger a `release:`-triggered workflow. An App-created Release does. There is no reason to restructure it, but the constraint is gone and should not be cited as one.
- **Least privilege stays explicit.** Each App is scoped to Contents and Pull requests write, and every workflow keeps its read-only `permissions:` floor — the only jobs elevating the default token are the two that upload release artifacts. What no longer exists is a standing **human** credential: the App private keys are still long-lived secrets able to mint installation tokens, so rotation discipline remains — but each is scoped to its App's two permissions, reads as the App in every audit trail, and is revoked centrally by rotating the key or uninstalling the App.
- **One App can back several repositories.** Splitting per repository is justified by blast radius, not by default.

## Alternatives considered

- **A PAT for release-please.** It would trigger the checks, since PAT-authored events are not suppressed, and needs no App. Rejected: it ties the release path to one person's account, expires on a schedule, consumes a seat, and makes every release action read as that human's.
- **A code-owner PAT for the Dependabot approvals.** The design this decision replaced: a fine-grained PAT satisfying the ruleset's code-owner review, held as `CODEOWNER_APPROVER_TOKEN` in both secret stores. It worked, but only by keeping a human credential standing forever, with every failure mode of the release-please PAT plus a wider blast radius — a token that can approve and merge as the code owner. Rejected once the code-owner requirement itself was on the table: the rule added nothing the eligibility gate and the one-review requirement do not already provide.
- **Keep `GITHUB_TOKEN` and accept the admin bypass.** Cheapest, and honest if written down. Rejected because it makes the required-check list a label rather than a guarantee on exactly the pull request that publishes signed artifacts to consumers.
- **A separate workflow, on schedule or dispatch, to run the checks against the release branch.** It would rebuild the check matrix in a second place, and its results would attach to a branch rather than to the PR, so the ruleset would still see nothing.
- **`pull_request_target`.** Does not apply: the problem is not which context the workflow runs in but that no pull-request event is emitted at all.
