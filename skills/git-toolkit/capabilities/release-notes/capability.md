---
name: release-notes
description: >
  Drafts release notes for a new version by aggregating commits and merged
  pull requests since the previous tag. Groups changes by conventional-commits
  type (feat / fix / refactor / docs / etc.), links closed issues, and credits
  contributors via PR author handles — never adds Co-Authored-By trailers
  automatically. Outputs markdown ready for GitHub Releases and the gh
  command. Triggers on "draft release notes", "what's in v1.4", "prepare
  the changelog", "generate release notes since the last tag".
---

# release-notes capability

Drafts release notes for a version by aggregating commits + PRs since the previous tag.

## Inputs

Resolve the range:

1. **End** — user-supplied tag/SHA, OR `HEAD`.
2. **Start** — user-supplied previous tag, OR most recent tag: `git describe --tags --abbrev=0 <end>^ 2>/dev/null`. If no prior tag exists → start from the first commit (`git rev-list --max-parents=0 HEAD`) and warn this is the initial release.

Guards:

- **Forge detection** — run `git remote get-url origin` and classify per `../../references/forge-adapters.md`. Surface `forge=<x>; capability assumes GitHub gh by default` in the proposal preamble. GitLab and Codeberg/Forgejo have native Releases concepts (`glab release create`, `tea release create`); Bitbucket Cloud does not — refuse cleanly on Bitbucket rather than emulating Releases via downloads.
- 0 commits in range → stop with "nothing since <tag>."
- `gh` not authenticated → degrade to commit-only mode (no PR enrichment, no contributor handles); warn the user.
- Repo has no remote → commit-only mode.

## Workflow

### 1. Gather commits and PRs

Commits in range:

```
git log --no-merges <start>..<end> --pretty=format:'%H%x09%s%x09%an%x09%ae'
```

PRs merged in range (when `gh` available):

```
gh pr list --state merged --search "merged:>=<date-of-start>" --limit 200 \
  --json number,title,body,labels,author,mergedAt,headRefName,baseRefName
```

Match commits to PRs via:

- Squash-commit subject ending in `(#<num>)` — primary heuristic
- `headRefName` matching the PR's source branch (for rebase-merged commits)

Commits with no PR match are direct-pushed; surface in a separate "Direct commits" section so they're not lost.

### 2. Classify by conventional-commits type

Parse each commit subject for `<type>(<scope>)<!>: <description>`. Group into:

| Group heading | Conventional-commits types |
|---|---|
| Breaking changes | Any commit with `!` marker or `BREAKING CHANGE:` footer (always first, regardless of type) |
| Features | `feat` |
| Bug fixes | `fix` |
| Performance | `perf` |
| Refactoring | `refactor` |
| Documentation | `docs` |
| Tests | `test` |
| Build & CI | `build`, `ci` |
| Chores | `chore`, `style` |
| Other | Anything that doesn't match conventional-commits |

If the repo doesn't use conventional commits, fall back to:

- Group by PR labels (when available) — `bug`, `enhancement`, `documentation`, etc.
- Or single "Changes" section with all bullets.

Match the repo's existing CHANGELOG style if present — check `CHANGELOG.md` for prior format (Keep-a-Changelog, custom, etc.).

### 3. Detect breaking changes

For each commit with `!` marker or `BREAKING CHANGE:` footer:

- Surface at the top under "Breaking changes"
- Include the migration note from the commit body verbatim if present
- If no migration note → write `Migration: see PR #N for details` and let the user fill in (do not fabricate)

### 4. Compose notes

```markdown
## [vX.Y.Z] - YYYY-MM-DD

<one-paragraph summary — draft from the top 3 most-impactful changes; mark
as "DRAFT: review before publishing">

### Breaking changes

- **<scope>**: <description>. Migration: <note from commit body, or "see PR #<N>">. ([#<PR>](url))

### Features

- **<scope>**: <description>. ([#<PR>](url) by @<author>)

### Bug fixes

- **<scope>**: <description>. Closes #<issue>. ([#<PR>](url) by @<author>)

...

### Contributors

@user1, @user2, @user3
```

Format rules:

- Per-bullet: lead with `**<scope>**` (bold) if conventional-commits scope present, then the verb/object, then PR link + author credit.
- Linked issues from commit and PR body → `Closes #N` per `../../references/issue-references.md` rules. Only include `Closes` keywords if the diff actually closes the issue.
- Skip commits whose subjects look generated (`Merge ...`, `Revert "..."` without context, bot-authored commits per `../../references/git-gh-quirks.md`).
- Authors credited via `@<github-handle>` from PR author in the "Contributors" section. **NEVER add `Co-Authored-By:` trailers to the release notes** — the contributor list provides credit.
- Match repo emoji convention by checking prior release notes; default to no emoji headings unless they're already established.

### 5. Secret scan

Run `../../references/secret-patterns.md` over the proposed notes. Release notes are public AND archived; redaction matters most here. On any match → WARN and refuse to include the bullet without user confirmation.

### 6. Body length / output

GitHub release notes have no strict size cap, but ≥10,000 chars renders poorly in the UI. Warn if proposed length exceeds that.

```
Proposed release notes for <tag-or-version>:

<full markdown>

---
Range: <start>..<end> (<N> commits, <M> PRs)
Contributors: <N> unique authors
Breaking changes: <count>
Length: <chars>

Apply with:
  gh release create <tag> --notes-file <path> [--draft] [--prerelease]

Or update an existing release:
  gh release edit <tag> --notes-file <path>

(Notes also written to: <tmpfile>)
```

Write notes to `mktemp` AND show inline. Never run `gh release create` automatically — releases are publicly visible and difficult to retract (deleting a release leaves a record in the GitHub events log).

## Edge cases

- **No prior tag** — start from first commit; warn this is the initial release.
- **Range crosses merged upstream** — filter out commits whose `baseRefName` isn't the release branch.
- **Pre-release** — if `--prerelease` likely, suggest a semver-compatible pre-release tag (`vX.Y.Z-rc.N`, `vX.Y.Z-beta.N`).
- **`CHANGELOG.md` exists** — show the user the section to ADD (not the whole file rewrite). Format-match the existing CHANGELOG style.
- **Empty commit subjects / commits with only body** — skip; warn user.
- **Squash-merged repo where PR body became commit message** (`sm == "PR_BODY"`) — use `gh pr view` body for the bullet text, not the truncated commit subject.

## Anti-patterns

- Don't auto-publish the release. Always require the user to run `gh release create`.
- **Don't add `Co-Authored-By:` trailers** — credit contributors via PR author handles in the "Contributors" section. This is a hard rule.
- Don't fabricate breaking-change migration notes if the commit body doesn't describe them. Write `Migration: see PR #N for details` instead.
- Don't include WIP / fixup! / squash! commits in the notes — they should have been cleaned up before merge (see `rebase-cleanup` capability).
- Don't promise behavior the diff doesn't deliver. Pull bullets from commit subjects + PR titles, not from imagination.
- Don't reorder breaking changes below other groups — they always come first.
- Don't include direct-pushed commits silently in the main groups; surface them separately so the user notices unreviewed changes.
