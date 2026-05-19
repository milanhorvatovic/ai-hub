---
name: rebase-cleanup
description: >
  Analyzes a branch's commits before merge or review and proposes an
  interactive-rebase plan: which commits to pick, squash, fixup, reword,
  drop, or reorder. Detects WIP commits, "address review" commits, fixup!
  /squash! markers, redundant formatting commits, and commits that should
  be merged or reordered. Outputs a rebase todo-list and the apply command —
  never runs the rebase automatically. Warns explicitly when rewriting
  commits that have already been pushed and reviewed. Triggers on "clean
  up my commits", "squash this branch", "prepare branch for merge", "fix
  commit history before review", "tidy commits".
---

# rebase-cleanup capability

Proposes an interactive-rebase plan to clean up a branch's commit history.

## Input guards

- **Resolve base** — PR base via `gh pr view --json baseRefName` if PR exists; else merge-base with `main` / `master` / `develop` (try each, first match wins).
- **≤1 commits in range** → stop with "nothing to clean up."
- **On default branch** → refuse; rebase-cleanup is for feature branches only.
- **Detect pushed commits**: `git rev-list <base>..HEAD` is the full range; `git rev-list <base>..HEAD ^@{u}` returns the *unpushed* commits in that range (reachable from HEAD but not from the branch's upstream), so the pushed set is the complement. Where no upstream is configured, fall back to per-commit `git branch -r --contains <sha>`. If any commit in range is pushed AND the PR has at least one review (`gh pr view --json reviews`) → emit the force-push warning (Step 6) **before** any plan is shown.

## Workflow

### 0. Rule catalog

Classifications in Step 2 and any REVIEW-shaped findings emitted along the way must use the kebab-case rule ids from `../../references/commit-smells.md` (especially `status-marker`, `generic-verb`, `vague-noun`, `repeated-fix`, `manual-revert`, `mixed-scope`). Detection patterns for the catalog's rules drive the classifier; the catalog stays the single source of "things to flag".

### 0b. Rule selectivity (optional `rules:` filter)

Same selectivity mechanism as `../commit-message/capability.md` Step 0b: a comma-separated `rules:` argument scopes classification to a subset of catalog rule ids (e.g. `rules: status-marker,repeated-fix,mixed-scope`). The cleanup plan only proposes actions for commits matching the active rules. Surface the active subset in the plan preamble so the reader knows which classifications were skipped. Useful when a team has agreed that some smells are out of scope for branch-cleanup work.

### 1. Gather commits and bodies

```
git log --no-merges <base>..HEAD --pretty=format:'%h%x09%an%x09%s%x09%P'
```

Per commit, fetch the body:

```
git show --no-patch --format='%h%n%s%n%n%b%n---' <sha>
```

### 2. Classify each commit

| Pattern | Suggested action |
|---|---|
| Subject contains `WIP`, `wip`, `[WIP]`, `TODO`, `XXX`, `temp` | `reword` (propose new subject per `../../references/format-subject.md`) |
| Subject prefix `fixup!` / `squash!` | `fixup` / `squash` into the named target commit (git auto-handles when `--autosquash` is set) |
| Subject is "Address review comments", "Apply review feedback", "PR fixes", or similar generic | `squash` into the most-related prior commit; reword the result to describe WHAT was fixed |
| Subject is `Fix typo`, `Format`, `Run prettier`, `Lint fix` after a real commit on the same files | `fixup` into the prior commit |
| `Revert "X"` followed later by `X` again | `drop` both |
| Identical or near-identical subjects (one is a refinement of the other) | `squash` |
| Subject + body together describe one logical change, not split-reviewable | `pick` (keep as-is) |
| Two commits modify the same file with related intent | Consider `squash`; suggest only if NOT separately reviewable |

### 3. Detect order issues

- Commit B depends on Commit A but appears before it (e.g. uses an import added later) → suggest reorder (move A before B).
- Commit B fixes a bug introduced by Commit A → suggest `squash` (collapse into A so the bug never shipped historically).

### 4. Apply format rules to proposals

For every `reword` and `squash` (which generates a new combined message), draft the new message per `../../references/format-subject.md` (subject) and `../../references/format-body.md` (body):

- Imperative mood, ≤72-char subject
- Conventional-commits prefix if the repo uses them
- Combined body explaining the merged intent, not the sequence of edits
- **Preserve existing trailers verbatim** per `../../references/trailer-semantics.md` — including `Co-authored-by:`, `Signed-off-by:`, etc. **Never add new trailers** as part of cleanup.

### 5. Output

```
Rebase plan for <branch> (N commits → M after cleanup):

Current commits:
  abc1234  WIP: try new parser
  def5678  fix tests
  ghi9012  Address review comments
  jkl3456  Format

Proposed:
  pick    abc1234  → reword to: feat(parser): add streaming JSON reader
  squash  def5678
  fixup   ghi9012  (folded into abc1234)
  fixup   jkl3456

Result (1 commit):
  feat(parser): add streaming JSON reader

  Replace the eager-load JSON parser with a streaming reader so we can
  handle responses larger than RAM. Tests cover the chunked-input path.

To apply manually:
  git rebase -i <base>
  # paste the proposed pick/squash/fixup lines, save, exit
  # at the first reword prompt, paste the proposed message

Or in one shot (uses GIT_SEQUENCE_EDITOR to inject the plan):
  GIT_SEQUENCE_EDITOR='cat > $1 <<EOF
pick abc1234 ...
squash def5678 ...
fixup ghi9012 ...
fixup jkl3456 ...
EOF' git rebase -i <base>
```

For every `reword` action, include the proposed message body inline so the user can paste it into the editor when prompted.

### 6. Force-Push Impact block (when commits are pushed)

Use the shared format from `../../capabilities/commit-message/capability.md` Step 5 — three impact buckets (none / mild / high) keyed on whether the commit is local-only, pushed-without-anchors, or pushed-with-review-anchors. Surface anchored review threads by URL when impact is `high`.

```
Force-Push Impact: <none / mild / high>
  Pushed commits:        <N of M>
  Review anchors at risk: <K> (list URLs if K > 0)
  Required to publish:    <none / git push --force-with-lease / git push --force-with-lease + reviewer coordination>

Rewriting commits on origin/<branch> may:
  - disrupt any reviewer with the branch checked out locally
  - lose review threads tied to specific commit SHAs (anchors detailed above)
  - break bisecting tools and CI caches keyed on commit hashes

The skill will not run force-push; user must opt in explicitly.
```

## Anti-patterns

- Don't run `git rebase -i` automatically — propose the plan; let the user run it.
- Don't suggest squashing commits that are individually reviewable or individually revertable. Multiple small commits is sometimes the right structure (especially for bisecting).
- Don't reword without proposing the new subject per `../../references/format-subject.md` — leaving the user to fill in is a non-answer.
- **Don't add `Co-Authored-By:` or any other trailers when squashing.** Only preserve trailers that were already present in the original commits, byte-for-byte.
- Don't include `git push --force` or `--force-with-lease` in any suggested command — the user must opt into the force-push risk.
- Don't propose changes to merge commits unless the user explicitly asks.
- Don't propose rebasing a branch whose base is itself a feature branch (stacked PR) without warning that rebasing rewrites the SHAs the stacked branch depends on. When dependents exist, emit a **Stacked Dependents** block before any plan: list each dependent branch and the rebase command needed to cascade the fix (`git checkout <dep> && git rebase <this-branch>`), in topological order. See `../../references/mass-rewrite.md` for the full cascade procedure when more than one level is involved.
