# NDJSON event schema

Every entry shim emits one JSON object per line on stdout. Each object has three fields: `event` (string, see EventType table below), `tool` (string, the tool name or sentinel like `"all"` / `"fix-cycle"`), and `detail` (string or object, shape depends on event type).

Consumers should parse one line at a time and dispatch by `event`. Schema is stable within a major version.

## EventType table

| Event | Tool field | Detail shape | When emitted |
|---|---|---|---|
| `available` | tool name | string (version string) | `probe.py`: each tool found on PATH |
| `installed` | tool name | string (version string) | `recommend-tools.py`: each tool already installed |
| `missing` | `"all"` or tool name | string (install hint) | `probe.py` exit 3; `md-audit.py` / `md-format.py` when no usable formatter; `md-audit-frontmatter.py` when yamllint absent |
| `recommend` | tool name | `{"priority_rank": int, "install_options": list[str]}` | `recommend-tools.py`: one per missing priority tool |
| `verdict` | tool name or `"none"` | string | `recommend-tools.py`: single summary event tied to exit code |
| `selected` | tool name | Pipeline-specific — see `selected` variants below | `md-audit` / `md-format` / `md-fix` (markdown formatter shape); `md-audit-frontmatter` (yamllint shape) |
| `bundled-config` | tool name | string (config path) | When a bundled fallback config is applied (baseline = universal-subset and tool has a bundled config) |
| `finding` | tool name | string (one line of formatter output) | `md-audit.py` / `md-fix.py` audit phase: per-finding line from the formatter |
| `changed` | tool name | string (one line of formatter output) | `md-format.py` write mode: per-file change line |
| `would-change` | tool name | string (one line of formatter check output) | `md-format.py --dry-run`: per-file would-change line |
| `clean` | tool name | string (human message) | When the chosen tool returns exit 0 with no findings/changes |
| `error` | tool name | `{"exit": int, "stderr"?: str}` (tool returned non-zero; `stderr` carries the failing-run diagnostic when present), `{"file": str, "reason": str}` (per-file unreadable), or string | When the chosen tool returns exit ≥ 2 (config error, plugin missing, etc.) OR — for `md-audit-frontmatter` — a target file fails to read (deleted between discovery and audit, encoding error, permission denied); see `error` variants below |
| `plugin-available` | `"mdformat"` | `{"plugin": str, "package": str, "version": str}` | `probe.py`: each detected mdformat plugin (mdformat-gfm, mdformat-tables, etc.) |
| `plugin-missing` | `"mdformat"` | `{"plugin": str, "package": str, "file": str, "reason": str}` | When mdformat is selected and a target file contains syntax requiring an absent plugin (today: GFM detection for `mdformat-gfm`) |
| `delta` | `"fix-cycle"` | `{"resolved": int, "still_open": int, "new": int}` | `md-fix.py`: single summary at the end of the audit → format → re-audit loop |

## Field-detail reference

### `selected` (most complex)

Two variants — the markdown formatter pipeline and the yamllint frontmatter pipeline emit different `detail` shapes. Consumers should branch on `mode` (`"audit"` / `"format"` mean the markdown shape; `"audit-frontmatter"` means the yamllint shape).

#### Markdown formatter variant

Emitted once per `md-audit` / `md-format` / `md-fix` invocation (and once per phase of fix-cycle).

| Field | Type | Meaning |
|---|---|---|
| `baseline` | string | The style-baseline config filename detected (`.markdownlint.json`, etc.) or `"universal-subset"` |
| `mode` | string | `"audit"` or `"format"` |
| `unwrap` | bool | Whether `--unwrap` was passed (adds `--prose-wrap=never` / `--wrap=no` to the cmd) |
| `config_source` | string | `"repo"` (repo declares config), `"bundled"` (bundled fallback used), or `"tool-default"` (no config passed) |
| `cmd` | string | The exact formatter argv as a space-joined string |
| `files_scoped` | int or null | Count of positional file args, or null when scope is the formatter's default glob |
| `dry_run` | bool | Whether `--dry-run` was passed (md-format only); always false for md-audit |

#### Frontmatter audit variant

Emitted once per `md-audit-frontmatter` invocation by `yaml_audit.audit_frontmatter`. The `tool` field on the event is always `"yamllint"`.

| Field | Type | Meaning |
|---|---|---|
| `mode` | string | Always `"audit-frontmatter"` |
| `config_source` | string | `"repo"` (caller passed `--yamllint-config`), `"bundled"` (bundled fallback yamllint.yaml), or `"tool-default"` (no config available) |
| `config_path` | string or null | Resolved absolute path of the yamllint config in use, or null when no config could be resolved |
| `files_scanned` | int | Count of markdown files the audit walked |

Notes:
- The frontmatter variant does NOT include `baseline`, `unwrap`, `cmd`, `files_scoped`, or `dry_run` — those are markdown-pipeline-specific concepts.
- Field-stability guarantees apply per-variant — adding fields to one variant doesn't imply adding them to the other.

### `recommend`

| Field | Type | Meaning |
|---|---|---|
| `priority_rank` | int | 1-based rank in `INSTALL_PRIORITY` (1 = top priority) |
| `install_options` | list[str] | Platform-specific install commands the user can run |

### `error`

Two variants. Consumers should branch on `isinstance(detail, dict) and "file" in detail` to distinguish.

#### Exit-code variant

Emitted once per pipeline when the chosen formatter exits ≥ 2 (config error, plugin missing, etc.) or returns a negative `returncode` (signal-killed: `-SIGTERM` → -15, `-SIGKILL` → -9). The `stderr` field carries the failing-run diagnostic verbatim (whitespace-stripped) when the tool produced any; the field is omitted entirely when stderr was empty, so a consumer can branch on `"stderr" in detail`.

```json
{"event": "error", "tool": "prettier", "detail": {"exit": 2, "stderr": "Invalid configuration: unknown option 'tabWdith'"}}
```

```json
{"event": "error", "tool": "prettier", "detail": {"exit": 2}}
```

Successful runs filter stderr out of the event stream (banner / deprecation noise would otherwise become spurious `finding` / `changed` events under FORMAT mode). The exit-code variant is the only path that attaches stderr; AUDIT mode still concatenates stderr into the `finding` stream because some tools emit real findings there.

#### Per-file unreadable variant

Emitted by `md-audit-frontmatter` once per file the audit could not read (deleted between discovery and audit, encoding error, permission denied). Emitted inline alongside the per-file processing order so consumers can correlate the failure with surrounding `finding` events:

```json
{"event": "error", "tool": "yamllint", "detail": {"file": "/repo/missing.md", "reason": "FileNotFoundError: [Errno 2] No such file or directory: '/repo/missing.md'"}}
```

The aggregate exit code stays 2 whenever any per-file error fires, even when real `finding` events also surface (see "Exit codes" below).

### `delta` (md-fix only)

```json
{"event": "delta", "tool": "fix-cycle", "detail": {"resolved": 3, "still_open": 1, "new": 0}}
```

Computed by comparing finding-line sets between pre-format audit and post-format audit. `resolved` = findings present pre but absent post; `still_open` = findings present in both; `new` = findings present post but absent pre.

## Exit codes

Uniform across all entry shims:

| Exit | Meaning |
|---|---|
| 0 | Clean (no findings or no changes needed) |
| 1 | Findings present, files changed, or fix-cycle left findings unresolved |
| 2 | Formatter invocation error (returncode ≥ 2), OR — for `md-audit-frontmatter` — any target file was unreadable (per-file ERROR events emit inline; lint findings, when also present, still appear in the event stream but the aggregate exit code stays 2 so consumers don't misread "audit found problems" as "audit setup is fine") |
| 3 | No usable tool on PATH |

Exception: `recommend-tools.py` uses exit 0 when the top-priority tool is installed, 1 when at least one priority tool is missing.

## Stability guarantees

- **Event names** are stable within a major version. Adding new event types is a minor-version change.
- **Detail fields** are additive within a major version. New fields may appear; existing fields may not be removed or change type.
- **Detail value formats** (e.g. version strings, install commands) follow upstream tool conventions and are not guaranteed stable across upstream releases.
