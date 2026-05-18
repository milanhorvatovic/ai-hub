# Review output format

Canonical output schema for any capability that runs in REVIEW mode (auditing existing commits, PR bodies, branch state) and emits per-rule findings. Load this when a capability needs to produce a review report.

## Why standardize

Without a shared schema, every capability invents its own table layout, every reviewer reads in a different shape, and tooling cannot consume the output programmatically. The goal: one structure that is human-readable inline and machine-parseable when emitted as NDJSON.

## Markdown table schema (human-facing)

The default human output is a markdown table with these columns:

| Rule | Result | Details |
|---|---|---|
| <rule name> | PASS / MOSTLY PASS / FAIL / N/A | <one-line specifics; commit SHA, line number, or quoted excerpt> |

- **Rule** — the rule's short name, taken verbatim from the spec it references (`Imperative mood`, `≤72 char subjects`, `Trailers auto-added`).
- **Result** — exactly one of `PASS`, `MOSTLY PASS`, `FAIL`, `N/A`. Reserve `N/A` for rules that do not apply to the target (e.g., trailer rules on a commit with no trailers).
- **Details** — for `FAIL` and `MOSTLY PASS`, name the offending commits by short SHA, and quote the offending excerpt. For `PASS`, leave blank or write the max observed (e.g., `longest is 57`). Keep details to one line; deeper context goes in the per-finding section below.

After the table, list each `FAIL` and `MOSTLY PASS` finding as a separate block:

```markdown
### Finding: <rule name> on <sha or scope>

<one-paragraph explanation of what is wrong>

**Proposed fix:** <one paragraph or code block showing the corrected message / state>

**Apply with:** <exact command — never auto-execute>
```

Findings with the same rule on multiple commits group under a single heading with a sub-list. No finding section is emitted for `PASS` or `N/A` rows.

## NDJSON schema (machine-facing)

When the invoking agent or pipeline wants programmatic output, emit one JSON object per finding on stdout. One object per row of the table above; rows with `result: "PASS"` may be elided depending on a `--include-pass` flag.

```jsonl
{"rule": "imperative-mood", "result": "PASS", "scope": "branch", "ref": "add-skill-foo", "count_checked": 16, "count_failed": 0}
{"rule": "subject-length", "result": "PASS", "scope": "branch", "ref": "add-skill-foo", "max_length": 57, "limit": 72}
{"rule": "body-wrap", "result": "FAIL", "scope": "commit", "sha": "f902472", "subject": "Extend Windows entries in .gitignore", "details": {"line": 5, "length": 74, "limit": 72, "excerpt": "- Thumbs.db:encryptable — NTFS-encrypted variant of the thumbnail cache."}, "fix": "Reflow paragraph to one line (flowing default) or wrap at column 72."}
```

Keys:

- `rule` — kebab-case rule identifier matching the rule's section in `format-conventions.md` or similar reference.
- `result` — `PASS` / `MOSTLY-PASS` / `FAIL` / `N/A`.
- `scope` — `commit` / `branch` / `pr` / `range`.
- `ref`, `sha`, `subject` — identifying fields for the target.
- `details` — rule-specific structured data; the fields vary per rule but `excerpt` is reserved for a verbatim quote.
- `fix` — short imperative describing the corrective action; never includes an apply command (those go in human output only).

The schema is also published as JSON Schema at `review-output.schema.json` (Draft 2020-12). Consumers can validate NDJSON streams with any standards-compliant validator (`ajv-cli`, `check-jsonschema`, etc.). The schema enforces: `scope=commit` requires `sha`; `scope=branch/range/pr` requires `ref`; `FAIL` and `MOSTLY-PASS` results require a `fix` string.

A worked example stream lives at `review-output.example.ndjson` — 15 findings covering PASS / MOSTLY-PASS / FAIL / N/A across commit / branch / pr / range scopes, including aggregate PASS counts, single-commit FAIL findings with `fix` imperatives, a PR-body MOSTLY-PASS with an excerpt, and a final verdict aggregate. Tests can use this file as a schema-validation fixture; new consumers can read it to see the schema applied to realistic findings rather than reading the schema in isolation.

## Verdict line

At the end of the report (both human and NDJSON), emit a single-line verdict:

- `COMPLIANT` — all rules `PASS` or `N/A`.
- `COMPLIANT with N minor fix(es) recommended` — only `MOSTLY PASS` findings, no `FAIL`.
- `NOT COMPLIANT (N FAIL, M MOSTLY PASS)` — at least one `FAIL`.

The verdict is what most readers will skim first; everything else is supporting detail.

## What this does NOT specify

- The set of rules to check — that comes from `format-conventions.md` and per-capability specs.
- How to format the apply commands — that follows the conventions of the invoking shell.
- Whether to auto-apply fixes — capabilities never auto-apply; this format is read-only output.
