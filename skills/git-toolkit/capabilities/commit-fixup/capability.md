---
name: commit-fixup
description: >
  Detects which prior commit the currently-staged changes belong to and
  proposes a git commit --fixup <sha> command, optionally followed by git
  rebase -i --autosquash. Inspects staged files, matches against recent
  commits that touched the same files, scores candidates, and surfaces the
  best target. Never amends or commits automatically. Triggers when the
  user asks to "make this a fixup", "amend into the right commit", "fix
  the previous commit", or "fixup a typo I just noticed".
---

# commit-fixup capability

Detects which prior commit the staged changes belong to and proposes a fixup commit.

## Input guards

- Must be inside a git repo.
- Must have staged changes: `git diff --cached --name-only` non-empty. If not, stop with "stage your fix first".
- Branch must have ≥1 commit (need a target candidate). If first commit, stop with "no prior commits to fix up".

## Workflow

### 1. Gather staged files

```
git diff --cached --name-only
```

### 2. Score candidate target commits

For each staged file, find recent commits that touched it:

```
git log --follow --pretty=format:'%h %s' -10 -- <file>
```

Aggregate scores across all staged files:

| Signal | Weight |
|---|---|
| Commit touched the same file → +5 per file |
| Commit touched the same hunk lines (use `git log -L`) → +10 |
| Commit is in the current branch's range (`<base>..HEAD`) → +3 (favors current-branch targets over historical) |
| Commit subject mentions the same scope/area (heuristic) → +2 |
| Commit is older than 30 days → -5 (stale targets are usually wrong) |
| Commit is by a different author than current user | -2 (cross-author fixups are unusual without coordination) |
| Commit is a merge commit | exclude entirely |

Top-scored commit is the proposed target.

### 3. Confidence check

If the top score is significantly higher than the runner-up (gap ≥ 5): high confidence — propose a single target.

If two or more candidates are close: surface all top candidates, let the user pick.

If no candidate scores above a floor (say, 3): the staged change isn't a fixup — suggest a regular commit instead (`git commit -m '...'` via the `commit-message` capability) and stop.

### 4. Detect if target is pushed and reviewed

```
git branch -r --contains <target>  # non-empty → the target commit is on a remote branch
```

`git branch -r --contains` reads local remote-tracking refs, which can be stale without a `git fetch`; run `git fetch` first if they may be out of date, otherwise a pushed target can read as not-pushed and silently skip the rebase-impact warning.

If yes, AND a PR exists with reviews: emit the rebase-impact warning (same as `rebase-cleanup`'s force-push warning). The fixup is fine to create; the eventual `git rebase --autosquash` is what's destructive.

### 5. Output

```
Proposed fixup target:
  abc1234  feat(auth): add token-refresh queue   (touches src/auth/refresh.py — same as staged)

  Confidence: high (next candidate scored 8 vs 23)

Apply with:
  git commit --fixup abc1234

Later, to squash into the target:
  git rebase -i --autosquash <base>

WARN: target abc1234 is on origin/feature/auth-refresh and PR #42 has 2 reviews.
      The fixup itself is safe; the eventual rebase --autosquash will require
      force-push and may disrupt reviewers.
```

For multi-candidate output, list each with score and let the user pick:

```
Top candidates:
  abc1234  fix(auth): handle expired tokens  (score: 23)
  def5678  refactor(auth): extract refresh   (score: 21)

Pick one:
  git commit --fixup abc1234
  git commit --fixup def5678
```

## Edge cases

- **Staged changes touch files no recent commit touched** — no candidate; suggest regular commit instead.
- **Staged changes are pure formatting on a fresh file** — the file's first commit is the target. Score appropriately.
- **Fixup target is itself a fixup** — fine; `--autosquash` handles chains. Surface but don't warn.
- **Multiple staged files with disjoint histories** — likely two separate logical changes; suggest splitting and committing separately, not a single fixup.
- **Target commit is on `main` / default branch** — refuse; fixups on shared history are dangerous. Suggest a follow-up commit instead.

## Anti-patterns

- Don't run `git commit --fixup` automatically — surface the command.
- Don't propose a fixup target when the change is logically distinct from prior commits — suggest a regular commit instead.
- Don't auto-run `git rebase -i --autosquash` — that's a separate user action with its own risks.
- Don't propose fixups against commits on the default branch (`main`/`master`/`develop`) — shared history.
- Don't include `git push --force` in the suggested follow-up — the user must opt into force-push explicitly.
- Don't add `Co-authored-by:` or any trailer when creating the fixup commit — the fixup inherits the target's trailers automatically on squash.
