---
name: branch-name
description: >
  Proposes a git branch name for new work — from currently-staged changes, a
  user-supplied description of intent, or both. Respects the repo's branch
  naming conventions (prefixes like fix/, feature/, chore/), reads recent
  branch patterns from git, and defaults to no issue numbers in the slug
  (repo convention can override).
  Outputs 2-3 candidates and the git checkout -b command for the user to
  run. Triggers when the user is about to start a new branch, asks "what
  should I name this branch", or wants a branch name from staged work.
---

# branch-name capability

Proposes a branch name for new work and surfaces the checkout command. Never runs it automatically.

## Input guards

- If no staged changes AND no user description → ask the user to either stage something or describe what the branch is for.
- If already on a non-default branch with no commits yet → propose renaming the current branch; output `git branch -m <new>` instead of `git checkout -b <new>`.
- If already on a non-default branch with commits → warn before suggesting a new branch; the user may have meant `rebase-cleanup` instead.

## Workflow

### 1. Detect repo convention

In priority order:

1. Read `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` if present — they may declare branch naming rules.
2. Sample recent branches: `git branch -a --sort=-committerdate | head -30`. Detect:
   - Dominant prefix pattern (`fix/`, `feature/`, `chore/`, `bug/`, `feat/`, etc.)
   - Slug style (kebab-case vs snake_case vs camelCase) — kebab dominates in most repos.
   - Whether issue numbers appear in slugs (some repos do `feature/123-add-X`; flag if user prefers no-number style).
3. Fallback default: `<type>/<short-slug>` in kebab-case.

## 2. Map intent to type

| Source | Maps to type |
|---|---|
| User explicitly says "bug" / "fix" / "regression" | `fix/` |
| User explicitly says "feature" / "add" / "new" | `feature/` |
| User explicitly says "refactor" / "cleanup" | `refactor/` (or `chore/` per repo convention) |
| Staged diff: only tests changed | `test/` |
| Staged diff: only docs / README / CHANGELOG | `docs/` |
| Staged diff: only deps / lockfile | `chore/deps` (or `deps/`) |
| Staged diff: new file in source dir | `feature/` |
| Staged diff: modification to existing logic without test changes | Heuristic: `fix/` if commit context suggests a bug, else `feature/` |

When ambiguous, pick the broader category (`feature/` over `refactor/`).

### 3. Generate slug

- Extract the most specific noun + optional verb from the intent or diff (`retry queue`, `token expiry`, `config parser`).
- Slug: lowercase, hyphenated, ≤40 chars including the prefix.
- **No issue numbers in the slug.** Issue refs belong in commit messages and PR descriptions per `../../references/issue-references.md`.
- No author names, dates, version numbers, or environment names.
- Strip articles (`a`, `the`, `an`) and weak verbs (`update`, `change`, `improve`).

### 4. Propose alternatives

Output 2-3 candidates ranked specific → general:

```
Proposed branch names:
  1. feature/streaming-json-parser     ← most specific (recommended)
  2. feature/json-parser-refactor
  3. feature/parser-rewrite             ← least specific

Apply with:
  git checkout -b feature/streaming-json-parser
```

If repo convention disagrees with the user's stated preference (e.g. repo uses issue numbers but user wants none), flag and let the user pick.

## Anti-patterns

- Don't include issue numbers in the slug (`feature/123-add-retry` ❌). Issue refs belong in commit messages and PR descriptions, not branch names.
- Don't use vague verbs (`update`, `change`, `improve`, `fix-stuff`) — pick the specific noun.
- Don't run `git checkout -b` automatically — surface the command.
- Don't include author / date / version / environment metadata in the slug.
- Don't propose a branch name when there's nothing to base it on (no staged changes + no description). Ask first.
- Don't suggest renaming branches that have been pushed without warning about `git push origin :<old>` cleanup and the impact on open PRs.
