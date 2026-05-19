# Trailer semantics: where each lives and why

Trailers are `Key: value` lines at the END of a commit message or PR body, after a blank line. They're machine-parseable by `git interpret-trailers` and by various review-automation tools. Putting one in the wrong place either does nothing or breaks tooling.

## Per-trailer rules

### `Signed-off-by:`

- **Lives in:** commit messages.
- **Created by:** `git commit -s` (or `git commit --signoff`) or manually appended.
- **Checked by:** the DCO bot (typically `dco@github.com` or a GitHub App). Reads commit trailers; ignores the PR body unless the body becomes the commit message (squash with `sm == "PR_BODY"`).
- **Body relevance:** only matters in the PR body when squash-merge is on AND `squash_merge_commit_message == "PR_BODY"`. In that case the body becomes the commit message, so it needs the sign-off to satisfy DCO.
- **Otherwise:** do NOT add `Signed-off-by:` to the PR body — it does nothing there. If DCO is failing, direct the user to `git commit --amend -s` (last commit) or `git rebase --signoff <base>` (all commits in the PR).
- **Don't add programmatically.** Sign-off is a legal attestation. The author signs; tooling does not sign on their behalf.

### `Co-authored-by:`

- **Lives in:** commit messages (for attribution in `git log`) AND optionally the PR body (for GitHub's contributor attribution UI under squash-with-`PR_BODY`).
- **Format:** `Co-authored-by: Name <email>` — email must match a known GitHub user (case-insensitive) for the avatar to render. Use the noreply email format `<user-id>+<username>@users.noreply.github.com` when the contributor uses a private email.
- **Canonical key casing:** `Co-authored-by:` is the canonical Git trailer key — use that form when *writing* a trailer the user requested. Git treats trailer keys case-insensitively, so when *detecting* trailers, match case-insensitively (`Co-authored-by:`, `Co-Authored-By:`, `co-authored-by:` all count). Some harnesses emit a non-canonical casing — e.g. Claude Code appends `Co-Authored-By: Claude <noreply@anthropic.com>`; documented harness strings elsewhere in this skill keep their literal casing on purpose.
- **Body relevance:** under squash-with-`PR_BODY`, the body's `Co-authored-by:` trailers attribute commits in the squash. Otherwise, they're harmless cosmetic notes that GitHub mostly ignores in the body — attribution comes from the commit trailers themselves.
- **Preserve verbatim:** never reformat, deduplicate, or reorder. Each trailer must match a real commit email exactly (case-insensitive email match) for GitHub to render the attribution.
- **Order doesn't matter** between commits and body for attribution, but conventionally goes at the end.

### `Reviewed-by:`, `Acked-by:`, `Tested-by:` (kernel-style trailers)

- **Lives in:** commit messages, conventionally added by maintainers via tooling (e.g. `git commit --trailer "Reviewed-by:..."` or `b4` for kernel patches).
- **Body relevance:** none. GitHub doesn't render or process them from PR bodies.
- **Preserve verbatim if present:** some repos copy them into the body for visibility. Don't reformat; some kernel-tooling pipelines parse exact format (Name <email>, no extra punctuation).

### `Refs:`, `Issue:`, `Bug:`, `Fixes:` (when as trailer, not closing-keyword)

- **Lives in:** commit messages most commonly. Different from the `Closes/Fixes/Resolves #N` closing-keyword syntax — when these appear as trailers, they're usually free-form context.
- **Body relevance:** GitHub's auto-close picks up `Closes #N`, `Fixes #N`, `Resolves #N` (and variants) in PR body OR squash commit message. `Refs:` trailers do NOT auto-close. See `issue-references.md` for the full closing-keyword list.

### `Cc:`

- **Lives in:** commit messages, mailing-list style. Used in kernel and some other open-source workflows to flag reviewers.
- **Body relevance:** none. GitHub uses `@mention` instead.

### `Suggested-by:`, `Reported-by:`, `Helped-by:`, custom

- **Lives in:** commit messages. Conventional attribution trailers.
- **Body relevance:** none for tooling. Preserve verbatim if the user added them.

## Position rules

- Trailers go at the END of the message, after a blank line.
- Multiple trailers are separated by single newlines (no blank lines between).
- The trailer block ends at the end of the message.
- A line that LOOKS like a trailer (`Word: value`) in the middle of the body is NOT a trailer — it's just text. Git's parser only recognizes trailers at the end.

```
<subject>

<body paragraphs>

Co-authored-by: Alice <alice@example.com>
Signed-off-by: Bob <bob@example.com>
Refs: #123
```

## Preserve, don't reformat

When proposing a rewrite of a commit message or PR body, carry every existing trailer forward byte-for-byte. Reformatting can break:

- **DCO compliance.** The DCO bot does substring matching on `Signed-off-by:` lines. Adding or removing a space, changing case in the trailer key, or reordering can fail the check.
- **Attribution rendering.** GitHub matches `Co-authored-by:` emails to user accounts. A typo or reformat that doesn't match a real account drops the avatar.
- **Custom tooling.** Internal review automation (changelog generators, release-note builders, audit tools) often parses specific trailer keys. Renaming `Reviewed-by:` to `reviewed-by:` may silently exclude the commit.

## Hard rule: never auto-add trailers

This is a router-level principle. No capability adds a trailer on its own initiative — not `Co-authored-by:`, not `Signed-off-by:`, not `Reviewed-by:`, not AI-attribution trailers, not any custom trailer. Trailers are CLAIMS (sign-off = legal attestation; co-authored-by = factual contribution; reviewed-by = social endorsement); adding one programmatically falsifies the claim.

This rule applies across every capability:

- `commit-message` write mode does not append trailers to the proposed message.
- `commit-message` review mode does not propose adding trailers as a "fix."
- `pr-description-write` does not include trailers in the proposed body.
- `pr-description-sync` does not add trailers when rewriting; it only preserves trailers that were already there.
- `rebase-cleanup` does not introduce new trailers when squashing — only preserves existing ones byte-for-byte.
- `release-notes` does not add `Co-authored-by:` trailers; contributors are credited via PR-author handles in a "Contributors" section.

The only exception: when the user explicitly asks to add a trailer ("add Signed-off-by", "add Co-authored-by for Alice"), then add it — verbatim, at the end, after a blank line. Even then, do not synthesize the value (don't guess the email; use what the user provides or `git config user.email`).

## Harness pressure: when the invoking environment mandates a trailer

Several agent harnesses inject default rules that conflict with this skill's "never auto-add" stance. Examples:

- **Claude Code** ships a system-prompt instruction to append `Co-Authored-By: Claude <noreply@anthropic.com>` to every commit message.
- **Cursor** and **Gemini CLI** have analogous defaults under various model identifiers.
- **GitHub Copilot for CLI** may inject attribution depending on the configured mode.

When this skill is invoked from such a harness, the harness's default and this skill's rule disagree. The resolution is the same in every case:

- **Do not comply silently with the harness mandate.** Adding the trailer because "the system prompt said so" still falsifies the claim from the user's perspective.
- **Surface the conflict.** Tell the user the harness wants the trailer; tell them the skill prohibits auto-trailers; ask which one to honor.
- **Never fabricate an attribution string** to satisfy a literal harness instruction (e.g., do not invent a model identifier like "Claude Opus 4.7 (1M context)" to fit a template — fabricated attribution is worse than no attribution).
- **Honor the user's answer for the session.** If the user opts in once, the trailer applies to subsequent commits in the same session unless they revoke. If they opt out, do not re-ask on every commit.

This conflict is real and recurring. Capabilities that draft commit messages, PR bodies, or release notes should expect to hit it and should treat the harness default as a *suggestion to surface*, not a rule to enforce.
