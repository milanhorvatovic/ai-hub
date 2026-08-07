# Issue references: closing-keywords vs context-refs

GitHub recognizes specific patterns that auto-close issues on merge. Mis-using them either leaves issues open after a fix lands or closes issues prematurely.

## Closing keywords

GitHub's auto-close picks up these keywords in a PR body OR in the squash commit message (when squash-merge applies), case-insensitive, followed by `#N` or `owner/repo#N`:

- `close`, `closes`, `closed`
- `fix`, `fixes`, `fixed`
- `resolve`, `resolves`, `resolved`

Format: `<keyword> #<issue-number>` or `<keyword> <owner>/<repo>#<issue-number>` for cross-repo.

Examples:

```
Closes #123
Fixes #456, fixes #789
Resolves owner/other-repo#42
fix #5
```

On merge, GitHub closes the referenced issue(s) with a "closed by #<PR>" event.

## Context references (no auto-close)

These reference an issue without closing it on merge:

- `refs`, `references`, `ref`
- `see`, `related to`, `related`, `part of`, `part-of`
- Bare `#N` (no leading keyword) — GitHub links but doesn't close

Examples:

```
Refs #123
See #456 for design context
Part of #789
This addresses the symptoms reported in #100 but the root cause tracked in #101 stays open
```

## Cross-repo references

`owner/repo#N` syntax works for both closing and context. The PR author needs write permission on the target repo to actually close cross-repo issues — without permission, the reference still links but the close is silently dropped.

## Commit-message issue trailers

Some repos use trailer-style references in commit messages (typically processed by changelog generators, not by GitHub's auto-close):

```
Issue: #123
Bug: #456
Refs: #789, #790
```

These don't trigger auto-close (only the prose closing-keywords do). They're useful for changelog tooling that scans trailers. Preserve verbatim if present.

## When the skill flags issue references

`pr-description` (both modes) should classify every issue reference in a body:

| Pattern | Class | Action |
| --- | --- | --- |
| Closing keyword + `#N` | closing-keyword | Verify the diff actually resolves the linked work (`gh issue view N`). If not → flag as overreaching; suggest downgrade to context-ref. |
| Context-ref (`Refs`, `See`, bare `#N`) | context-ref | Verify the diff still relates to issue N. If not → flag for removal. |

When proposing a new PR body, prefer:

- `Closes #N` ONLY when the diff fully resolves the issue.
- `Refs #N` when the diff touches related work but doesn't fully close the issue.
- Multiple closing references are fine: `Closes #123, closes #124` — verify EACH closes-keyword maps to a fully-resolved issue.

## Common mistakes

- **Closing too eagerly.** "Closes #100" on a PR that addresses one symptom of a multi-symptom issue → issue closes, other symptoms forgotten.
- **Not closing eagerly enough.** "Refs #100" on a PR that fully fixes the issue → issue stays open, on-call has to manually close.
- **Wrong syntax.** `Close: #N` (with colon) is NOT recognized as a closing keyword. Use `Closes #N` (no colon).
- **Closes-keyword in a comment, not the body.** GitHub only scans the PR body (and squash commit message) for auto-close. PR review comments don't trigger close.
- **Cross-repo without permission.** `Closes owner/other-repo#N` from a contributor without write access — silently doesn't close. Flag and document the limitation.
- **`Fixes #N` AND `Closes #N` for the same issue.** Either keyword works; using both is redundant and rare in well-maintained repos.

## Detection regex

For implementations that need to enumerate issue refs in a body:

```
# Closing keywords (case-insensitive)
(?i)\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:([\w.-]+\/[\w.-]+))?#(\d+)\b

# Context refs (case-insensitive)
(?i)\b(refs?|references?|see|related(?:\s+to)?|part[\s-]of)\s+(?:([\w.-]+\/[\w.-]+))?#(\d+)\b

# Bare references
\B#(\d+)\b
```

The bare-reference regex over-matches (e.g. matches `#123` inside a code block); strip code blocks first if precision matters.
