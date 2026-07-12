---
name: worktree-setup
description: >
  Sets up a new git worktree for parallel work on a feature or fix branch.
  Detects the repo's worktree conventions before proposing anything — rules
  documented in config or agent-instruction files, placement inferred from
  existing worktrees via git worktree list, and the branch-naming style in
  use — falling back to a sibling worktrees/ directory when nothing is
  documented or detectable. Outputs the git worktree add command; never runs it
  automatically. Triggers when the user asks to "set up a worktree", "create
  a worktree for X", "new worktree for branch Y", or wants to start parallel
  work on a separate branch without touching the current checkout.
---

# worktree-setup capability

Proposes a `git worktree add` command following the repo's detected parallel-work conventions.

## Input guards

- Must be inside a git repo: `git rev-parse --show-toplevel` — if not, stop.
- Must have either a target branch name OR a description to derive one from. If neither, ask.
- If the proposed worktree path already exists → refuse (overwrite is risky).
- If the proposed branch already exists → propose checkout into worktree instead of `-b`.

## Workflow

### 1. Detect the worktree convention

Resolve the parent repo first — `git rev-parse --show-toplevel`; repo name is its basename. Then infer the placement root, in priority order:

1. **Documented rules** — `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` may state where worktrees live; documented repo conventions override anything observed or defaulted, per the router.
2. **Existing worktrees** — `git worktree list --porcelain`. If any worktree besides the main checkout exists, infer the placement root (sibling `<parent-name>-worktrees/`, sibling `worktrees/<parent-name>/`, directories directly next to the repo, or something else) and the path style (nested branch path with slashes vs flattened slug) from the paths already in use.
3. **Fallback default** — the sibling root `<parent>/../<parent-name>-worktrees/`. Note in the output that the default was used because nothing was documented or detectable.

Worktree path: `<root>/<branch>` — the branch path verbatim (nested) by default, or with `/` converted to `-` when the detected path style flattens.

### 2. Determine branch name

If user provided a name → validate it against the detected naming convention below; if it doesn't follow, suggest a corrected version.

If user provided only a description → infer the branch name using the same detection order branch naming always follows:

1. Naming rules declared in `CLAUDE.md` / `AGENTS.md` / `CONTRIBUTING.md`.
2. The dominant pattern in recent branches — `git branch -a --sort=-committerdate | head -30`: prefix vocabulary (`fix/`, `feature/`, `chore/`, …), slug style (kebab vs snake), whether issue numbers appear in slugs.
3. Fallback when nothing is detectable: `fix/<slug>` or `feature/<slug>` prefixes, no issue numbers in the slug.

Whatever the source: slug from the most-specific noun, kebab-case unless the detected slug style differs, and ≤40 chars total including the prefix — the length cap holds regardless of what detection found.

### 3. Check pre-conditions

- Branch exists locally? `git show-ref --verify --quiet refs/heads/<branch>` — if yes, use `git worktree add <path> <branch>` (no `-b`).
- Branch exists on remote only? `git ls-remote --heads origin <branch>` — fetch first, then add.
- Target path exists? `[ -e <path> ]` — refuse if so.

### 4. Output

Show the proposed command and the rationale:

```
Worktree plan:
  Parent repo:    /path/to/repo
  Worktree root:  /path/to/repo-worktrees   (<documented rules / detected from existing worktrees / sibling default — nothing detectable>)
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
- **No worktree root exists yet** — propose creating the directory as part of the command: `mkdir -p <worktree-root> && git worktree add ...`.
- **Branch name with slashes** (`fix/expired-token`) — with the default nested style the worktree path includes the slash literally, creating nested dirs (`worktrees/fix/expired-token`) that match `git worktree list` output; when the detected path style is flattened, convert `/` to `-` instead.
- **User's requested placement contradicts the documented or detected convention** — flag the mismatch, show both paths, and let the user pick. Honor an explicit choice, noting in the plan that it diverges from the repo's convention.
- **Next-to-repo placement requested when nothing is documented or detectable** (fresh repo, fallback case) — honor, but warn first: a worktree directly beside the repo gets swept up by parent-directory tooling (backup and sync globs, IDE workspace scans), which the sibling `worktrees/` default exists to avoid.

## Anti-patterns

- Don't auto-run `git worktree add` — surface the command, let the user run it.
- Don't include issue numbers in the branch slug unless the detected convention uses them — issue refs belong in commit messages and PR descriptions.
- Don't invent prefixes beyond the detected vocabulary — when nothing is detectable, stick to the `fix/` / `feature/` fallback unless the user explicitly asks.
- Don't override a documented or detected placement convention with the sibling default — the default exists only for repos where neither yields anything.
- Don't create the worktree from an outdated base — if the parent's `main`/`master` is behind, suggest `git fetch && git pull` first (in the parent, not the new worktree).
- Don't propose deleting an existing worktree path silently — refuse and let the user decide.
