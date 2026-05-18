---
name: merge-execute
description: >
  Outputs the canonical gh pr merge command for the PR, with the right
  method flag (squash / rebase / merge) per the repo's allowed merge
  methods and the user's intent. Pairs with merge-readiness (the gate
  check). Never merges automatically — surfaces the command for the user
  to run. Triggers when the user asks "merge this PR", "what's the right
  gh pr merge command", "how do I merge this", after merge-readiness
  reports READY.
---

# merge-execute capability

Outputs the canonical `gh pr merge` command. Tiny capability — read repo policy, pick flags, surface.

## Input guards

- Resolve target PR (number from user OR `gh pr list --head <branch>`).
- `state == OPEN` and not draft → otherwise refuse.
- `gh` auth required.
- Highly recommended (but not required): user has already run `merge-readiness` and saw `READY`.

## Workflow

### 1. Read repo merge policy

```
gh api repos/{owner}/{repo} --jq '{
  squash: .allow_squash_merge,
  rebase: .allow_rebase_merge,
  merge:  .allow_merge_commit,
  st: .squash_merge_commit_title,
  sm: .squash_merge_commit_message
}'
```

### 2. Determine method

| Repo allows | User intent | Recommended `--method` |
|---|---|---|
| squash only | (default) | `--squash` |
| rebase only | (default) | `--rebase` |
| merge only | (default) | `--merge` |
| multiple | not specified | Pick from `CONTRIBUTING.md` / `CLAUDE.md` if stated; otherwise ask: "which method does this repo prefer for this kind of change?" |
| multiple | user-specified ("squash this") | Use specified method, but verify it's allowed |

When in doubt, surface the choices and let the user pick rather than guessing.

### 3. Determine other flags

- **`--delete-branch`** — include by default if branch is a feature branch (`fix/` / `feature/` prefix). Skip for `main`/`master`/`develop`.
- **`--auto`** — only when user explicitly requests "merge when checks pass" / "auto-merge".
- **`--admin`** — never include automatically. If user asks for admin override, surface the flag with a strong warning.
- **`--subject` / `--body`** — only when the user wants to override the commit message. For `sm == "PR_BODY"` repos, this is unnecessary (body is auto-used).

### 4. Output

```
PR #42 merge command:

  gh pr merge 42 --squash --delete-branch

Repo merge policy:
  Allowed methods: squash, rebase
  Squash commit subject: from PR title
  Squash commit body: from PR body

Notes:
  - Branch `feature/streaming-parser` will be deleted after merge.
  - The PR body becomes the squash commit body (sm == "PR_BODY"); confirm
    body is in shape via pr-description-sync if you haven't.
  - Auto-merge not enabled; this will merge immediately.
```

If user wants auto-merge:
```
  gh pr merge 42 --squash --delete-branch --auto
```

Never run `gh pr merge` automatically. Output the command; let the user run it.

## Edge cases

- **PR is the base of a stacked PR** — warn that merging this will rebase the dependent stack PRs; suggest reviewing stack state first.
- **Repo has admin-only merge** — output the command, note the user needs admin and that `--admin` flag bypasses protections.
- **Repo requires linear history** — only `--rebase` or `--squash` work; `--merge` will error.
- **Cross-repo PR from fork** — same command; merge happens on the base repo regardless of fork.
- **PR is part of a release train (e.g. `release-please` PR)** — confirm with user before merging; release-train PRs often have specific merge expectations.

## Anti-patterns

- Don't merge automatically.
- Don't pick a method when multiple are allowed and the repo doesn't declare a preference — ask.
- Don't include `--admin` without explicit user request and a warning.
- Don't include `--delete-branch` for default branches.
- Don't bypass `merge-readiness` checks — if the user invokes this without running readiness, suggest running it first (especially for first-time PRs in this repo).
- Don't surface `--auto` unless the user asked for it — auto-merge is a deliberate choice, not a default.
