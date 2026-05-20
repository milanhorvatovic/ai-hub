---
name: pr-description-write
description: >
  Authors a new PR description from scratch when a PR has no body, an unfilled
  template, a one-liner, or a WIP marker. Gathers the branch's diff and commit
  history, applies the repo's PR template if present, and follows the
  format-conventions and merge-policy rules. Never edits the PR automatically —
  produces a proposal and the exact gh command. Triggers when the user asks to
  write, author, or draft a PR description / PR body / PR summary; when the PR
  has no description yet; or when the existing description is empty / WIP /
  unfilled template.
---

# pr-description-write capability

Authors a PR body from scratch and proposes it to the user.

## When this capability fires (vs `pr-description-sync`)

- This capability: body is empty, body is `WIP` / one-liner, body is an unfilled template (per `../../references/pr-template-detection.md` >60% overlap rule).
- `pr-description-sync`: body has substantive content that needs validation against the branch.

`pr-description-sync` will detect the empty/WIP/unfilled case and recommend this capability rather than proposing a write itself.

## Input resolution

Same as `pr-description-sync`:

1. PR number or URL the user provided.
2. PR for current branch: `gh pr list --head <branch> --state all --json number,state,baseRefName,author`. Ask if >1 open.
3. None → stop with "no PR yet — create one first."

Guards:

- **Forge detection** — run `git remote get-url origin` and classify per `../../references/forge-adapters.md`. Surface `forge=<x>; capability assumes GitHub gh by default` in the proposal preamble. On non-GitHub remotes (GitLab / Codeberg / Bitbucket), follow the degrade path in `forge-adapters.md` — refuse cleanly if no portable equivalent exists.
- **State** — if `state ∈ {MERGED, CLOSED}` → refuse.
- **Bot author** — if `author.login` matches a login pattern in `../../references/bot-signatures.md` → skip; bot-authored PRs do not get human-written bodies from this capability.
- **gh auth** — on failure, tell the user to run `gh auth login`.
- **First-time contributor heuristic** — count the PR author's prior merged contributions: `gh pr list --author <author.login> --state merged --json number --jq 'length'`. If < 3, prepend `(first-time contributor heuristic — proposal expanded with extra context in Why and Test plan sections)` to the proposal preamble and bias the draft toward an explicit Why section even when the change looks self-explanatory. Newcomers benefit from the verbose explanation; long-time contributors usually don't need it. The heuristic is informational — it never blocks a proposal.

## Workflow

### 1. Gather diff and commits

Per `../../references/git-gh-quirks.md`, branch on cross-repo vs same-repo:

- **Cross-repo**: `gh api repos/{o}/{r}/pulls/{num}/files --paginate`, `gh pr diff <num> --patch`, `gh pr view <num> --json commits`.
- **Same-repo**: `git fetch origin <baseRefName>` (graceful degrade), `git log --no-merges <base>..HEAD --pretty=format:'%h %s'`, `git diff --stat <base>...HEAD`.

Reconcile local HEAD vs `headRefOid` and switch to cross-repo path on divergence.

### 2. Inventory changes

Bucket changed paths (code / tests / docs / config / CI / assets / infra / schema / deps) per the structure described in `pr-description-sync`. Sample largest + most-recently-modified file per bucket. Skip binaries.

### 3. Query merge policy

`gh api repos/{owner}/{repo} --jq '{squash:.allow_squash_merge, sm:.squash_merge_commit_message, st:.squash_merge_commit_title, rebase:.allow_rebase_merge}'`.

This determines the BODY SHAPE:

- `sm == "PR_BODY"` → flat prose, no markdown headings, ≤72-char first line (becomes the commit subject if `st != "PR_TITLE"`). Template per `../../references/merge-policy.md`.
- Anything else → standard markdown structure.

### 4. Find the template

Per `../../references/pr-template-detection.md`, resolve all candidate template paths. Pick:

- Single template (most repos) → use it.
- Multi-template directory → ask the user which one (the user may have intended a `feature.md` vs `bugfix.md`).
- No template → use the generic structure from `../../references/format-pr.md` (Summary / Changes / Test plan / Notes).

Preserve the template's section headings VERBATIM. Carry over instructional HTML comments if they help the user verify; otherwise strip them.

### 5. Draft the body

Per section:

| Section | Content source |
|---|---|
| Summary | 1-3 sentences derived from commit subjects + dominant change buckets. State what the PR does and why (motivation). |
| Changes | Per-bucket bullets: `<area>: <what changed>`. Pull verbs from commit subjects when accurate. |
| Test plan | Look for: changed test files (indicates what the author tested); CI workflow runs; commit messages mentioning testing. **Never invent** test items the author didn't reference. If unknown, write `Verification pending — to be confirmed by author`. |
| Screenshots / Demos | Skip for non-UI PRs. For UI PRs, leave a placeholder: `<!-- attach before/after screenshots -->`. |
| Migration notes / Rollout | Fill ONLY when an escalator-tier change is in the diff: schema migration, security change, public-API change, dep / runtime version bump, CI / release workflow change, user-visible behavior change. |
| Linked issues | Per `../../references/issue-references.md`: classify each reference from commit messages or branch name; prefer `Refs #N` unless the diff fully closes the issue. |

### 6. Apply format rules

Per `../../references/format-pr.md`:

- For `sm == "PR_BODY"`: flat prose, ≤72-char first line, no headings (see `../../references/merge-policy.md` template).
- For non-squash-`PR_BODY`: markdown structure per template.
- Imperative present-tense bullets in "Changes" section.
- Present-tense Summary describing what the PR does (e.g. "Adds retry logic…"), per `../../references/format-pr.md`.
- No marketing language.

### 7. Pre-display secret scan

Per `../../references/secret-patterns.md`. On match → redact + WARN. Never include detected secrets.

### 8. Body length check

GitHub PR body limit = 65,536 chars. If proposal >~65,000 → warn, suggest trimming.

### 9. Output

```
Proposed PR description for #<num>:

<full proposed body>

---
Length: <chars> chars (cap: 65,536)
Merge policy: <sm value> — <implications>
Template used: <path or "generic">
Issue refs: <classified list>

Apply with:
  gh pr edit <num> --body-file <path>

(Body also written to: <tmpfile path>)
```

Show the proposal INLINE AND write it to a `mktemp` file. The user can either copy from terminal or pass the file path to `gh pr edit`.

Never run `gh pr edit` automatically.

## Edge cases

- **PR is a draft** — same workflow; note draft status in the output. Drafts are expected to evolve; the proposed body is a starting point, not a final.
- **Squash-merge with `sm == "PR_BODY"` AND `st == "PR_TITLE"`** — the PR title becomes the commit subject. Validate the title against commit-subject rules too; flag if it's stale or unconventional (suggest a title alongside the body, but do not auto-edit the title).
- **No commits on branch yet** — if the diff is empty, stop with `EMPTY-DIFF`; can't author a body without changes.
- **Branch with one commit only** — the commit's subject + body may already be the right PR body content. Surface this and ask: use the commit message as the PR body, or write a fresh PR body?
- **Force-pushed branch** — use the local-vs-remote head reconciliation from `../../references/git-gh-quirks.md`.

## Anti-patterns

- Don't invent test-plan items. Use `Verification pending — to be confirmed by author` when unknown.
- Don't include screenshots / demo sections unless the diff has UI files.
- Don't fill in migration notes if there's nothing migration-relevant in the diff.
- Don't write a body for a closed/merged PR.
- Don't run `gh pr edit` automatically.
- Don't carry forward unfilled template comments verbatim in the final proposal — strip them once content has been filled in.
- Don't reformat the template's section headings — use them as the repo wrote them.
