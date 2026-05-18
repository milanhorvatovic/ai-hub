---
name: commit-amend-message
description: >
  Amends only the message (subject and/or body) of the most recent commit
  without touching the staged diff. Validates the new message against the
  repo's commit format conventions and warns when HEAD has been pushed.
  Distinct from rebase-cleanup, which handles ranges and full rewrites.
  Never amends automatically. Triggers when the user asks to "fix the last
  commit message", "reword HEAD", "amend the message" (not the diff), "the
  subject is wrong on the last commit", or "fix a typo in my commit message".
---

# commit-amend-message capability

Amends only the message of HEAD; leaves the staged diff untouched.

## Input guards

- Must be inside a git repo.
- Must have ≥1 commit: `git rev-list --count HEAD` ≥ 1.
- Check if HEAD has been pushed: `git rev-list HEAD --remotes | head -1` — emit a **Force-Push Impact** block (per `../../capabilities/commit-message/capability.md` Step 5: none / mild / high) before any proposal. If impact is `high` (PR has review comments anchored to HEAD's SHA), surface every anchored thread URL and require explicit user opt-in before showing the amended message.
- This capability touches the message only. If the user actually wants to add or change the diff, redirect them to `git commit --amend` directly (with staged changes) or to `rebase-cleanup` for non-HEAD commits.

## Workflow

### 1. Read current message

```
git log -1 --format='%s%n%n%b'
```

Parse into subject + body + trailers. Preserve trailers verbatim per `../../references/trailer-semantics.md`.

### 2. Determine the new message

Two modes:

**Mode A: user supplied a new message** — use it as-is. Validate format only (see Step 3).

**Mode B: user asked to "fix" / "improve" without supplying text** — apply `../../references/format-conventions.md` rules to the existing message:
- If subject is too long, too generic, or past-tense → propose a rewritten subject.
- If body has a missing `BREAKING CHANGE:` footer for `!`-marked commits → propose adding it.
- If body has restatement of subject in past tense → propose removing.
- Keep all trailers verbatim.

### 3. Validate against format conventions

Apply checks from `../../references/format-conventions.md`:

| Check | Severity |
|---|---|
| Subject length ≤72 | error if >72 |
| Imperative mood | warn (heuristic) |
| No trailing period | error |
| Conventional-commits prefix if repo uses CC | error |
| Body wrap ≤72 (if body present) | warn |
| Blank line after subject | error |
| Secret-pattern scan | error per `../../references/secret-patterns.md` |
| Trailers preserved byte-for-byte | error if reformatted |

If any error-level check fails, fix and re-validate before proposing.

### 4. Output

```
Current HEAD message:
  abc1234  Fixed bug.

Proposed message:
  abc1234  fix(auth): handle expired token in refresh path

  Replace the eager refresh attempt with a guarded check so we don't
  spam the auth provider with refresh calls on every 401.

  Refs: #142

Apply with:
  git commit --amend -m "fix(auth): handle expired token in refresh path" \
    -m "Replace the eager refresh attempt with a guarded check so we don't" \
    -m "spam the auth provider with refresh calls on every 401." \
    -m "Refs: #142"

Or use a file (recommended for multi-paragraph bodies):
  git commit --amend -F <mktemp-path>
```

Write the proposed message to a `mktemp` file AND show inline. Never run `git commit --amend` automatically.

### 5. Pushed-commit warning (when applicable)

```
WARN: HEAD (abc1234) is on origin/<branch>.

Amending requires `git push --force-with-lease origin <branch>`, which:
  - disrupts collaborators with the branch checked out
  - may lose PR review threads tied to the old SHA
  - breaks CI caches and external links to the old SHA

If a PR exists and has reviews, prefer adding a follow-up commit that
fixes the message context, OR coordinate the force-push with reviewers
before applying. The skill will not run force-push on your behalf.
```

## Edge cases

- **HEAD is a merge commit** — amending changes only the merge commit's message, not its parents. Safe but rarely meaningful; warn.
- **HEAD is empty (initial commit)** — fine to amend; no pushed-state concern.
- **User wants to also stage more changes** — redirect: stage first, then they should run `git commit --amend` directly (or `--amend --no-edit` to keep the existing message). This capability is message-only.
- **User wants to amend a NON-HEAD commit** — refuse; redirect to `rebase-cleanup` with the appropriate range.
- **HEAD is signed (GPG/SSH)** — `git commit --amend` re-signs by default. Note this in the output if the existing commit was signed and the user's git config sets `commit.gpgsign true`.

## Anti-patterns

- Don't run `git commit --amend` automatically.
- Don't propose changes to non-HEAD commits — that's `rebase-cleanup`'s job.
- Don't strip or reformat trailers — preserve verbatim per `../../references/trailer-semantics.md`.
- Don't add `Co-Authored-By:` or any trailer the existing message didn't have, unless the user explicitly asks.
- Don't include `git push --force-with-lease` in the suggested command — the user must opt in to the rewrite-history risk.
- Don't propose amending a commit whose subject is fine just to be "cleaner" — only when there's a concrete fix needed.
