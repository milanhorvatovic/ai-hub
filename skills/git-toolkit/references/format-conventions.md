# Format conventions (index)

The single load-bearing file every capability checks first. Contains Precedence (which sources of truth override which) and Tone (cross-cutting). For the detailed subject / body / PR rules, load the specific slice — this file points at each.

## Precedence

Repo conventions override these defaults. Check in order:

1. `CLAUDE.md` / `AGENTS.md` — agent-facing rules. If they specify commit or PR format, use it verbatim.
2. `CONTRIBUTING.md` — human contributor guide. Often contains the canonical format.
3. `.commitlintrc*`, `commitlint.config.*`, `.czrc`, `.gitlint`, `.gitmessage` — lint configs and templates declare the format machine-checks enforce.
4. `.github/PULL_REQUEST_TEMPLATE.md` (and variants — see `pr-template-detection.md`) — defines PR body structure.
5. The slice files below — only when nothing above is present.

If multiple sources conflict, the order above wins.

The same sources carry a second axis. Where a repository declares its private surface — a track-code series, private path prefixes, repositories it keeps unreadable — `publication-audience.md` matches those declarations exactly rather than heuristically, at the severity the declaration states. Read both axes in one pass over these files: a capability that opens `AGENTS.md` for format alone reads it twice and honors it once.

### Fresh-repo fallback

When none of the precedence sources are present and `git log --pretty=format:'%s'` shows fewer than ~5 prior commits, there is no observable convention. The capability should:

- Use the defaults from the slice files below silently — do not pause to ask the user; that adds friction without value.
- **Surface the assumption in the capability output.** Include a one-line "Inferred conventions" block in the proposal so the user can correct it before applying. Example: `Inferred conventions: no commit-lint config detected, only 1 prior commit — using defaults (plain imperative subject, flowing paragraphs, no conventional-commits prefix).`
- Treat the first 3–5 user-accepted commits in such a repo as the emergent convention; once the sample grows, switch to detect-from-history mode.

### Non-English convention detection

When the sample of last ~20 commit subjects is available but most subjects are not English, the imperative-mood and English-verb-lexicon checks become inappropriate. Heuristic: classify each sampled subject by detecting whether its first word is one of ~50 common English imperative verbs (`Add`, `Fix`, `Refactor`, `Remove`, `Update`, `Rename`, `Extract`, `Replace`, `Move`, `Bump`, `Document`, etc., plus conventional-commits prefixes `feat:`, `fix:`, etc.). If fewer than 50% of sampled subjects match, the repo's primary language is probably not English; skip imperative-mood enforcement and surface the assumption in the inferred-conventions line. The capability still applies non-language-specific rules: ≤72 columns, no trailing period, single line, no status markers, no issue numbers in subject.

## Slice files

Pick the slice you need rather than loading this index plus every rule:

| Slice | What it covers |
| --- | --- |
| `format-subject.md` | Commit subject + PR title rules: imperative mood, length cap, conventional-commits syntax, what makes a good subject, required/forbidden elements, anti-examples |
| `format-body.md` | Commit body: flowing-paragraph default, hard-wrap opt-in, body required/optional/none decision tree, body contents required/forbidden, anti-examples |
| `format-pr.md` | PR description: structure templates, sections to consider, interaction with merge mode, PR-specific anti-patterns |

Capabilities are encouraged to link directly to the slice they need (e.g., `commit-message` WRITE mode loads `format-subject.md` and `format-body.md`; `pr-description` WRITE mode loads `format-pr.md` and `format-subject.md` for the title). Linking to this index file works too — it's the legacy entry point — but adds a hop.

## Tone (cross-cutting)

Applies across commit messages, PR bodies, and release notes:

- Past tense for what a change did, in commit-message bodies and release notes: "Added retry logic to the consumer." (PR descriptions are the exception — the Summary section uses present tense, "Adds retry logic…"; see `format-pr.md`.)
- Present tense for what the code does (in inline references): "the consumer now retries on transient failures."
- Active voice: "The parser rejects invalid tokens" not "Invalid tokens are rejected by the parser."
- No first-person plural in commit messages ("we added") — use imperative or third person.
- No second-person address in commit messages ("you should…") — direct address belongs in code review, not history.
