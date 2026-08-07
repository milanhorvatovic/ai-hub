# Review — industry best practices

External standards, comment conventions, reviewer discipline. Complements the principle-anchored workflow in `../capability.md`.

## External standards

- **[Conventional Comments](https://conventionalcomments.org/)** — labeled comment prefixes that remove "is this a blocker?" ambiguity. Industry-recognized; many open-source projects adopt them.

## Comment labels (Conventional Comments)

Every review comment should carry a label that signals its weight:

| Label | Meaning | Example |
| --- | --- | --- |
| `praise:` | Acknowledge good work | `praise: nice use of the typestate pattern here` |
| `nitpick:` | Minor; non-blocking | `nitpick: trailing whitespace` |
| `suggestion:` | Recommended change | `suggestion: extract this 30-line block into a function` |
| `question:` | Asking, not telling | `question: is this intentional, or should it raise?` |
| `issue:` | A real problem that needs addressing | `issue: this leaks the API token to logs` |
| `thought:` | Reflective, non-actionable | `thought: similar logic exists in module X; future cleanup` |
| `todo:` | Author's TODO surfaced for the next pass | `todo: add a test for the empty-list case` |
| `chore:` | Process/admin (rebase, conflict, missing label) | `chore: needs rebase on main` |

Decorators clarify weight further:

- `(blocking)` — must be addressed before merge.
- `(non-blocking)` — author can accept or decline; not a merge gate.
- `(if-minor)` — fix only if cheap.

Example: ``issue (blocking): this query has no `WHERE user_id = ?` — any user can read any record``.

## Map to severity (parent skill)

Conventional Comments labels overlay onto this skill's severity:

| Severity (parent skill) | Default label                            |
| ----------------------- | ---------------------------------------- |
| **must**                | `issue (blocking):`                      |
| **should**              | `suggestion:` or `issue (non-blocking):` |
| **could**               | `nitpick:` or `thought:`                 |

Always cite the principle number for `issue:` and `suggestion:` so the author can verify the anchor.

## Approve vs request-changes

- **Approve with comments** — the PR has only `should` / `could` findings (or zero findings). The author can address or decline; merge is not blocked.
- **Request changes** — the PR has at least one `must` finding (`issue (blocking):`). The author must address or push back; merge is blocked.
- **Comment only** — used when you have observations but explicitly defer the approval decision to another reviewer (e.g., domain expert needed).

Avoid "approve" with hidden expectations; if you want the author to address something, say so explicitly with a `(blocking)` decorator.

## Praise is allowed and recommended

When the author did something well — a clever-but-clear abstraction, a particularly readable test, a careful migration — say so. Reviews that contain only criticism train authors to associate review with stress, which makes the next PR more defensive, not better.

Praise costs nothing and is the single highest-ROI review behavior. Aim for one `praise:` comment per non-trivial PR.

## Reviewer load discipline

- **Stay under ~400 LOC per review session.** Beyond that, defect-detection rate falls off a cliff; reviewers start skimming.
- **One review at a time.** Don't interleave two PRs in one sitting — the cognitive switching makes both reviews worse.
- **Time-box.** A review session of 60-90 minutes is the practical maximum before fatigue overrides judgment.
- **Ask the author to split** PRs that exceed these thresholds, rather than approving them out of fatigue.

## What good looks like (for authors, surfaced during review)

When reviewing, flag the absence of these as `suggestion:` or `chore:`:

- **PR title** explains _what_ changes in one line.
- **PR description** explains _why_ it changes, _how_ it was tested, and any deployment / migration concerns.
- **Commits** are small and have meaningful subjects (Conventional Commits or the repo's style).
- **Tests** exist for new behavior; bug fixes have a failing-first test (principle 2).
- **Diff is focused** — no unrelated reformatting, no opportunistic refactors (principle 1).

These are review-time _signals_, not findings — they shape the next PR more than this one.

## What to skip during review

- **Formatter-handled style** (indentation, quotes, trailing commas) — let the formatter fix it.
- **Personal-preference renames** when the existing name is consistent with the file.
- **Findings that match the surrounding file's conventions** — local consistency wins (principle 9). Flag the file-level conflict instead.
- **Generated code, vendored code, migrations** — out of scope unless they were generated/written by hand in this PR.

## Constructive phrasing

- **Describe the consequence**, not the verdict. Say "this leaks the token to logs" / "this couples X to Y, so changes to Y require touching X." Not "this is bad practice."
- **Suggest a concrete change** when the suggestion is non-trivial. A two-line code sketch beats two paragraphs of prose.
- **Reference the principle** for traceable rules; reference _external standards_ (Conventional Commits, PEPs, Rust API Guidelines) when the rule is industry-wide rather than team-local.
- **Ask, don't accuse.** `question: was this intentional?` opens a conversation; `you forgot to handle X` closes it.

## Anti-patterns specific to review

Stated once, in `../capability.md` — the entry point every review already loads, so repeating them here would only give the two lists room to drift apart. This file covers the external-standards side of review; the behavioral failure modes live there.
