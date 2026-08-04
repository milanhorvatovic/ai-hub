# Format conventions: PR description

PR title rules and PR body structure. Load this when a capability is drafting or validating a pull request body. The PR title itself follows commit-subject rules — see `format-subject.md`.

For Precedence and Tone, see the `format-conventions.md` index.

## PR description (body)

Structure depends on the repo's PR template. If present, follow it. If not, the conventional structure is:

```
## Summary

<1-3 sentences: what the PR does and why>

## Changes

- <area>: <what changed>
- <area>: <what changed>

## Test plan

- [ ] <test or verification step>
- [ ] <another step>

## Notes (optional)

<migration notes, rollout caveats, screenshots, linked issues>
```

## Sections to consider including

- **Summary / Overview** — always.
- **Changes / What changed** — bulleted per-area, especially for multi-area PRs.
- **Test plan** — what the author verified before requesting review.
- **Screenshots / Demos** — UI changes only.
- **Migration notes / Rollout** — when the change affects production deploys, schema, or config.
- **Linked issues** — `Closes #N` / `Refs #N` per `issue-references.md`.

## Interaction with merge mode

When the repo squash-merges with `squash_merge_commit_message == "PR_BODY"`: drop markdown headings, use flat prose. The body becomes the commit message; `## Summary` literal text ends up in `git log`. See `merge-policy.md` for the squash-with-`PR_BODY` template.

When the repo squash-merges with `squash_merge_commit_message == "COMMIT_MESSAGES"`: the body's role is purely for review; the squash commit aggregates the branch's commit messages. The PR body can use the full markdown structure without git-log pollution.

## Anti-patterns

- **Unfilled template sections.** A PR body that ships with the template's `<description here>` placeholders still in place is worse than no body at all — it signals the author didn't read the template. The capability flags any line containing `TODO`, `<...>`, `[describe ...]`, or empty checklist items in non-checkbox positions.
- **Stale claims after follow-up commits.** Once the body says "max 3 attempts" but a follow-up commit changes it to 2, the body is wrong. `pr-description` SYNC mode exists to catch this; emit a `MINOR-UPDATE` proposal.
- **Conversational fluff.** "Hey team! I've been working on this for a few days and I think it's almost ready 🚀" — strip and replace with the Summary section.
- **Embedded auto-attribution trailers.** PR bodies are not commits; trailers in PR bodies are usually accidental copy-paste from a commit-message editor. See `trailer-semantics.md`.

## Tone considerations

Most of the rules from `format-conventions.md` Tone section apply, with these PR-specific notes:

- The Summary section is *present tense* describing the change ("Adds retry to the upload queue"), not past tense ("Added retry...").
- The Test plan checklist is *imperative* ("Run unit tests", "Deploy to staging") not declarative.
- The Notes / Migration section can shift to past tense for what was tested and present for what reviewers should do.
