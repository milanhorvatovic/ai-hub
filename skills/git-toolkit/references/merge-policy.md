# Merge policy: how the repo merges shapes commit and PR-body format

The repo's merge settings determine whether the PR body becomes the commit message on merge — which determines how proposals must be shaped. Capabilities query this once per session.

## Query

```
gh api repos/{owner}/{repo} --jq '{
  squash: .allow_squash_merge,
  sm:     .squash_merge_commit_message,
  st:     .squash_merge_commit_title,
  rebase: .allow_rebase_merge,
  merge:  .allow_merge_commit
}'
```

Requires `repo` scope on the gh token. On private repos without scope, returns 404 — treat as "merge policy unknown" and default to normal markdown.

## Interpretation

| Setting | Implication for the proposal |
|---|---|
| `sm == "PR_BODY"` | The PR body **is** the squash commit message on merge. Shape MAJOR rewrites and new PR descriptions as a commit message: imperative subject ≤72 chars (if `st == "PR_TITLE"`, the PR title becomes the commit subject and the body holds only the commit body), flat prose body, avoid markdown headings (`#` / `##`) because they end up literal in `git log`. |
| `sm == "COMMIT_MESSAGES"` | Squash commit body is concatenated from the branch's commit messages — PR body is not used in the commit log. Body decoupled → use normal markdown structure. The individual commits' format matters here; run `commit-message` review on the branch. |
| `sm == "PR_TITLE"` | Squash commit body is just the PR title (no body content). PR body decoupled from commit log → normal markdown is fine. |
| `sm == "BLANK"` | Squash commit body is empty. PR body decoupled → normal markdown is fine. |
| `st == "PR_TITLE"` (with squash enabled) | The squash commit subject = PR title. The PR title must follow commit-subject format rules (imperative, ≤72 chars, conventional prefix if used). |
| `st == "COMMIT_OR_PR_TITLE"` | The squash commit subject defaults to the sole commit's subject (or PR title if multi-commit). Both need to follow commit-subject format. |
| `allow_rebase_merge == true` and the user plans to rebase-merge | Each commit subject + body lands verbatim in the base branch. The PR body is NOT the commit message, but every individual commit message matters. Run `commit-message` review on the whole branch. |
| `allow_merge_commit == true` and the user plans to merge-commit | The merge commit's message defaults to `Merge pull request #N from <branch>` followed by the PR title. The PR body is not used. Normal markdown is fine for the body; PR title still matters because it appears in the merge commit. |
| Settings query fails (private repo, missing scope, network) | Note "merge policy unknown" in the verdict; default to normal markdown structure but caveat that the user should verify before merging on a squash-with-`PR_BODY` repo. |

## Squash-with-`PR_BODY` template

When `sm == "PR_BODY"` and the proposal is a PR body that will become the squash commit message:

```
<imperative subject, ≤72 chars, no period>
                                          ← blank line required
<paragraph or bullets — flat prose, no markdown headings>

<optional trailers: Co-authored-by:, Signed-off-by:>
```

Do NOT include `## Summary`, `## Changes`, `## Test plan` headings — they end up in `git log --oneline` looking like `## Summary` literal text. Use prose paragraphs and inline bullets instead. The first line becomes the commit subject (or, if `st == "PR_TITLE"`, the PR title does); everything after the blank line becomes the commit body.

## Multi-method repos

A repo can enable multiple merge methods simultaneously. The user picks at merge time. If you can't know which they'll pick:

- Surface the most restrictive constraint (squash-with-`PR_BODY` if available — it forces the strictest format on the body).
- For commit-level work, assume rebase-merge (every commit's format matters).
- For PR-level work, assume squash with the strictest `sm` setting available.

## What to NOT confuse

- `squash_merge_commit_title` vs `squash_merge_commit_message` — separate settings. Title controls the commit subject source; message controls the commit body source. Both matter independently.
- "Squash merge" does NOT automatically mean "body becomes commit message." Only `sm == "PR_BODY"` does. Repos that squash with `sm == "COMMIT_MESSAGES"` derive the commit log from individual commits — the PR body is decoration.
- "Rebase merge" does NOT mean "commits get rewritten." It means commits get applied to the base unchanged. The PR body is irrelevant; per-commit format is critical.
