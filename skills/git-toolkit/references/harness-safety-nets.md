# Harness safety nets

Load this when a capability's proposed command is likely to be blocked by an agent-harness classifier (Claude Code's auto-mode classifier, similar guards in other harnesses). The goal is to phrase the proposal so the user sees the full context and intent, not just the bare command — that gives the classifier (and the user) enough signal to evaluate the operation correctly.

## Known classifier triggers

These operations are routinely flagged. The skill does not bypass classifier guards; instead it pre-frames the operation so the user has the context to authorize it explicitly.

| Operation | Common reason flagged | Mitigation |
|---|---|---|
| `git push --force-with-lease` on a branch with reviewers | Destructive to remote state; may overwrite collaborator work. | Use the Force-Push Impact block (commit-message Step 5) to surface anchors and reviewers. Ask for explicit opt-in before showing the push command. |
| `git push --force` (without `--with-lease`) | Strictly worse than `--force-with-lease`. | Never propose. Always use `--force-with-lease`. |
| `git reset --hard` on a branch that has local commits past the target | Drops uncommitted or unpushed work irrecoverably (without reflog). | Confirm the discarded commits' SHAs are recoverable via reflog or backup tag; list what would be lost; ask for opt-in. |
| `git filter-branch` on multiple refs at once | Reads as "mass history rewrite". | Process one branch at a time (see `mass-rewrite.md` per-branch sequencing). |
| `git filter-repo` / `git filter-branch` without backup tags | No recovery path. | Tag each affected branch tip with `pre-rewrite/<branch>` before invoking. |
| `git commit` with a `Co-Authored-By:` trailer naming a fabricated identifier (e.g., a model name with marketing suffixes) | Reads as impersonation / content integrity. | Per `trailer-semantics.md` harness-pressure section, never fabricate attribution. If the user wants a trailer, use their literal text. |
| `git branch -D` on a branch with unmerged commits | Discards work that exists nowhere else. | Check `git merge-base --is-ancestor <branch> <any-other-ref>`; if false, list unmerged commits before proposing the delete. |
| `gh pr merge` on a PR with failing checks or unresolved threads | Bypasses team policy. | Run `merge-readiness` first; only emit `gh pr merge` after a `READY` verdict. |

## Proposal phrasing

When proposing a flagged operation, the capability output should include four parts in order:

1. **Intent** — one sentence stating what the operation accomplishes.
2. **Impact** — one paragraph listing what changes locally and remotely, who is affected, and what is reversible.
3. **Recovery path** — the exact commands to undo, if possible.
4. **The command itself** — never inside a "run this" framing without the prior three parts.

Example:

```
Intent: Republish the rewritten history of update-gitignore to origin so collaborators get the corrected commit messages.

Impact: origin/update-gitignore moves from f902472 to a2a5352 (4 commits with new SHAs). Any reviewer with the branch checked out locally must run `git pull --rebase` next time they fetch. No review comments are anchored to the old SHAs (verified via `gh pr view --json reviews`).

Recovery: `git push --force-with-lease origin pre-rewrite/update-gitignore:update-gitignore` restores the pre-rewrite state from the backup tag (only valid until the backup tag is deleted).

Command:
  git push --force-with-lease origin update-gitignore
```

The user (and any classifier reading the conversation) can now decide with full context.

## What this skill does NOT do

- The skill does not attempt to bypass classifier denials. If a classifier blocks a proposal, the capability surfaces the block, explains why, and lets the user re-authorize, run the command themselves, or add a permission rule to their harness settings.
- The skill does not silence harness warnings (e.g., `FILTER_BRANCH_SQUELCH_WARNING=1` is only set within an already-authorized invocation; the warning is informative for the user even if it does not change behavior).
- The skill does not chain proposals to evade per-command limits. If a multi-step operation must be split, each step has its own intent / impact / recovery framing.
