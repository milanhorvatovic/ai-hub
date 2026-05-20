# Output format

How scan and audit results are presented. One human-readable markdown report,
plus an optional machine-readable NDJSON finding stream for tooling.

## scan output

A snapshot, grouped by domain, every line citing its source:

```markdown
# <repo-name> — <domain> conventions (scan)

Scanned <YYYY-MM-DD>, <N> source files.

- **<convention>:** <value>. Source: `<file>`.
- **<convention>:** <value>. (inferred from git history; not declared)

## Conflicts
- [CONFLICT] `<file-A>` says <X> but `<file-B>` says <Y>.
```

## audit output

The scan plus judgment. Each finding carries a severity and a one-line *why*,
and the section closes with a domain score from `oss-health-rubric.md`:

```markdown
# <repo-name> — <domain> audit

Health: <NN>% (<satisfied>/<applicable> weighted checks)

## Findings
- [must] Missing `<file>`. <why it matters for an OSS repo>. → scaffold available
- [should] `<file>` present but <weakness>. Source: `<file>`. → fix suggested
- [could] Consider `<file>`. <upside>.

## Already solid
- `<file>` — <what's good about it>. Source: `<file>`.
```

For a **full-repo audit**, emit one `audit` section per domain, then a roll-up:

```markdown
# <repo-name> — repository health audit

Overall health: <NN>%   (GitHub community profile: <NN>%)

## Priorities
1. [must] …
2. [should] …
3. [could] …

Domain scores: licensing <NN>% · security <NN>% · … 
```

## NDJSON findings (optional, for tooling)

When the user or a calling tool wants machine-readable output, emit one JSON
object per finding, newline-delimited:

```
{"domain":"licensing","check":"license-present","severity":"must","status":"fail","file":null,"message":"No LICENSE at repo root","scaffold":"capabilities/licensing"}
{"domain":"security-policy","check":"security-md","severity":"should","status":"pass","file":".github/SECURITY.md","message":"Disclosure policy present"}
```

Fields: `domain`, `check` (kebab-case id), `severity` (`must`/`should`/`could`),
`status` (`pass`/`fail`/`warn`/`skip`), `file` (source path or `null`),
`message`, and optional `scaffold` (capability that can generate the fix).

## Rules

- Never assert a convention without a source; use `(inferred …)` or `(not declared)`.
- Show unmet `must`/`should` items next to any score — the number alone isn't actionable.
- Write reports to `mktemp` *and* show inline, so the user can save or paste them.
- Offer the next action (`scaffold` for a `must`/`should`) rather than just listing the gap.
