# Report format (agent-rendered)

The skill emits raw NDJSON events on stdout. An invoking agent (e.g. Claude under `/docs-steward`) aggregates them and renders the user-facing report in the shape below. The skill itself does not write a markdown report file — that's the agent's responsibility if the user wants one.

## Shape

```markdown
# Docs steward report — <repo-name>

Scanned <N> markdown files at <YYYY-MM-DD HH:MM:SS>.
Style baseline: <baseline-event-detail>     # e.g. ".prettierrc" or "universal-subset"
Fix engine: <selected-event-cmd>             # the formatter argv from the `selected` event

## Findings

- **<file>:<line-and-rule-from-formatter-output>** — <message>
- ...
```

## Per-finding rendering

Each `finding` event becomes one line. The line text is the formatter's raw output (e.g. `path/to/file.md:12 MD040/fenced-code-language Fenced code blocks should have a language specified`); the agent does not synthesize severity tiers or rule codes that the formatter didn't emit. Findings are rendered in NDJSON-stream order.

## Header fields

| Field | Source NDJSON event | Source field |
| --- | --- | --- |
| `<repo-name>` | (derived) | basename of `repo.repo_root` result |
| `<N>` | (derived) | count of distinct files mentioned across `finding` events |
| `<YYYY-MM-DD HH:MM:SS>` | (derived) | local time of the audit run |
| Style baseline | `selected` | `detail.baseline` |
| Fix engine | `selected` | `detail.cmd` |

## When the audit reports clean

If a `clean` event is present and no `finding` events, the agent renders:

```markdown
# Docs steward report — <repo-name>

Scanned <N> markdown files at <YYYY-MM-DD HH:MM:SS>.
Style baseline: <baseline>
Fix engine: <cmd>

✓ Audit passed. No findings.
```

## When the audit emits MISSING or ERROR

The agent surfaces the event detail verbatim and notes the exit code. Example for MISSING:

```markdown
# Docs steward report — <repo-name>

⚠ No usable formatter on PATH. Exit code 3.

Install hint:
> <install_options from recommend-tools.py if available>
```

For ERROR (returncode ≥ 2 from the formatter):

```markdown
# Docs steward report — <repo-name>

⚠ Formatter exited with code <N>. Output captured below.

<finding/changed event lines verbatim>
```
