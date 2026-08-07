# Review output format

Canonical output schema for any capability that runs in REVIEW mode (auditing existing commits, PR bodies, branch state) and emits per-rule findings. Load this when a capability needs to produce a review report.

## Why standardize

Without a shared schema, every capability invents its own table layout, every reviewer reads in a different shape, and tooling cannot consume the output programmatically. The goal: one structure that is human-readable inline and machine-parseable when emitted as NDJSON.

## Markdown table schema (human-facing)

The default human output is a markdown table with these columns:

| Rule | Result | Details |
| --- | --- | --- |
| <rule name> | PASS / MOSTLY-PASS / FAIL / N/A | <one-line specifics; commit SHA, line number, or quoted excerpt> |

- **Rule** — the rule's short name, taken verbatim from the spec it references (`Imperative mood`, `≤72 char subjects`, `Trailers auto-added`).
- **Result** — exactly one of `PASS`, `MOSTLY-PASS`, `FAIL`, `N/A`. Reserve `N/A` for rules that do not apply to the target (e.g., trailer rules on a commit with no trailers).
- **Details** — for `FAIL` and `MOSTLY-PASS`, name the offending commits by short SHA, and quote the offending excerpt. For `PASS`, leave blank or write the max observed (e.g., `longest is 57`). Keep details to one line; deeper context goes in the per-finding section below.

After the table, list each `FAIL` and `MOSTLY-PASS` finding as a separate block:

```markdown
### Finding: <rule name> on <sha or scope>

<one-paragraph explanation of what is wrong>

**Proposed fix:** <one paragraph or code block showing the corrected message / state>

**Apply with:** <exact command — never auto-execute>
```

Findings with the same rule on multiple commits group under a single heading with a sub-list. No finding section is emitted for `PASS` or `N/A` rows.

## NDJSON schema (machine-facing)

When the invoking agent or pipeline wants programmatic output, emit one JSON object per finding on stdout. The stream keeps per-target granularity where the table aggregates: a rule that passes or doesn't apply emits one aggregate object (scope `branch` / `range`, typically carrying `count_checked` / `count_failed`), while every `FAIL` / `MOSTLY-PASS` finding emits one object per offending target (scope `commit` / `pr`, with `sha` or `ref`, an excerpt, and a `fix`). Aggregate `PASS` objects may be elided depending on a `--include-pass` flag.

```jsonl
{"rule": "imperative-mood", "result": "PASS", "scope": "branch", "ref": "add-skill-foo", "count_checked": 16, "count_failed": 0}
{"rule": "subject-length", "result": "PASS", "scope": "branch", "ref": "add-skill-foo", "count_checked": 16, "count_failed": 0, "max_length": 57, "limit": 72}
{"rule": "body-wrap", "result": "FAIL", "scope": "commit", "sha": "f902472", "subject": "Extend Windows entries in .gitignore", "details": {"line": 5, "length": 74, "limit": 72, "excerpt": "- Thumbs.db:encryptable — NTFS-encrypted variant of the thumbnail cache."}, "fix": "Reflow paragraph to one line (flowing default) or wrap at column 72."}
```

Keys:

- `rule` — kebab-case rule identifier from the rule-id registry (below).
- `result` — `PASS` / `MOSTLY-PASS` / `FAIL` / `N/A`.
- `scope` — `commit` / `branch` / `pr` / `range`.
- `ref`, `sha`, `subject` — identifying fields for the target.
- `details` — rule-specific structured data; the fields vary per rule but `excerpt` is reserved for a verbatim quote.
- `fix` — short imperative describing the corrective action; never includes an apply command (those go in human output only).

The schema is also published as JSON Schema at `review-output.schema.json` (Draft 2020-12). Consumers can validate NDJSON streams with any standards-compliant validator (`ajv-cli`, `check-jsonschema`, etc.). The schema enforces: `scope=commit` requires `sha`; `scope=branch/range/pr` requires `ref`; `FAIL` and `MOSTLY-PASS` results require a `fix` string; and the `rule` enum enforces registry membership — a finding with an id outside the registry fails validation.

A worked example stream lives at `review-output.example.ndjson` — 14 findings covering PASS / MOSTLY-PASS / FAIL / N/A across commit / branch / pr / range scopes, including aggregate PASS counts, single-commit FAIL findings with `fix` imperatives, a PR-body MOSTLY-PASS with an excerpt, and a final verdict aggregate. Tests can use this file as a schema-validation fixture; new consumers can read it to see the schema applied to realistic findings rather than reading the schema in isolation.

## Rule-id registry

Every `rule` id in a stream resolves to a single registry with two halves:

1. **Smell ids** — every `` ### `<id>` `` entry in `commit-smells.md` (25 rules). Detection patterns, fixes, and before/after examples live there.
2. **Check and meta ids** — the table below: checks that grade a format property rather than detect a smell, plus the meta rows a report carries. They have no catalog entry; this table is their definition.

| Id | Class | Meaning |
| --- | --- | --- |
| `conventional-commits-prefix` | check | Subject carries the repo's conventional-commits prefix; `N/A` when the repo doesn't use them |
| `body-wrap` | check | Body lines stay within the column limit — hard-wrap repos only; `N/A` under the flowing-paragraph default |
| `blank-line-after-subject` | check | Exactly one blank line separates subject and body |
| `trailer-position` | check | Trailers sit at the end of the body, after a blank line |
| `trailer-format` | check | Each trailer matches `^[A-Z][A-Za-z-]*: .+$` |
| `trailers-preserved` | check | A rewrite kept existing trailers byte-for-byte |
| `novel-scope` | check | Conventional-commits scope appears in the repo's recent history (a novel scope is advisory, never a hard failure) |
| `dangling-issue-ref` | check | `Closes` / `Refs` targets resolve to existing issues (best-effort) |
| `secret-leak` | check | No text matches the `secret-patterns.md` catalog |
| `multiline-subject` | check | Subject is a single line |
| `reflow-artifact` | check | A body transformation left an artifact (joined-word boundary, broken list); `details` names it — emitted by `commit-body-reflow` |
| `force-push-impact` | meta | Force-push impact bucket for the reviewed ref; `details.excerpt` carries none / mild / high per `force-push-impact.md` |
| `verdict` | meta | Final aggregate object closing every NDJSON stream (see Verdict line) |

The JSON Schema's `rule` enum is the machine form of this registry — both halves, nothing else. Adding a rule means adding it to `commit-smells.md` (smells) or to the table above (checks / meta) AND to the schema enum; the repo's test suite holds catalog, table, and enum in sync, and resolves the ids capabilities cite — rule-catalog sections, `Rule id` table columns, embedded NDJSON examples — against the enum.

**Deprecated aliases** — this note is the only place the retired spellings may appear: `past-tense-verb` and `overlong-subject` were unified into the broader `imperative-mood` and `subject-length`. Consumers with stored streams map the old ids forward; nothing emits them anymore.

## Severity mapping

Capabilities that grade checks internally with `error` / `warn` severities (e.g. commit-message REVIEW) translate them to results at emission time. The mapping is defined once, here:

| Internal severity                         | Result        |
| ----------------------------------------- | ------------- |
| `error` — hard-rule violation             | `FAIL`        |
| `warn` — soft cap, heuristic, or advisory | `MOSTLY-PASS` |
| check passed                              | `PASS`        |
| rule does not apply to the target         | `N/A`         |

Aggregation across a range: one table row per rule, not per commit. A rule's result is `FAIL` if any target trips its `error` condition, else `MOSTLY-PASS` if any target trips a `warn`, else `PASS` (`N/A` when the rule applies to no target). Per-target specifics — offending SHAs, excerpts — go in `Details`, and each `FAIL` / `MOSTLY-PASS` rule gets a finding block in the human report. The NDJSON stream is the granular complement: a passing rule emits its aggregate object, a failing rule one object per offending target (see the NDJSON schema above).

## Verdict line

At the end of the report, emit a single verdict.

**Human output** — one of these plain-text lines:

- `COMPLIANT` — all rules `PASS` or `N/A`.
- `COMPLIANT with N minor fix(es) recommended` — only `MOSTLY-PASS` findings, no `FAIL`.
- `NOT COMPLIANT (N FAIL, M MOSTLY-PASS)` — at least one `FAIL`.

**NDJSON output** — emit the verdict as a final JSON object with `rule: "verdict"`, never as a bare text line (a plain line would break the one-JSON-object-per-line contract). It carries the aggregate counts — `count_checked` / `count_failed` tally the evaluated items (commits, in a range review), while the excerpt tallies rule results — and `result` (`PASS` when compliant, `FAIL` when not), e.g. `{"rule": "verdict", "result": "FAIL", "scope": "range", "ref": "main..feature", "count_checked": 16, "count_failed": 5, "details": {"excerpt": "5 FAIL, 2 MOSTLY-PASS, 9 PASS"}, "fix": "Address the 5 FAIL findings before requesting review."}` — see `review-output.example.ndjson`.

The verdict is what most readers will skim first; everything else is supporting detail.

## What this does NOT specify

- The set of rules to check on a given run — capabilities and the optional `rules:` filter decide that; the registry above fixes only the id vocabulary.
- How to format the apply commands — that follows the conventions of the invoking shell.
- Whether to auto-apply fixes — capabilities never auto-apply; this format is read-only output.
