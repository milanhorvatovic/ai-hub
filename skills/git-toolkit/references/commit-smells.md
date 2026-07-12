# Commit smells — catalog

Anti-patterns that REVIEW-mode capabilities (`commit-message` review, `rebase-cleanup`, `commit-body-reflow`, `merge-readiness`) scan for. Each entry pairs a pattern with why it's bad, how to fix it, and a before/after example. Use this catalog as the consolidated source of "things to flag"; the rule rows in `format-subject.md` and `format-body.md` say WHAT the rule is, this file says HOW to recognize a violation in the wild.

Findings emitted from this catalog should use the `rule` ids defined here verbatim, so the `review-output.md` NDJSON stream is greppable.

## Rule selectivity (optional `rules:` filter)

By default every catalog rule runs. When the user passes a `rules:` argument — a comma-separated list of kebab-case rule ids, e.g. `rules: past-tense-verb,trailing-period,overlong-subject` — only those rules are evaluated. Unmatched rule ids are surfaced as a warning ("`rules: ehubble-quirky` not in catalog") but do not halt the run. The consuming capability's output preamble must list the active subset so the reader knows what was *not* checked: `Active rule subset: past-tense-verb, trailing-period, overlong-subject (3 of 24 catalog rules)`.

The NDJSON output shape from `review-output.md` is unchanged — findings still carry their `rule` id; the only change is which rules contribute. Useful in CI contexts where a repo has accepted some smells as out-of-scope but wants to enforce others on every run.

## Subject smells

### `generic-verb` — "Update X", "Change Y", "Fix bug"

The subject uses a verb that carries no information about what the change does. Reader of `git log --oneline` gets no signal beyond "something happened in X".

**Pattern**: subject starts with one of `Update`, `Change`, `Improve`, `Tweak`, `Adjust`, `Modify`, `Touch up`, `Clean up`, `Tidy`.

**Why**: the imperative-mood rule in `format-subject.md` requires a specific verb that names the operation. Generic verbs are technically imperative but say nothing.

**Fix**: pick a specific verb that names the operation (`Add`, `Remove`, `Rename`, `Extract`, `Inline`, `Replace`, `Fix`, `Refactor`, `Reorder`, `Split`, `Merge`, `Bump`).

**Example**:

```
Bad:  Update parser.py
Good: feat(parser): add streaming JSON reader
```

### `vague-noun` — "fix bug", "fix issue", "fix things"

The subject names a verb but no specific noun. Combined with `generic-verb`, this produces the canonical "fix bug" anti-commit.

**Pattern**: subject contains a verb + one of `bug`, `issue`, `thing`, `stuff`, `things`, `code`, `problem` with no other noun.

**Fix**: name the specific thing changed. "Fix retry timeout", "Fix null deref in handler".

### `status-marker` — "WIP", "TODO", "[DRAFT]"

The subject carries draft state.

**Pattern**: subject contains any of `WIP`, `[WIP]`, `TODO`, `XXX`, `temp`, `TEMP`, `DRAFT`, `[DRAFT]`, `fixme`, `FIXME`.

**Fix**: the change isn't ready to ship; squash into the prior commit, `git stash`, or rewrite the message after finishing the change.

**Example**:

```
Bad:  WIP: try new approach to retry
Good: (don't commit yet; squash into the prior real commit or git stash)
```

### `issue-in-subject` — "Fix retry bug #123"

Issue reference embedded in the subject line.

**Pattern**: subject matches `#\d+` or `(GH|JIRA|PROJ)-\d+`.

**Fix**: move the issue ref to the body using `Closes #123` (auto-closes) or `Refs #123` (linked but not closed). See `issue-references.md`.

### `filepath-in-subject` — "src/foo.py: fix X"

Subject uses a path prefix or a filename to scope the change.

**Pattern**: subject contains `/`, or ends with `.py` / `.js` / `.ts` / `.go` / `.rs` / `.java` / `.rb` / `.md` / `.json` / `.yml` / etc. before a verb.

**Fix**: drop the filepath; `git log --stat` shows files. Use a scope (`feat(parser): ...`) if the repo uses conventional commits.

### `trailing-period` — "Add retry to consumer."

**Pattern**: subject ends with `.`.

**Fix**: delete the period. Subject is a title, not a sentence.

### `past-tense-verb` — "Added retry to consumer"

**Pattern**: subject starts with a past-tense English verb (`Added`, `Fixed`, `Removed`, `Updated`, `Changed`, `Refactored`, `Renamed`).

**Fix**: imperative mood (`Add`, `Fix`, `Remove`, `Refactor`, `Rename`).

### `overlong-subject` — "Add retry to the upload queue with exponential backoff and configurable max attempts"

**Pattern**: subject length (in display columns, not bytes — see `format-body.md` recipe) exceeds 72.

**Fix**: shorten by dropping qualifiers; move detail to body. Hard cap stays at 72 because GitHub truncates there.

### `emoji-prefix` — "✨ Add streaming JSON parser 🚀"

**Pattern**: subject starts with an emoji code point not preceded by alphanumeric.

**Fix**: drop unless the repo's last ~20 commits all use emoji prefixes (gitmoji convention).

### `bracketed-author` — "[author] add retry"

**Pattern**: subject starts with `[author-name]` or `(author-name)`.

**Fix**: drop. Author is in commit metadata (`%an`/`%ae`); subject is for the change.

### `bracketed-version` — "v2.4: add retry"

**Pattern**: subject starts with `v\d`, or `\d+\.\d+`, or `[v\d]`.

**Fix**: drop. Versions are in tags; subject is for the change.

## Body smells

### `restated-subject` — body's first line repeats the subject

**Pattern**: body's first non-blank line is ≥80% similar to the subject (Levenshtein distance) or contains the entire subject as a substring.

**Fix**: drop the duplicate line. Body starts with motivation, not restatement.

### `listed-files` — body says "Files changed: X, Y, Z"

**Pattern**: body contains a line matching `^Files? (changed|modified|touched):\s*` or `^Touched files:\s*`.

**Fix**: drop. `git show --stat` does this; the body is for intent.

### `auto-trailer` — body ends with an attribution trailer the user didn't request

**Pattern**: body ends with `^(Co-authored-by|Signed-off-by|Reviewed-by|Generated-by|Authored-by):\s` (case-insensitive) when no user instruction asked for it.

**Fix**: per `trailer-semantics.md` Hard rule, drop unless the user explicitly asked. Trailers are CLAIMS; an automated tool adding one falsifies the claim.

### `marketing-language` — "we are excited to announce this awesome change"

**Pattern**: body contains any of `excited to`, `pleased to`, `happy to (announce|share)`, `awesome`, `amazing`, `delighted`, `proud to`, `incredible`.

**Fix**: drop. Commit messages are documentation; marketing belongs in release blog posts.

### `apology-language` — "sorry for the late fix, this should have been cleaner"

**Pattern**: body contains any of `sorry for`, `apologies for`, `should have been`, `unfortunately`, `hopefully this`, `fingers crossed`.

**Fix**: drop. History is not a changelog of feelings; if the message would help future readers debug, write it as observation ("Earlier commit X took the wrong approach because Y; this corrects to Z").

### `personal-jargon` — body uses in-group nicknames or unexplained abbreviations

**Pattern**: hard to detect mechanically; the capability surfaces a `MAYBE` finding when the body contains TitleCase tokens not present in the diff or in recent commit history.

**Fix**: spell out the term on first use, or skip mention. `git log` outlives the author's tenure.

## PR-body smells

### `unfilled-template` — placeholder text still present

**Pattern**: PR body contains `<...>`, `[describe ...]`, `TODO`, `TBD`, `<!--`, or empty `## Section` headers with no content underneath.

**Fix**: fill in the section, or remove it if irrelevant. See `pr-description-write` capability.

### `stale-claim` — body says one thing, diff shows another

**Pattern**: detected by `pr-description-sync`, not by static catalog scan. The capability re-reads the body after each commit and classifies divergence as `IN-SYNC` / `MINOR-UPDATE` / `MAJOR-REWRITE`.

**Fix**: re-run `pr-description-sync` and accept the proposed update.

### `conversational-fluff` — "Hey team!", "I've been working on this for…"

**Pattern**: PR body opens with greeting + first-person narrative.

**Fix**: strip greeting; replace with structured Summary section per `format-pr.md`.

### `embedded-trailer` — `Co-authored-by:` line inside the PR body

**Pattern**: PR body contains a trailer-format line (`^[A-Z][a-zA-Z-]+:\s`) not at the very end of a structured section.

**Fix**: drop. Trailers belong in commit messages, not PR bodies (where they would only end up in the squash-commit message anyway if `squash_merge_commit_message == "PR_BODY"`, and that's usually unintended).

## Cross-cutting smells

### `mixed-scope` — one commit changes wholly unrelated areas

**Pattern**: `git show --name-only <sha>` touches files in two or more top-level directories that have no historical co-change pattern.

**Fix**: split into separate commits via `git reset HEAD~ && git add -p && git commit` per logical group. The body should justify why a bundled commit makes sense if you decide to keep it bundled.

### `repeated-fix` — "fix typo", "fix typo again", "fix actual typo"

**Pattern**: three or more consecutive commits where the subject contains `fix` and shares >50% token overlap (`typo`, `lint`, `format`, `style`).

**Fix**: squash via `rebase-cleanup` (autosquash) or `commit-fixup` if caught mid-work.

### `manual-revert` — commit semantically undoes earlier work without using `git revert`

**Pattern**: `git diff <earlier>..<later>` on a file shows the later commit removes lines the earlier added (or vice versa), and the later commit subject does not contain `revert`.

**Fix**: surface as a `MAYBE` finding — the manual undo may be intentional (different motivation than the original change) or accidental (could squash both away). Let the user decide.
