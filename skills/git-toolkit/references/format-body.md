# Format conventions: commit body

Body / paragraph rules for git commit messages. Load this when a capability is drafting or validating the body of a commit (anything after the blank line that follows the subject).

For subject-line rules, see `format-subject.md`. For PR description structure, see `format-pr.md`. For Precedence and Tone, see the `format-conventions.md` index.

## Body rules

- **Blank line after subject.** Required. Many tools (including GitHub's UI) merge subject and body if missing.
- **Body prose flows as paragraphs by default.** Each paragraph is a single line in the source — sentences flow together within the paragraph, blank lines separate paragraphs. Let the reader's tools (terminal, `git log`, GitHub, IDEs) soft-wrap on display. This avoids visually-broken fragments and keeps the body editable without manual reflow when text changes.
  - **Multiple paragraphs are encouraged** when the body covers distinct intents (motivation, what changed, follow-ups). Group sentences by topic; let each topic be its own paragraph.
  - **Lists**: one item per line, no internal wrap. Long items stay long; readers' tools fold them.
  - **Hard-wrap at ~72 columns is opt-in per repo, not the default.** Detect via the last ~20 commits — if `git log --pretty=format:'%b' -20 | head -100` consistently shows lines wrapped near 70–72, the repo prefers hard-wrap and you should match it. Otherwise default to flowing paragraphs.
  - **When the repo demonstrably uses hard-wrap**: measure in display columns (not UTF-8 bytes — an em-dash, smart quote, or accented letter is one column on screen even though it costs multiple bytes; `awk length` and `wc -c` report bytes and will overstate); treat 72 as a soft cap (1–3 column overshoot OK when the alternative is awkward fragmentation); never substitute display characters (em-dash → hyphen, smart quotes → ASCII, accented → unaccented) just to fit the cap (semantic regression); never rewrite a pre-existing commit body for a 1–2 column overshoot alone (the history-rewrite cost outweighs the cosmetic gain).
  - **Recipe — count display columns from a commit's body**: pipe through Python's `unicodedata` to fold combining marks and treat wide CJK characters as 2 columns. POSIX-only `awk` and `wc -c` count bytes and will mislead. Example: `git log -1 --pretty=format:'%b' <sha> | python3 -c 'import sys,unicodedata as u; [print(sum(2 if u.east_asian_width(c) in "WF" else 0 if u.category(c).startswith("M") else 1 for c in l), l) for l in sys.stdin.read().splitlines()]'` prints `<columns> <line>` for each body line. Filter to `awk '$1 > 72'` to surface real violations.
- **Explains WHY, not WHAT** in most cases — the diff shows what. The body explains motivation, alternatives considered, constraints discovered, trade-offs.
- **Links to context** — issue numbers (see `issue-references.md`), design docs, ADRs, prior PRs.
- **No marketing language** — "we are excited to announce", "this awesome change", "amazing improvement". Drop it.
- **Trailers** go at the end after a blank line. See `trailer-semantics.md`.

## Flowing vs hard-wrap: side-by-side example

Same body content, two styles. The flowing version is the default for fresh repos; the hard-wrap version is correct when the repo's last ~20 commits demonstrably use it.

**Flowing (default)** — each paragraph is one line; reader's tools soft-wrap.

```
Reorganize .gitignore by area with section headers

Same content as before, regrouped under explicit area headers so a reader can find rules by context rather than scanning a flat list. Splits Python into runtime / virtual envs / test+lint / packaging, and pulls the JetBrains and VS Code commented blocks into a dedicated Editor section.

Lists keep one item per line, no internal wrap:
- Python — runtime artifacts
- Python — virtual environments
- Python — test, coverage, type-check, lint
- Editor / IDE local state
```

**Hard-wrap at ~72 columns** — paragraphs broken to fit terminal width.

```
Reorganize .gitignore by area with section headers

Same content as before, regrouped under explicit area headers so a
reader can find rules by context rather than scanning a flat list.
Splits Python into runtime / virtual envs / test+lint / packaging,
and pulls the JetBrains and VS Code commented blocks into a dedicated
Editor section.

Lists keep one item per line, no internal wrap:
- Python — runtime artifacts
- Python — virtual environments
- Python — test, coverage, type-check, lint
- Editor / IDE local state
```

The list items are identical in both — one item per line is independent of paragraph wrap style. Only the prose paragraphs differ.

## Body structure (loose)

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

## Body required vs optional vs none

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

## Body contents — required and forbidden

**Required (when body is present):**

| Element | Why |
|---|---|
| Blank line between subject and body | Many tools merge them otherwise |
| Reason / motivation | "Why now" is what the diff cannot show |
| Specific over generic | "Resolves race in retry queue" not "fix issue" |

**Forbidden:**

| Element | Why |
|---|---|
| Restating the subject as the first body line | The reader just read it; this is duplication |
| Listing files changed | `git show --stat` does this; the body is for intent |
| Marketing language ("awesome", "excited", "amazing") | Subjective + unhelpful + dates fast |
| Auto-added attribution trailers (`Co-authored-by:` etc. without user request) | See `trailer-semantics.md` — trailers are CLAIMS |
| Apology language ("sorry for the late fix", "this should have been cleaner") | History is not a changelog of feelings |
| Personal nicknames or in-group jargon | `git log` outlives the author's tenure |

## Decision tree: do I need a body?

```
Is it a breaking change?                        → YES, body REQUIRED
Is it a perf claim?                             → YES, body REQUIRED
Is it security?                                 → YES, body REQUIRED
Is it a schema/data migration?                  → YES, body REQUIRED
Is the WHY non-obvious from the diff?           → YES, body recommended
Are there alternatives that were rejected?     → YES, body recommended
Is there a related issue / design doc / PR?    → YES, body recommended (with link)
Is the subject self-explanatory + mechanical?  → NO body needed
```

## Anti-examples → fixed (body only)

| Bad | Good | What's wrong |
|---|---|---|
| Body: `Added a parser. This commit adds a parser.` | (drop the redundant body OR write the actual why) | Body restates subject |
| Body: `Files changed: foo.py, bar.py, baz.py` | (drop — `git show --stat` does this) | Body duplicates diff metadata |
| Body: `Signed-off-by: Claude` (auto-added) | (drop — only add trailers on user request) | Auto-added attribution trailer |
