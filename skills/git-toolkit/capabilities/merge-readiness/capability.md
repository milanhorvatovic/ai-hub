---
name: merge-readiness
description: >
  Pre-merge gate check for a pull request — verifies CI checks are green,
  required approvals are in place, no merge conflicts exist, the PR
  description is in sync with the branch, no WIP commits remain, and the
  repo's branch-protection rules are satisfied. Outputs a structured
  READY / PARTIALLY-READY / NOT-READY verdict with a per-gate status table
  (PARTIALLY-READY = all gates pass but one or more carry warnings) and what
  to fix next. Never merges automatically. Triggers when the user asks "is this
  PR ready to merge", "what's blocking merge", "can I ship this", or
  before invoking merge-execute.
---

# merge-readiness capability

Checks all the gates that should be green before merging, and reports go/no-go.

## Input guards

- **Forge detection** — run `git remote get-url origin` and classify per `../../references/forge-adapters.md`. Surface `forge=<x>; capability assumes GitHub gh by default` in the proposal preamble. On non-GitHub remotes (GitLab / Codeberg / Bitbucket), follow the degrade path in `forge-adapters.md` — gate semantics (CI status, approvals, mergeability, threads) map but the API shape differs.
- Resolve target PR per `pr-description-sync`'s Inputs (PR number/URL provided, OR `gh pr list --head <branch>`).
- If `state ∈ {MERGED, CLOSED}` → refuse (already merged or closed).
- If `author.login` matches a pattern in `../../references/bot-signatures.md` → mention but proceed. This is the deliberate read-only/informational carve-out from the router's bot-exemption rule (see `../../SKILL.md` Principles): merge-readiness reports a verdict rather than rewriting bot-controlled content, so it runs on bot PRs instead of skipping.
- `gh` auth required — on failure, tell the user to `gh auth login`.

## Workflow

### 0. Rule catalog

Gate-shaped findings emitted alongside the READY / NOT-READY verdict (e.g., when a stale-description or unfilled-template smell blocks readiness) use the kebab-case rule ids from `../../references/commit-smells.md` so the report can be parsed alongside other capabilities' REVIEW output. Gates themselves (CI status, approvals, mergeability) are not catalog rules and stay named as they are.

### 1. Fetch PR metadata

```
gh pr view <num> --json number,url,title,body,baseRefName,headRefName,headRefOid,\
isDraft,state,mergeable,mergeStateStatus,reviewDecision,latestReviews,\
statusCheckRollup,additions,deletions,changedFiles,isCrossRepository
```

### 2. Run gate checks

| Gate | Check | Pass / Fail / Warn |
|---|---|---|
| **Not draft** | `isDraft == false` | Fail if draft; suggest `gh pr ready <num>` |
| **State** | `state == OPEN` | Fail otherwise |
| **CI checks** | All required checks in `statusCheckRollup` pass: `conclusion ∈ {SUCCESS, NEUTRAL}` (NEUTRAL = pass-with-caveats, consistent with `pr-checks-summary`). `SKIPPED` is OK; pending → Warn; failure → Fail. Treat a check as required when `isRequired` is true (GraphQL) or it appears in the base branch protection's required-checks list; optional-check failures → Warn, not Fail | List failing checks by name |
| **Mergeable** | `mergeable == MERGEABLE` AND `mergeStateStatus ∈ {CLEAN, HAS_HOOKS, UNSTABLE}` | Fail on `CONFLICTING`, `DIRTY`, `BLOCKED`, `BEHIND` |
| **Approvals** | `reviewDecision == APPROVED` | Fail on `REVIEW_REQUIRED` or `CHANGES_REQUESTED` |
| **No unresolved threads** | GraphQL `pullRequest.reviewThreads { isResolved }` (REST `pulls/{n}/comments` doesn't expose resolution state) — see `../pr-conversation-resolve/capability.md` step 1 for the canonical query | Warn (not fail) — some teams allow merge with open threads |
| **No WIP commits** | `git log --no-merges <base>..HEAD --pretty='%s'` — check for `WIP`/`wip`/`[WIP]`/`fixup!`/`squash!` | Fail; redirect to `rebase-cleanup` |
| **Description in sync** | Run a light version of `pr-description-sync` workflow (does body claim work that's still in the diff?) | Warn if MINOR-UPDATE; Fail if MAJOR-REWRITE or HANDOFF-TO-WRITE |
| **No outdated PR** | `headRefOid` matches the SHA the latest review was against (best-effort) | Warn if reviewers approved a different SHA |
| **Branch-protection rules satisfied** | `gh api repos/{o}/{r}/branches/<base>/protection` (best-effort; requires permissions) | Mention rules that are configured |
| **No release branch lockdown** | Check `CONTRIBUTING.md` or repo notes for freeze periods | Warn (manual; hard to detect) |

### 3. Compute verdict

- **READY** — All gates pass with no warnings.
- **PARTIALLY-READY** — All gates pass but one or more carry warnings; safe to merge with explicit caveat.
- **NOT-READY** — Any gate fails.

### 4. Output

```
Verdict: NOT-READY for PR #42

Gate checks:

| Gate                  | Status  | Detail |
|-----------------------|---------|--------|
| Not draft             | ✓ PASS  | |
| State                 | ✓ PASS  | OPEN |
| CI checks             | ✗ FAIL  | 2 failing: `test (3.11)`, `lint` |
| Mergeable             | ✓ PASS  | CLEAN |
| Approvals             | ✗ FAIL  | REVIEW_REQUIRED (1 of 2 approvals) |
| No unresolved threads | ⚠ WARN  | 3 open threads in src/auth/refresh.py |
| No WIP commits        | ✓ PASS  | |
| Description in sync   | ⚠ WARN  | MINOR-UPDATE: "added retry logic" claim is partial |
| Outdated PR           | ✓ PASS  | |
| Branch protection     | ✓ PASS  | requires 2 approvals, CI green |

Next steps:
  - Fix CI: `gh pr checks 42 --watch` then debug failing checks
  - Request review from second approver (suggested: @api-team via CODEOWNERS)
  - Address open threads (or invoke pr-conversation-resolve to draft responses)
  - Optionally: invoke pr-description-sync to apply the MINOR-UPDATE
```

For PASS or PARTIAL, also note what the user would run to merge:

```
When ready, merge with:
  (see the merge-execute capability for the canonical command)
```

## Edge cases

- **Auto-merge enabled** — surface as a passing gate; note that auto-merge will fire when remaining gates pass.
- **Required checks list empty** — repo doesn't enforce any required checks; warn that gates are weak.
- **Cross-repo PR (fork)** — branch protection on the BASE repo, not the fork. Same checks apply.
- **Squash-with-`PR_BODY` repo** — when description is `NOT-IN-SYNC`, severity is higher (body becomes commit message); upgrade Warn → Fail.
- **Repo allows admin merge** — never suggest using admin override; that's an explicit user decision.

## Anti-patterns

- Don't merge automatically; pair with `merge-execute` for the apply command.
- Don't downgrade FAIL gates to WARN to make the verdict look better — accuracy over optimism.
- Don't suggest force-pushing to "fix" failed gates (e.g. squashing WIPs via rebase) without going through `rebase-cleanup` for proper analysis.
- Don't fire if the user just wants to merge — that's `merge-execute`. This capability is a check, not an action.
- Don't run the full `pr-description-sync` workflow inline — do a lightweight check and surface "run pr-description-sync for details" if MINOR/MAJOR.
