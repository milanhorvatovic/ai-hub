# Format conventions: commit subject, commit body, PR title, PR description

Load this when any capability needs to decide whether a commit message or PR body conforms to the repo's format rules, or when drafting one from scratch.

## Precedence

Repo conventions override these defaults. Check in order:

1. `CLAUDE.md` / `AGENTS.md` — agent-facing rules. If they specify commit or PR format, use it verbatim.
2. `CONTRIBUTING.md` — human contributor guide. Often contains the canonical format.
3. `.commitlintrc*`, `commitlint.config.*`, `.czrc`, `.gitlint`, `.gitmessage` — lint configs and templates declare the format machine-checks enforce.
4. `.github/PULL_REQUEST_TEMPLATE.md` (and variants — see `pr-template-detection.md`) — defines PR body structure.
5. These defaults — only when nothing above is present.

If multiple sources conflict, the order above wins.

## Commit subject line

- **Imperative mood** — "Add X" / "Fix Y" / "Refactor Z", not "Added X", "Adds Y", "Fixed Z". The convention is "If applied, this commit will ___".
- **≤72 characters** hard, ≤50 ideal. GitHub truncates at 72 in most UIs; `git log --oneline` becomes unreadable past that.
- **No trailing period.** Subject is a title, not a sentence.
- **No leading capitalization rule by default** — follow the repo's existing convention (check the last ~20 commits with `git log --pretty=format:'%s' -20`).
- **Single line.** First newline ends the subject.

### Conventional commits (when the repo uses them)

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

### What makes a good subject

- Specific verb + specific object: `Fix race in token-refresh queue` not `Fix bug`.
- Says WHAT changed, not how it was changed: `Replace JSON parser with streaming reader` not `Use streamlined approach in parser`.
- Says it from the user's perspective for `feat`/`fix`; from the maintainer's perspective for `refactor`/`chore`.

### Subject contents — required and forbidden

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
| Author / date / version metadata (`v1.4: add X`, `[Alice] update Y`) | Tags + trailers carry attribution; subjects are for the change itself |
| Emoji prefixes (`✨ Add X`) | Repo-specific style — only use if the repo's last ~20 commits all use them |
| `!` breaking-change marker without `BREAKING CHANGE:` footer in body | The marker is a claim; the body must explain the breakage and migration |

## Commit body

- **Blank line after subject.** Required. Many tools (including GitHub's UI) merge subject and body if missing.
- **Wrapped at 72 chars** unless the repo overrides (e.g. `.gitconfig` `core.commentChar` with non-default wrap). Wrapping is for the reader of `git log` in a terminal; long-form prose is fine if the repo doesn't enforce.
- **Explains WHY, not WHAT** in most cases — the diff shows what. The body explains motivation, alternatives considered, constraints discovered, trade-offs.
- **Links to context** — issue numbers (see `issue-references.md`), design docs, ADRs, prior PRs.
- **No marketing language** — "we are excited to announce", "this awesome change", "amazing improvement". Drop it.
- **Trailers** go at the end after a blank line. See `trailer-semantics.md`.

### Body structure (loose)

```
<subject line ≤72 chars>

<paragraph explaining motivation — why was this needed?>

<optional paragraph on alternatives considered or trade-offs>

<optional paragraph on follow-ups or known limitations>

<optional BREAKING CHANGE footer for breaking commits>
BREAKING CHANGE: <one-line description>
<multi-line migration notes>

<optional trailers — only when user-requested>
Refs: #123
Signed-off-by: Name <email>
```

Short, well-scoped commits often don't need a body at all — subject is enough. Don't pad just to have a body.

### Body required vs optional vs none

**Body is REQUIRED when:**

- Breaking change (subject has `!` marker) → body must contain `BREAKING CHANGE: <description>` footer with migration notes
- Performance change claiming a measurable improvement → body must state the measurement or benchmark
- Security-relevant change → body must state the threat being addressed (CVE, advisory, internal finding)
- Schema or data migration → body must state migration path forward + rollback
- Non-obvious refactor that changes invariants → body must state which invariant changed and why
- Commit touching multiple unrelated areas (rare; usually a smell) → body must justify why they're bundled

**Body is RECOMMENDED when:**

- The "why now" is non-obvious — there was a triggering event, a deadline, a constraint discovered late
- Multiple reasonable approaches existed — body documents alternatives considered and the trade-off
- An issue / design doc / ADR / prior PR provides context — body holds the link
- Known follow-up work or limitations exist — body holds the TODO so it's not lost
- The change is large enough that the diff alone obscures intent

**NO body needed when:**

- Subject is self-explanatory and the change is mechanical
- Small bug fix where the diff IS the explanation
- Repo convention is subject-only commits (check `git log --format='%h%n%b---' -20`)
- Dependency bumps with no companion code changes (mechanical version updates)
- Formatting / whitespace-only commits

### Body contents — required and forbidden

**Required (when a body is written):**

| Element | Why |
|---|---|
| **Blank line after subject** | Exactly one blank line — many tools (including GitHub's UI) merge subject and body when missing |
| **WHY, not WHAT** | The diff shows WHAT; the body explains motivation, constraints, context the reader can't infer from the code |
| **Context links** (issue, design doc, ADR, prior PR) | Gives the reader a way to find the conversation that led to this commit |
| **BREAKING CHANGE: footer for breaking commits** | `BREAKING CHANGE: <one-line description>` followed by detailed migration notes — required if subject has `!` |

**Forbidden in body:**

| Element | Why |
|---|---|
| Restatement of subject in past tense (`Added X. This commit adds X.`) | Redundant; says nothing new |
| File listings (`Changed: foo.py, bar.py`) | Reader uses `git show --stat`; body shouldn't duplicate the diff metadata |
| Marketing language (`amazing`, `powerful`, `exciting`, `we are excited to`) | Commit messages are engineering artifacts; drop the sales voice |
| AI-attribution trailers (`Co-Authored-By: Claude`) | Per skill principle: never auto-add trailers — only when user explicitly requests |
| Trailer-shaped lines mid-body | Trailers go at the end only — `git interpret-trailers` silently ignores mid-body trailers, causing tooling to break |
| Multi-paragraph hard-wrapped for visual width | Wrap at 72 chars per LINE; one logical paragraph = one logical paragraph, not visually-broken fragments |
| Generated content listings (lockfile diffs, generated-code summaries) | The diff already covers it |
| Time spent / cost estimates / private team metrics | Belong in PR description or team trackers, not commit history |
| Status updates (`Still working on X, will follow up`) | If status, don't commit yet — use draft PR comments instead |

### Decision tree: do I need a body?

```
Is the commit a breaking change?               → YES, body required (BREAKING CHANGE: footer)
Is it a perf / security / migration commit?    → YES, body required
Does the diff have a non-obvious WHY?          → YES, body recommended
Are there alternatives that were rejected?     → YES, body recommended
Is there a related issue / design doc / PR?    → YES, body recommended (with link)
Is the subject self-explanatory + mechanical?  → NO body needed
```

## PR title

- Same rules as commit subject — imperative, ≤72 chars, no trailing period, conventional-commits prefix where the repo uses it.
- For repos that squash-merge with `squash_merge_commit_title == "PR_TITLE"`, the PR title becomes the squash commit subject — the format rules apply doubly.

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

**Sections to consider including:**

- **Summary / Overview** — always.
- **Changes / What changed** — bulleted per-area, especially for multi-area PRs.
- **Test plan** — what the author verified before requesting review.
- **Screenshots / Demos** — UI changes only.
- **Migration notes / Rollout** — when the change affects production deploys, schema, or config.
- **Linked issues** — `Closes #N` / `Refs #N` per `issue-references.md`.

**When the repo squash-merges with `sm == "PR_BODY"`:** drop markdown headings, use flat prose. The body becomes the commit message; `## Summary` literal text ends up in `git log`. See `merge-policy.md` for the squash-with-`PR_BODY` template.

## Tone

- Past tense for what the PR did (in the body): "Added retry logic to the consumer."
- Present tense for what the code does (in inline references): "the consumer now retries on transient failures."
- Active voice: "The parser rejects invalid tokens" not "Invalid tokens are rejected by the parser."
- No first-person plural in commit messages ("we added") — use imperative or third person.

## Anti-examples → fixed

Pair table for `commit-message` review mode and reference in write mode.

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
| `feat!: change auth API` (no body) | Subject + `BREAKING CHANGE: clients must now send Bearer tokens; X-Auth-Token removed in v3.0` in body | `!` requires a body explanation |
| `Improve performance` | `perf(parser): cache regex compilation` + body with measurement | Generic claim, no specifics |
| `update deps` | `chore(deps): bump react-router 6.20.0 → 6.21.1` | Generic + lowercase — pick one style |
| `[WIP][Alice] working on auth` | (don't commit yet) | Status + author + vague |
| `🚀 Add streaming JSON parser ✨` | `feat(parser): add streaming JSON reader` | Emoji unless repo-wide convention |
| Body: `Added a parser. This commit adds a parser.` | (drop the redundant body OR write the actual why) | Body restates subject |
| Body: `Files changed: foo.py, bar.py, baz.py` | (drop — `git show --stat` does this) | Body duplicates diff metadata |
| Body: `Signed-off-by: Claude` (auto-added) | (drop — only add trailers on user request) | Auto-added attribution trailer |
