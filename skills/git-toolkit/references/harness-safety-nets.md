# Harness safety nets

Load this when a capability's proposed command is likely to be blocked by an agent-harness classifier (Claude Code's auto-mode classifier, similar guards in other harnesses). The goal is to phrase the proposal so the user sees the full context and intent, not just the bare command — that gives the classifier (and the user) enough signal to evaluate the operation correctly.

## Known classifier triggers

These operations are routinely flagged. The skill does not bypass classifier guards; instead it pre-frames the operation so the user has the context to authorize it explicitly.

| Operation | Common reason flagged | Mitigation |
|---|---|---|
| `git push --force-with-lease` on a branch with reviewers | Destructive to remote state; may overwrite collaborator work. | Use the Force-Push Impact block (`force-push-impact.md`) to surface anchors and reviewers. Ask for explicit opt-in before showing the push command. |
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

## Known harnesses

The same operation may be blocked by one harness and pass on another, and the mitigation phrasing differs slightly per harness. A non-exhaustive catalog:

| Harness | Classifier / safety surface | Trailer default | Notes |
|---|---|---|---|
| Claude Code | "auto mode classifier"; per-command permission prompts; settings.json hooks | `Co-Authored-By: Claude <noreply@anthropic.com>` | Most aggressive on mass-rewrite, force-push, and fabricated-attribution. Surfacing intent/impact/recovery before the command typically unblocks. |
| Cursor | YOLO-mode toggle + per-action confirmation | varies by model | Less surface area than Claude Code; force-push to non-main usually passes without prompt. |
| Gemini CLI | sandbox modes + tool allowlist | `Co-Authored-By: Gemini` (configurable) | Sandbox blocks file writes outside cwd; mass-rewrite needs explicit cwd inclusion. |
| GitHub Copilot for CLI | command preview + accept | none by default | Treats every shell invocation as confirm-once; mass operations need batched explicit confirmations. |
| GitHub Copilot Workspace | session-level intent tracking | none | More forgiving on history rewrites within a single "task" boundary. |
| OpenAI Codex (CLI) | per-step confirmation | none by default | Force-push and `git reset --hard` require explicit step approval each time. |
| z.ai GLM CLI | tool-use approval per call | none | Behavior similar to Codex; no aggregate classifier. |
| Kimi (Moonshot) CLI | per-call confirmation | none | Same as above. |
| opencode | provider-agnostic; routes to backing model + applies that model's defaults | inherits from backing provider | Force-push and mass-rewrite policies depend on which provider is wired in. |
| Aider | git-aware; auto-commits with its own attribution unless disabled | `Aider <author>` style trailer by default | The auto-commit behavior conflicts with this skill's "propose, don't execute" stance; user typically needs to disable auto-commit. |

## Detecting which harness invoked you

A capability can adjust its mitigation phrasing if it knows which harness is in play. Signals (in order of reliability):

- **Environment variables**: `CLAUDE_CONFIG_DIR` (Claude Code), `CURSOR_*` (Cursor), `GEMINI_API_KEY` plus `gemini`-cli process tree (Gemini CLI), `OPENCODE_PROFILE` (opencode), `CODEX_HOME` (OpenAI Codex CLI). Read with `os.environ.get(...)`; absent values mean the harness probably isn't running.
- **Process tree**: `ps -o comm= -p $PPID` walks up; common names include `claude`, `cursor-agent`, `gemini`, `codex`, `kimi`, `opencode`, `aider`.
- **Filesystem hints**: `.claude/` directory in cwd (Claude Code project config), `.cursor/` (Cursor workspace), `.aider*` files (Aider session state).
- **User-agent in API calls** when the harness exposes one to subprocesses (rare; most don't).

When unknown, default to the most defensive phrasing (full intent / impact / recovery framing on every flagged operation). False positives are cheap; false negatives — proposing a bare destructive command to a strict classifier — cost the whole turn.

## What this skill does NOT do

- The skill does not attempt to bypass classifier denials. If a classifier blocks a proposal, the capability surfaces the block, explains why, and lets the user re-authorize, run the command themselves, or add a permission rule to their harness settings.
- The skill does not silence harness warnings (e.g., `FILTER_BRANCH_SQUELCH_WARNING=1` is only set within an already-authorized invocation; the warning is informative for the user even if it does not change behavior).
- The skill does not chain proposals to evade per-command limits. If a multi-step operation must be split, each step has its own intent / impact / recovery framing.
