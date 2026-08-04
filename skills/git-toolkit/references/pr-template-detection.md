# PR template detection: paths, parsing, unfilled-detection

Load this when a capability needs to determine whether a PR description is an unfilled template, or which template a new PR description should follow.

## Template path resolution

GitHub looks for PR templates in these locations, case-sensitive on case-sensitive filesystems but the GitHub UI accepts both cases. Check all of them in order; first non-empty match wins for the "primary template":

1. `.github/PULL_REQUEST_TEMPLATE.md`
2. `.github/pull_request_template.md` (lowercase variant — common in older repos)
3. `PULL_REQUEST_TEMPLATE.md` (repo root)
4. `pull_request_template.md` (repo root, lowercase)
5. `docs/PULL_REQUEST_TEMPLATE.md`
6. `docs/pull_request_template.md`
7. Every `*.md` under `.github/PULL_REQUEST_TEMPLATE/` (multi-template directory — each file is a separate selectable template the user can pick via `?template=foo.md` query param)

For multi-template repos, the user could have started from any of the templates in `.github/PULL_REQUEST_TEMPLATE/`. Check each one against the body and treat as "unfilled" if any matches the threshold below.

### Other forges

Template detection is an on-disk read, so it works on every forge — only the paths differ:

- **GitLab** — `.gitlab/merge_request_templates/*.md` on the default branch; each file is a selectable template (the GitLab analog of the multi-template directory). A template named `Default.md` (case-insensitive) auto-applies to new MRs; projects on paid tiers can instead set a default in project settings, which takes priority over `Default.md`.
- **Gitea / Forgejo (Codeberg)** — single template only, no PR-template chooser: `PULL_REQUEST_TEMPLATE` / `pull_request_template` with `.md` / `.yaml` / `.yml`, in the repo root, `.gitea/`, or `.github/`; Forgejo also reads `.forgejo/`. First match wins.
- **Bitbucket Cloud** — no repository-file PR-template convention; skip template detection.

The parsing, comment-stripping, and unfilled-threshold rules below are forge-independent.

## Comment stripping

Strip HTML comments from both the template content and the current PR body before comparing:

```
re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
```

HTML comments are template hints (`<!-- describe your change here -->`) that the user is expected to delete. Counting them as "matching content" would over-trigger the unfilled detection.

After stripping, also normalize whitespace: collapse runs of whitespace to a single space, strip leading/trailing whitespace per line. Don't drop newlines entirely — preserve structural breaks.

## Unfilled-detection threshold

Compute the verbatim overlap between the stripped template and the stripped body. Definition: the length of the longest common subsequence of the whitespace-normalized template and body, divided by the length of the whitespace-normalized template. Both operands are the normalized strings from the step above, so the single spaces that survive normalization are counted consistently in numerator and denominator.

```
overlap_ratio = len(longest_common_subseq(template, body)) / len(template)
```

(Substring match is a fast approximation if LCS is too expensive — `overlap_ratio = len(longest_common_substring(template, body)) / len(template)`. Both work for the threshold below.)

If `overlap_ratio > 0.6` → treat as **template not filled in**.

The 0.6 threshold is empirical: real PR descriptions that legitimately reuse template structure (kept `## Summary` and `## Test plan` headings) hit around 0.3–0.5 overlap because the user added body content under each heading. Truly unfilled templates hit 0.85+.

## Partial-fill case

A user might fill in `## Summary` but leave `## Test plan` and `## Migration notes` empty. This is NOT unfilled — the user made an authoring decision. Don't flag as MAJOR-REWRITE just because some sections are empty. The 60% threshold handles this naturally because the overall overlap is lower.

The exception: if the template explicitly says `<!-- DELETE THIS LINE -->` and that line still appears in the body verbatim, treat as a separate "template literal hint not removed" warning — but not as MAJOR-REWRITE.

## Using templates when authoring from scratch

When `pr-description` WRITE mode is drafting a new body and a template exists:

1. Pick the primary template (first match from the path order above).
2. Use the template's section headings VERBATIM — the team has already agreed on these.
3. Preserve HTML comments that look like instructional hints (the user can delete them when they review the proposal).
4. Fill in each section from the diff inventory; if a section doesn't apply (e.g. `## Screenshots` for a backend PR), leave the heading and write `N/A` or omit the heading entirely (check repo convention by looking at recent merged PRs' bodies).

When NO template exists, use the generic structure from `format-conventions.md` (Summary / Changes / Test plan / Notes).

## When detection should be skipped

- Repo has no template files at any of the paths above → skip detection entirely.
- The PR is bot-authored (filtered at the bot guard) → skip; bot descriptions follow their own structure.
- The PR body is empty (zero non-whitespace chars) → already MAJOR-REWRITE by the empty-body rule; template detection adds no new information for the verdict but is still useful to `pr-description` WRITE mode for picking which template to fill.
