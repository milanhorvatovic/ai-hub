# Worked example: one change, every capability

Load this when you want to see how the skill's capabilities chain across a single change's lifecycle, from "I just started work" to "merged". The example is fictional but realistic; substitute your own change for each step.

## The scenario

You discover that the upload queue in a Node.js service has no retry on transient network failures, and uploads silently fail when the storage backend hiccups. You decide to add an exponential-backoff retry with a max of 3 attempts. The work spans two files: `src/upload/queue.js` (the retry logic) and `src/upload/queue.test.js` (the test).

Throughout the walkthrough, capabilities **propose** and you **apply** — no capability ever runs the state-changing command for you.

## Step 1 — `branch-name` (git-side)

You start with the change idea, no branch yet. Trigger: "propose a branch name for a retry fix in the upload queue".

Capability output:

```
Repo prefix convention: detected `fix/` for bug fixes from last 20 branches (90% match).

Proposed branch names (in order of fit):
  1. fix/upload-queue-retry              [recommended — concise, matches convention]
  2. fix/upload-queue-transient-failures [more specific, slightly long]
  3. fix/queue-retry                     [shorter; loses the "upload" scope]

Create with:
  git checkout -b fix/upload-queue-retry
```

You run option 1.

## Step 2 — `commit-message` WRITE mode (git-side, optional gh enrichment)

You implement the retry, stage `src/upload/queue.js`. Trigger: "write a commit message for the staged changes".

The capability runs the workflow from `commit-message/capability.md`:

1. Reads `git diff --cached` — sees the retry loop, the timeout constant, the import of a backoff helper. SPLIT's partition analysis runs here, as it does on every commit: one file, one concern, so the answer is N=1 and the walkthrough never hears about it. That silence is the designed behaviour, not an omission from this example.
2. Reads `CLAUDE.md` / `CONTRIBUTING.md` / `.commitlintrc*` — let's say the repo uses Conventional Commits (detected via `.commitlintrc.json` with `@commitlint/config-conventional`).
3. Samples last 20 commits to confirm the convention is live.
4. Drafts the subject + body.

Capability output:

```
Inferred conventions: conventional-commits (commitlint config present), imperative mood, flowing-paragraph bodies (last 20 commit bodies single-line per paragraph).

Proposed commit message:

fix(upload): retry transient failures up to 3 times with backoff

The upload queue dropped uploads silently when the storage backend returned a transient 5xx or a connection reset. Adds an exponential-backoff retry (250ms / 500ms / 1000ms) capped at 3 attempts; permanent errors (4xx) still fail fast without retry. The retry counter is logged at INFO so operators can see hot spots.

Apply with:
  git commit -F - <<'EOF'
  fix(upload): retry transient failures up to 3 times with backoff

  The upload queue dropped uploads silently when the storage backend returned a transient 5xx or a connection reset. Adds an exponential-backoff retry (250ms / 500ms / 1000ms) capped at 3 attempts; permanent errors (4xx) still fail fast without retry. The retry counter is logged at INFO so operators can see hot spots.
  EOF
```

You apply.

## Step 3 — `commit-message` WRITE again (second commit)

You stage `src/upload/queue.test.js`. Trigger: same.

```
Proposed commit message:

test(upload): cover the retry path with stubbed transient failures

Adds three test cases against the retry: a single transient failure that succeeds on attempt 2, three transient failures that exhaust the budget and surface the error, and a 404 that fails fast without retry. Uses the existing nock fixture pattern from the rest of the upload suite.

Apply with: <command>
```

## Step 4 — mid-work `commit-fixup` (git-side)

A reviewer (or you) notices the backoff helper import is unused in the test. You fix it, stage. Trigger: "is this a fixup for an earlier commit?".

```
Likely fixup target: 9a3f2c1 "test(upload): cover the retry path with stubbed transient failures" (file overlap 100%, time delta 12 minutes).

Apply with:
  git commit --fixup 9a3f2c1
  # later, before review:
  git rebase --autosquash --interactive origin/main
```

You apply the fixup commit; the rebase happens later in Step 6.

## Step 5 — `commit-message` REVIEW mode (git-side, gh enrichment)

You've written 3 commits + 1 fixup. Before opening the PR, you audit. Trigger: "review my commits on this branch".

Capability output uses the schema from `review-output.md`:

```
Reviewed: 4 commits in fix/upload-queue-retry vs origin/main.

| Rule | Result | Details |
|---|---|---|
| Conventional-commits prefix | PASS | all commits use fix/test |
| Imperative mood | PASS | "retry", "cover", "wire" |
| ≤72 char subjects | PASS | longest is 65 |
| No trailing period | PASS | |
| Body flowing | PASS | paragraphs are single-line per commit |
| Trailers preserved | N/A | no trailers present |
| Force-Push Impact | N/A | branch never pushed; impact = none |

COMPLIANT
```

## Step 6 — `rebase-cleanup` (git-side)

You decide to autosquash the fixup before pushing. Trigger: "clean up the commit history".

```
Stacked Dependents: none.
Force-Push Impact: none (never pushed).

Proposed rebase plan:
  pick   c1a2b3d  fix(upload): retry transient failures up to 3 times with backoff
  pick   9a3f2c1  test(upload): cover the retry path with stubbed transient failures
  fixup  f5e4d2a  fixup! test(upload): cover the retry path with stubbed transient failures
  pick   2b8c4e9  docs(upload): note the retry behavior in README

Result: 3 commits.

Apply with:
  git rebase --autosquash --interactive origin/main
```

You apply. History collapses to 3 commits.

## Step 7 — first push, open PR

```
git push -u origin fix/upload-queue-retry
gh pr create --draft  # creates the PR (#729 in this walkthrough) with no body
```

## Step 8 — `pr-description` WRITE mode (forge-side)

The PR has no body, so the capability's mode detection picks WRITE. Trigger: "write a PR description".

Capability output:

```
PR template detected: .github/PULL_REQUEST_TEMPLATE.md with sections "Summary" / "Why" / "Test plan" / "Risk".

Proposed PR body:

## Summary
Adds exponential-backoff retry to the upload queue for transient (5xx / connection reset) failures, capped at 3 attempts. Permanent errors (4xx) fail fast as before.

## Why
Uploads silently failed during a 20-minute backend incident last week. Reads of `queue_drops_total` confirm the silent loss; the metric was already in place but had no alarm. Retry is the cheaper of the two mitigations (alarm + retry both planned; retry first because it removes the loss, the alarm only surfaces it).

## Test plan
- [x] Unit: three new cases in `queue.test.js` covering recover-on-2, exhaust-on-3, fail-fast-on-4xx.
- [x] Local: ran against a fault-injection wrapper around the storage SDK; observed 2/3 successes on simulated 503s, 100% failures on simulated 404.
- [ ] Staging: deploy and watch `upload_retry_total` for the first hour.

## Risk
Retry doubles the load on the backend during incidents (up to 3x for a 100% failure rate). The 1s cap and 3-attempt budget keep amplification bounded. If the backend is genuinely down for >3s, behavior is unchanged from today (loss).

Apply with:
  gh pr edit 729 --body-file <mktemp-path>
```

`<mktemp-path>` — here and in every later apply command — stands for the temp file the proposing capability writes alongside the inline proposal (created with `mktemp`; the capability's real output prints the actual path).

You apply.

## Step 9 — `pr-link-issues` (forge-side)

Trigger: "find issues this PR addresses".

```
Detected issue refs in branch/commits/body: none.

Searched recent issues for keywords "upload retry", "queue drops":
  - #482  "Uploads silently fail during storage incident" (matches 6 keywords; diff covers the symptom)
  - #491  "Add retry to upload queue"                    (matches 9 keywords; diff implements the proposal)

Proposed addition to PR body:

  Closes #491
  Refs #482

Apply with: gh pr edit 729 --body-file <mktemp-path>
```

You apply.

## Step 10 — `pr-description` SYNC mode (forge-side)

A reviewer asks for changes. You add a follow-up commit that lowers the max attempts from 3 to 2 based on backend load testing. The body is substantive now, so mode detection picks SYNC. Trigger: "is the PR body still accurate?".

```
Divergence classification: MINOR-UPDATE.

Stale claims in current body:
  - "capped at 3 attempts" → diff now shows 2.
  - "(250ms / 500ms / 1000ms)" → diff now shows (250ms / 500ms).
  - Test-plan checkbox "exhaust-on-3" → renamed to "exhaust-on-2".

Proposed body diff:
  -capped at 3 attempts
  +capped at 2 attempts
  -(250ms / 500ms / 1000ms)
  +(250ms / 500ms)
  -[x] Unit: three new cases ... exhaust-on-3 ...
  +[x] Unit: three new cases ... exhaust-on-2 ...

Apply with: gh pr edit 729 --body-file <mktemp-path>
```

## Step 11 — `pr-checks-summary` (forge-side)

A CI check goes red. Trigger: "what failed in CI?".

```
Failing checks: 1 of 7

  ❌ unit-tests (Node 20)
     Log excerpt:
       FAIL src/upload/queue.test.js
         retry > exhausts the budget and surfaces the error
         AssertionError: expected 2 calls, got 3
     Likely cause: max-attempts changed from 3 to 2; test still expects 3.
     Reproduce locally: npm test -- src/upload/queue.test.js

Fix proposal: Update the `exhausts the budget` test to assert 2 calls instead of 3.
```

You fix, push.

## Step 12 — `pr-conversation-resolve` (forge-side)

Three review threads exist. Trigger: "summarize unresolved threads".

```
Unresolved threads: 3

  1. @reviewer-1 on src/upload/queue.js:42
     "Should we cap the retry budget per upload OR per queue session?"
     → Addressed by commit a8c2f1d which added the per-upload cap. Propose:
       Response: "Per-upload — see a8c2f1d. Per-queue would be useful for the
       fan-in case (#502) but is out of scope here."
       After reply: gh pr review --comment --body ... ; gh api ... resolve

  2. @reviewer-2 on README change
     "Add a metric to track retry exhaustion?"
     → Not yet addressed. Propose:
       Response: "Good catch — opened #503 to add upload_retry_exhausted_total
       in a follow-up since it touches the metrics-conventions ADR."
       (don't auto-resolve; #503 is the closure path)

  3. @reviewer-3 on package.json
     "Why did the package-lock change?"
     → Inspection shows transitive bump in axios from 1.5.1 to 1.5.2 (security
       patch, unrelated to this PR). Propose:
       Response: "Transitive security bump in axios; unrelated to this change
       but caught by `npm ci`. Happy to split if you'd prefer."
       (offer split; don't auto-resolve)

The skill never posts; you choose which to send.
```

## Step 13 — `merge-readiness` (forge-side)

Trigger: "is the PR ready to merge?".

```
PR: #729 fix(upload): retry transient failures

| Gate | Status | Detail |
|---|---|---|
| CI checks | ✅ PASS | 7/7 green |
| Approvals | ✅ PASS | 2/2 required |
| Mergeable | ✅ CLEAN | no conflict |
| Unresolved threads | ⚠️  WARN | 1 (reviewer-3, axios bump — see pr-conversation-resolve) |
| Draft state | ✅ ready | |
| WIP commits | ✅ none | |
| Description in sync | ✅ IN-SYNC | last sync check passed |

Verdict: PARTIALLY-READY (all gates pass; 1 warn on unresolved thread).

Resolution: either close @reviewer-3's thread with a follow-up answer or accept the
risk and merge over it (your call) — PARTIALLY-READY means it's safe to merge with
an explicit caveat.
```

## Step 14 — `merge-execute` (forge-side)

After @reviewer-3's thread is resolved, you re-run `merge-readiness` (now READY). Trigger: "what's the merge command?".

```
Repo merge policy: squash-only (detected via gh api repos/<owner>/<repo>).

Apply with:
  gh pr merge --squash --delete-branch
```

Optional `--auto` flag if you want to set merge-on-green for a still-pending check.

## Step 15 — `release-notes` (git-side, optional gh enrichment, when cutting a release)

After a few PRs have landed, you tag a release. Trigger: "draft release notes for v2.4.0".

```
Detected: grouping = conventional-commits (13/14 subjects match CC); changelog style = none
forge=github
Range: v2.3.7..HEAD
Commits: 14 (after squash-merges)

## Features
- (none)

## Fixes
- fix(upload): retry transient failures up to 2 times with backoff (#729, @author)
- fix(api): return 422 not 500 for malformed JSON bodies (#734, @reviewer-1)

## Docs
- docs(upload): note the retry behavior in README (#729, @author)

## Chore
- chore(deps): bump axios 1.5.1 -> 1.5.2 (security patch, transitively via #729)

Contributors: @author, @reviewer-1, @reviewer-2, @reviewer-3

Apply with: gh release create v2.4.0 --notes-file <mktemp-path>
```

## Capabilities and modes not used in this walkthrough

- **`worktree-setup`** — useful when working on multiple branches in parallel; not needed for a single change.
- **`commit-message` AMEND mode** — useful for fixing only the wording of HEAD (no diff change); not needed here since the messages were good on first draft.
- **`commit-message` SPLIT mode, in its series form** — it ran silently at Step 2 and returned one commit. A pile mixing the retry fix with, say, an unrelated CI bump would have been proposed as an ordered two-commit series instead.
- **`commit-body-reflow`** — useful when switching style across many commits at once; not needed for a 3-commit PR.

Each is documented in its own `capabilities/<name>/capability.md`.

## Takeaways

- Capabilities chain naturally but never auto-trigger each other; the user invokes each.
- The git-side / forge-side boundary is visible at every step (capabilities labeled `[git-side]` work without a forge CLI; the forge-side steps show the GitHub `gh` worked example).
- Every state-changing command (`commit`, `rebase`, `push`, `gh pr edit`, `gh pr merge`) is proposed and applied by the user, never run automatically.
- Trailers are absent throughout — no `Co-authored-by`, no `Signed-off-by`, unless the user asked.
