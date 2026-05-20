# Format conventions: commit subject + PR title

Subject-line rules for git commits, with the same rules applied (and noted as such) to PR titles. Load this when a capability is drafting or validating a single-line title — commit subject or PR title.

For body / paragraph rules, see `format-body.md`. For PR description structure beyond the title, see `format-pr.md`. For Precedence (which sources override which), see the `format-conventions.md` index.

## Subject-line rules

- **Imperative mood** — "Add X" / "Fix Y" / "Refactor Z", not "Added X", "Adds Y", "Fixed Z". The convention is "If applied, this commit will ___".
- **≤72 characters** hard, ≤50 ideal. GitHub truncates at 72 in most UIs; `git log --oneline` becomes unreadable past that.
- **No trailing period.** Subject is a title, not a sentence.
- **No leading capitalization rule by default** — follow the repo's existing convention (check the last ~20 commits with `git log --pretty=format:'%s' -20`).
- **Single line.** First newline ends the subject.

## Conventional commits (when the repo uses them)

Detect via: `.commitlintrc*` config, `commitlint.config.*` with `@commitlint/config-conventional`, OR observation — if the last ~20 commit subjects all match `^(feat|fix|chore|docs|refactor|test|perf|build|ci|style|revert)(\([^)]+\))?!?:\s`, the repo uses conventional commits.

Format: `<type>(<scope>)<!>: <description>`

| Type | When |
|---|---|
| `feat` | New user-facing feature |
| `fix` | Bug fix |
| `chore` | Maintenance, no user-visible change |
| `docs` | Documentation only |
| `refactor` | Code change with no behavior change |
| `test` | Adding / updating tests |
| `perf` | Performance improvement |
| `build` | Build system / dependencies |
| `ci` | CI configuration |
| `style` | Whitespace, formatting, semicolons |
| `revert` | Reverts a previous commit |

- `(<scope>)` is optional — a noun like `api`, `parser`, `auth`. Use a scope present in past commits when possible (consistency > novelty).
- `!` after type/scope indicates a breaking change. Also requires `BREAKING CHANGE:` footer in body.
- Subject after `: ` follows the same rules as a plain subject (imperative, ≤72 chars total *including* the prefix).

## What makes a good subject

- Specific verb + specific object: `Fix race in token-refresh queue` not `Fix bug`.
- Says WHAT changed, not how it was changed: `Replace JSON parser with streaming reader` not `Use streamlined approach in parser`.
- Says it from the user's perspective for `feat`/`fix`; from the maintainer's perspective for `refactor`/`chore`.

## Subject contents — required and forbidden

**Required (must be present):**

| Element | Why |
|---|---|
| **Specific verb** in imperative mood | The reader must know what the commit DOES — `Add`, `Remove`, `Refactor`, `Fix`, `Rename`, `Extract`. Not `Update`, `Change`, `Improve`, `Tweak`. |
| **Specific noun** (the thing being changed) | `the retry queue`, `auth middleware`, `JSON parser` — not `the code`, `things`, `stuff` |
| **Smallest accurate description** | If the change fits in 50 chars, don't pad to 72. Pad-to-length looks like effort but says less. |

**Forbidden (must NOT be present):**

| Element | Why |
|---|---|
| Past tense verb (`Added`, `Fixed`, `Removed`) | Convention: "If applied, this commit will ___" — imperative |
| Trailing period | Subject is a title, not a sentence |
| Generic verbs alone (`Update X`, `Change Y`, `Fix bug`, `Tweak config`) | Without a specific noun and outcome, the subject says nothing |
| Status markers (`WIP`, `[WIP]`, `TODO`, `XXX`, `temp`) | Committed commits must be complete; status markers leak draft state — squash before commit |
| Issue numbers in subject (`Fix retry bug #123`) | Issue refs belong in body or trailers; pollutes `git log --oneline` |
| File names or paths (`src/foo.py: fix race`) | Reader uses `git log --stat` / `--name-only` for files; subject is for intent |
| Implementation detail (`Use regex for retry`, `Switch from map() to forEach()`) | The outcome matters, not the technique — reader sees the diff for technique |
| Author / date / version metadata (`v1.4: add X`, `[author] update Y`) | Tags + trailers carry attribution; subjects are for the change itself |
| Emoji prefixes (`✨ Add X`) | Repo-specific style — only use if the repo's last ~20 commits all use them |
| `!` breaking-change marker without `BREAKING CHANGE:` footer in body | The marker is a claim; the body must explain the breakage and migration |

## PR title note

PR titles follow the same rules as commit subjects: imperative, ≤72 chars, no trailing period, conventional-commits prefix where the repo uses it. For repos that squash-merge with `squash_merge_commit_title == "PR_TITLE"`, the PR title becomes the squash commit subject — the format rules apply doubly. See `merge-policy.md` for the merge-mode interaction.

## Anti-examples → fixed (subject only)

| Bad | Good | What's wrong |
|---|---|---|
| `Update parser.py` | `feat(parser): add streaming JSON reader` | Generic verb + file path; doesn't say WHAT or WHY |
| `Fix bug` | `fix(auth): handle expired token in refresh path` | No scope + no specific bug named |
| `Address review comments` | `fix(api): handle null in response_dict` | Describes the cause (review) instead of the fix |
| `WIP: try new approach` | (don't commit — squash into prior or `git stash`) | Status markers don't ship to history |
| `Fix bug #123 in retry logic` | Subject: `fix(retry): clear backoff on success` + body: `Closes #123` | Issue ref out of subject |
| `Refactor src/foo.py to use map()` | `refactor(foo): simplify item transformation` | Drop file path + implementation detail |
| `Added X to do Y.` | `Add X to do Y` | Past tense + trailing period |
| `Tweak config` | `chore(ci): bump runner timeout from 5m to 10m` | "Tweak" + "config" are non-information |
| `feat!: change auth API` (no body) | Subject + `BREAKING CHANGE: …` in body | `!` requires a body explanation |
| `Improve performance` | `perf(parser): cache regex compilation` + body with measurement | Generic claim, no specifics |
| `update deps` | `chore(deps): bump react-router 6.20.0 → 6.21.1` | Generic + lowercase — pick one style |
| `[WIP][author] working on auth` | (don't commit yet) | Status + author + vague |
| `🚀 Add streaming JSON parser ✨` | `feat(parser): add streaming JSON reader` | Emoji unless repo-wide convention |
