---
name: worktree-setup
description: >
  Sets up a new git worktree in the sibling worktrees/ directory for parallel
  work on a feature or fix branch. Reads the parent repo location, applies
  the user's branch-naming conventions (fix/ and feature/ prefixes, no issue
  numbers), and outputs the git worktree add command. Never runs the command
  automatically. Triggers when the user asks to "set up a worktree", "create
  a worktree for X", "new worktree for branch Y", or wants to start parallel
  work on a separate branch without touching the current checkout.
---

# worktree-setup capability

Proposes a `git worktree add` command following the user's parallel-work conventions.

## Input guards

- Must be inside a git repo: `git rev-parse --show-toplevel` — if not, stop.
- Must have either a target branch name OR a description to derive one from. If neither, ask.
- If the proposed worktree path already exists → refuse (overwrite is risky).
- If the proposed branch already exists → propose checkout into worktree instead of `-b`.

## Workflow

### 1. Resolve parent repo and worktree location

- Parent repo: `git rev-parse --show-toplevel`.
- Repo name: basename of parent.
- Worktree root: **sibling `worktrees/` directory** — `<parent>/../<parent-name>-worktrees/` OR `<parent>/../worktrees/<parent-name>/` (check which pattern the user's existing worktrees follow with `git worktree list`).
- Worktree path: `<worktree-root>/<branch-slug>`.

Default to sibling layout — the user's documented convention puts worktrees in a sibling `worktrees/` directory, NOT next to the repo.

### 2. Determine branch name

If user provided a name → validate it against the rules below (the same conventions the `branch-name` capability applies); if it doesn't follow them, suggest a corrected version.

If user provided only a description → infer the branch name from the same rules:
- `fix/<slug>` or `feature/<slug>` prefix (per user convention, no other prefixes by default)
- Kebab-case slug from the most-specific noun
- ≤40 chars total
- **No issue numbers in the slug** (per user convention)

### 3. Check pre-conditions

- Branch exists locally? `git show-ref --verify --quiet refs/heads/<branch>` — if yes, use `git worktree add <path> <branch>` (no `-b`).
- Branch exists on remote only? `git ls-remote --heads origin <branch>` — fetch first, then add.
- Target path exists? `[ -e <path> ]` — refuse if so.

### 4. Output

Show the proposed command and the rationale:

```
Worktree plan:
  Parent repo:    /path/to/repo
  Worktree root:  /path/to/repo-worktrees   (sibling layout, per your convention)
  Branch:         feature/streaming-parser  (new branch)
  Worktree path:  /path/to/repo-worktrees/feature/streaming-parser

Apply with:
  git worktree add /path/to/repo-worktrees/feature/streaming-parser -b feature/streaming-parser

After adding, switch to it:
  cd /path/to/repo-worktrees/feature/streaming-parser
```

For existing branch (no `-b`):
```
  git worktree add /path/to/repo-worktrees/fix/expired-token-handling fix/expired-token-handling
```

For remote-only branch (fetch + add):
```
  git fetch origin fix/expired-token-handling
  git worktree add /path/to/repo-worktrees/fix/expired-token-handling fix/expired-token-handling
```

Never run any of these automatically.

## Edge cases

- **Bare repo** — `git worktree` works on bare repos too; the parent-path discovery changes (`git rev-parse --git-dir`). Detect and adjust.
- **Detached HEAD in parent** — worktree-add still works; warn the user that the new worktree will start from current HEAD which may not be `main`.
- **No `worktrees/` sibling exists yet** — propose creating the directory as part of the command: `mkdir -p <worktree-root> && git worktree add ...`.
- **Branch name with slashes** (`fix/expired-token`) — the worktree path includes the slash literally; that creates nested dirs (`worktrees/fix/expired-token`). This is fine and matches `git worktree list` output.
- **User wants worktree next to repo, not in sibling dir** — refuse politely; the documented convention is sibling. If they override explicitly, honor and warn.

## Anti-patterns

- Don't auto-run `git worktree add` — surface the command, let the user run it.
- Don't include issue numbers in branch slug — issue refs belong in commit messages and PR descriptions.
- Don't use prefixes other than `fix/` and `feature/` unless the user explicitly asks or the repo documents alternatives.
- Don't place the worktree next to the repo (e.g. as `<parent>-worktree`); use the sibling `worktrees/` directory.
- Don't create the worktree from an outdated base — if the parent's `main`/`master` is behind, suggest `git fetch && git pull` first (in the parent, not the new worktree).
- Don't propose deleting an existing worktree path silently — refuse and let the user decide.
