---
name: pr-conversation-resolve
description: >
  Lists unresolved review threads on a PR, proposes a response for each
  (either a "this was addressed in commit <sha>" reply or a substantive
  response draft), and surfaces the gh / GraphQL commands to post replies
  and mark threads resolved. Never posts comments or resolves threads
  automatically. Triggers when the user asks "what review comments are
  unresolved", "wrap up review feedback", "respond to all open threads",
  "what comments still need responses", or before invoking merge-readiness.
---

# pr-conversation-resolve capability

Lists unresolved review threads, proposes responses, surfaces commands. Doesn't post anything.

## Input guards

- **Forge detection** — run `git remote get-url origin` and classify per `../../references/forge-adapters.md`. Surface `forge=<x>; capability assumes GitHub gh by default` in the proposal preamble. On non-GitHub remotes (GitLab / Codeberg / Bitbucket), follow the degrade path in `forge-adapters.md`; thread-state semantics differ subtly across forges and may not round-trip exactly.
- Resolve PR (user-supplied OR `gh pr list --head <branch>`).
- `state == OPEN` and not closed — otherwise threads are moot.
- `gh` auth required.

## Workflow

### 1. Fetch review threads

Use GraphQL (REST doesn't expose `isResolved`):

```
gh api graphql -f query='
query($owner: String!, $repo: String!, $pr: Int!, $endCursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $endCursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 20) {
            nodes {
              databaseId
              author { login }
              body
              createdAt
              commit { oid }
            }
          }
        }
      }
    }
  }
}' -F owner=<o> -F repo=<r> -F pr=<num>
```

`reviewThreads` is capped at 100 per page. For PRs with more threads, loop on the cursor: pass `-F endCursor=<endCursor>` from the previous page while `pageInfo.hasNextPage` is true, accumulating `nodes` across pages — otherwise threads past the first 100 are silently dropped, which would undercount the "unresolved" total reported in Step 4. (`gh api graphql --paginate` automates this only when the query declares a variable literally named `$endCursor` and exposes `pageInfo { hasNextPage endCursor }`, as above — `gh` ignores any other cursor variable name.)

### 2. Filter to unresolved

Keep threads where `isResolved == false`. Note `isOutdated` separately (the file changed since the comment).

### 3. For each unresolved thread, classify

| Signal | Suggested response type |
|---|---|
| Recent commit touches `<path>` near `<line>` AND commit subject suggests fix | "Addressed in commit <sha>" reply + propose `resolveReviewThread` |
| Recent commit touches `<path>` but no clear signal it addresses this comment | "Addressed in commit <sha> — please confirm" reply (let reviewer mark resolved) |
| No relevant commit since the comment | Substantive response draft needed (acknowledge / question / disagree / agree-and-will-fix) |
| Thread is outdated AND no relevant commit | "This is no longer applicable since <path> changed in <sha>; please confirm" |
| Thread is a nitpick / preference | Brief acknowledgment + decision (accept / decline with rationale) |

### 4. Match comments to commits

For each unresolved thread:
- Look at commits on the branch since the thread was opened: `git log --since="<thread createdAt>" <base>..HEAD -- <path>`
- Score relevance by file path + line proximity + subject keywords
- If a commit clearly addresses the comment, propose the "Addressed in <sha>" reply

### 5. Draft responses

For each thread, generate a proposed response:

- **Tone:** professional, brief, specific. Match the repo's review tone (sample existing replies from the PR).
- **Reference commits with short SHA + subject**, not the full hash.
- **Don't speculate** about what the reviewer meant — if ambiguous, draft a clarifying question instead.
- **Never agree to changes you haven't seen the user agree to** — for "you should change X" comments where no fix has landed, draft "Will address" / "Need to think about this" / "Pushed back: …" alternatives and let the user pick.

### 6. Output

```
PR #42 — 3 unresolved threads of 7 total

## Thread 1: src/auth/refresh.py:42

  @reviewer (5 days ago):
  > This guard doesn't handle the case where expiry is exactly now —
  > you might want `<=` instead of `<`.

  Status: addressed in abc1234 fix(auth): use <= for expiry comparison

  Proposed reply:
    Good catch — fixed in abc1234, switched to `<=`. Thanks!

  Apply with:
    gh api graphql -f query='mutation { addPullRequestReviewThreadReply(...) ... }' \
      -F threadId=<thread-id> -F body='Good catch — fixed in abc1234, switched to `<=`. Thanks!'

  Then resolve:
    gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "<id>"}) { ... } }'

## Thread 2: src/auth/refresh.py:78 (OUTDATED)

  @reviewer (3 days ago):
  > Why not pull this into a helper?

  Status: file rewrote since (now at line ~50 in def5678). Comment may no longer apply.

  Proposed reply (pick one):
    a) "This file was rewritten in def5678 — could you re-review the helper structure
       in the new version?"
    b) "Refactored in def5678, please take another look."

  Apply (option a):
    gh api graphql ... -F body='...'

## Thread 3: src/auth/types.py:15 (NOT YET ADDRESSED)

  @reviewer (2 days ago):
  > Can we type this as `Token | None` instead of `Optional[Token]`?

  Status: no commit since the comment touches this file.

  Proposed reply (draft — pick one or revise):
    a) "Will do — switching to `Token | None` syntax in the next push."
    b) "We're still on Python 3.9 minimum per setup.cfg, which doesn't support
       union syntax. Could you confirm whether we should bump the minimum, or
       keep `Optional[Token]`?"
    c) (Decline) "Sticking with `Optional[Token]` for consistency with the rest
       of the module; would prefer to do a sweep PR if we change style."

  Apply (after picking):
    gh api graphql ... -F body='<chosen text>'
```

Always:
- Show the original comment in full (or first 3 lines + ellipsis if long)
- Surface the commit-match analysis
- Draft response options when ambiguous
- Provide both the reply command AND the resolve command separately (some threads want a reply WITHOUT resolving; reviewer marks resolved)

Never post or resolve automatically.

## Edge cases

- **Self-review threads** (you opened threads on your own PR) — surface separately; usually low priority.
- **Bot-authored threads** (CodeQL, Sonar, etc.) — flag as bot comments; "Addressed in <sha>" may not be enough to satisfy the bot, which only re-checks on push.
- **Threads with many comments** — surface the LATEST comment in the thread; earlier comments are context.
- **Suggestion-block comments** (`suggestion` markdown) — the reviewer proposed a code change; offer to accept the suggestion via `gh pr review --comment --body '...' --apply-suggestion` (if supported by gh) OR direct the user to the PR UI's "commit suggestion" button.
- **Resolved threads being re-opened by new commits** — don't list (only `isResolved == false`).
- **PR with 50+ threads** — paginate; show top 10 unresolved + a count.

## Anti-patterns

- Don't post replies automatically — every response is a public engineering act.
- Don't resolve threads automatically — resolution is a social signal that the reviewer's concern is addressed.
- Don't draft sycophantic responses ("Great point!" "Awesome feedback!") — match the repo's existing tone.
- Don't agree to changes without evidence the user agrees — draft alternatives when the response requires a decision.
- Don't claim a commit fixes a thread without high confidence — when uncertain, propose "addressed in <sha> — please confirm" not "fixed in <sha>".
- Don't add trailers (`Co-authored-by:`, etc.) to comment bodies.
