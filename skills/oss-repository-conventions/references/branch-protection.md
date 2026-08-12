# Branch & tag protection

How the default branch — and release tags, deployment environments — are guarded. GitHub offers two mechanisms; the audit recognizes both, and settings are always **proposed, never applied**.

## Two mechanisms

- **Classic branch protection** — one rule per branch-name pattern: `gh api repos/{owner}/{repo}/branches/{branch}/protection`.
- **Repository rulesets** (newer) — layerable rules targeting multiple branches/tags, with bypass actor lists and org-level inheritance: `gh api repos/{owner}/{repo}/rulesets`.

Prefer rulesets for new setups; recognize **either** as satisfying a protection check.

## Protections to look for (default branch)

| Protection | Why |
| --- | --- |
| Require a pull request before merging | no direct pushes to the default branch |
| Required approving reviews (≥1; dismiss stale; require code-owner review; require last-push approval) | changes are actually reviewed |
| Require status checks to pass (strict / "up to date") | only green, current code merges |
| Require conversation resolution | no unresolved review threads slip through |
| Require linear history | no merge-commit tangle (pairs with squash/rebase) |
| Require signed commits | history is verifiable — see `commit-signing.md` |
| Block force-push and deletion | history can't be rewritten or the branch removed |
| Restrict who can push / bypass | least privilege on the protected branch |

**Solo-maintainer note:** requiring ≥1 approval blocks a sole maintainer (no one to approve). For solo repos, gate on status checks + block force-push + linear history, and add review requirements when collaborators join. Where automation approves (the pr-autonomy ladder's L2+), a review requirement becomes satisfiable again — but **code-owner** review interacts with automation identity in a way worth deciding deliberately: see `automation-identity.md` § "Code-owner review and automation".

## Required-check context names

The `required status checks` list matches on **context names**, and three registration rules routinely produce a required context that never reports (blocking every merge):

- Contexts register from the **job**, not the workflow: a job `test:` with no `name:` override registers as `test` — never `<workflow> / test`.
- **Matrix** jobs append a parenthesized suffix in declaration order: `test (ubuntu-latest, 3.12)`.
- A job that **calls a reusable workflow** reports as `caller-job / callee-job` — so extracting a job into a reusable workflow silently renames its context, and the ruleset must be updated in the same change.

Never infer a context name: push a PR and read **all** registered names with `gh pr checks <pr> --json name` (not `--required`, which filters to the already-required set and hides exactly the new or renamed context being discovered), copy them exactly into the ruleset, then confirm with `--required` that the list matches.

## Tag protection

Protect release tags (`v*`) from deletion/overwrite with a **tag ruleset** (or legacy tag-protection rules) so a published release can't be silently re-pointed. Pairs with signed tags (`security-policy`).

## Deployment environments

For repos that deploy, GitHub **environment protection rules** (required reviewers, wait timer, allowed branches, environment secrets) gate releases/deploys. Audit when a workflow job declares an `environment:`.

## Merge queue

For high-traffic repos, a **merge queue** re-tests each PR against the latest base before merging, preventing "green-but-stale" merges. A `could`.

## Checking & proposing

Read protection via `gh api .../branches/{default}/protection` and `gh api .../rulesets`; mark protection `unknown` when `gh` is unavailable. The `security-policy` capability owns the payload template (`branch-protection.example.json`) and proposes the `gh` command — never applies it.
