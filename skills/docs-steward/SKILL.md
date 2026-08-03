---
name: docs-steward
description: >
  Use when markdown docs need checking or fixing, not writing: the skill
  audits and formats a repo's markdown by orchestrating the formatter its
  config declares (markdownlint-cli2 / markdownlint / prettier / mdformat /
  dprint / remark) plus a complementary lint pass, and runs a yamllint
  audit over frontmatter and fenced YAML blocks; bundled fallbacks
  fill what the repo leaves undeclared. Read-only until fixes are
  approved; emits
  NDJSON findings the invoking agent renders and offers to fix. Triggers
  on "steward the docs", "audit docs", "check docs", "review markdown",
  "format docs", "fix markdown", "audit frontmatter", "lint frontmatter",
  "recommend doc tools", pre-release sweeps, or /docs-steward. Never
  writes new prose, adds no rules beyond its bundled fallbacks, never
  auto-installs tools.
allowed-tools: Bash Read Grep Edit Write
metadata:
  version: "1.1.0" # x-release-please-version
---

# docs-steward

## Purpose

Run external markdown formatters and yamllint on existing repo docs; emit findings as NDJSON on stdout; apply the chosen formatter's `--fix` / `--write` mode on explicit approval.

## Is / is-not

- **Is:** an orchestrator that runs markdown formatters + yamllint on existing repo docs and emits findings.
- **Is not:** a doc generator, a code editor, a code reviewer, a native markdown parser. Whatever checks the chosen formatter performs are the checks that fire — the skill adds no rules of its own beyond the bundled fallback configs (step 4).

The skill respects whatever formatter / linter config the repo declares; an undeclared concern gets the bundled fallback where the skill ships one, tool defaults otherwise.

## Supported file types

- **Markdown** (`.md`, `.markdown`) via `md-audit.py` / `md-format.py` / `md-fix.py` — driven by the chosen formatter.
- **YAML frontmatter and fenced YAML blocks inside markdown** via `md-audit-frontmatter.py` — driven by yamllint.

No other file types are handled.

## Triggers

- "Audit docs" / "check docs" / "review markdown"
- "Format docs" / "format markdown" / "fix markdown" / "reformat docs"
- "Audit frontmatter" / "lint frontmatter" / "check yaml in docs"
- "What tools do I need to install?" / "recommend doc tools"
- Before tagging a release (run audit; resolve findings)
- `/docs-steward`

Do **not** trigger when: the user wants new prose written (authoring, not maintenance); the repo's conventions should be discovered or summarized (a convention-scanning concern); a skill directory needs validation against the Agent Skills specification (spec conformance); or commit messages / PR descriptions / branch names are wanted (a git authoring concern).

## Runtime requirements

`scripts/` requires Python 3.10+ (stdlib only, cross-platform — macOS, Linux, Windows). The orchestrated formatters install separately; the skill surfaces install hints via `recommend-tools.py` and never auto-installs.

## Reference ownership

Each fact lives in one file and this router links and summarizes instead of restating — with two deliberate, contract-tested exceptions stated in both places: the formatter fallback chain and the skip-directory list, which the doc-vs-code suite pins to the code wherever they appear. [`references/formatter-tools.md`](references/formatter-tools.md) owns tool facts: baseline detection and selection order (fed by `selector.py`), per-tool commands, output parsing, install hints. [`references/usage.md`](references/usage.md) owns CLI I/O: the invocation cheatsheet, flags, discovery, the stdout and exit-code contract. [`references/ndjson-schema.md`](references/ndjson-schema.md) owns event semantics. [`references/report-format.md`](references/report-format.md) owns the agent-rendered report shape. [`assets/configs/README.md`](assets/configs/README.md) owns bundled-config policy. [`references/architecture.md`](references/architecture.md) owns the `scripts/` layout and extension recipes.

## Workflow

### 1. Locate repo root

`git rev-parse --show-toplevel`; outside a git repo, fall back to the current working directory — discovery then walks the filesystem instead of asking git, so `.gitignore` is not respected (only the built-in skip list applies); a limitation worth noting in the report.

### 2. Inventory markdown files

`discovery.list_markdown_files` builds one shared inventory of every `.md` / `.markdown` file under the repo root (tracked + untracked-but-not-ignored; skips `node_modules`, `.git`, `dist`, `build`, `.venv`, `venv`, `target`). Every pass of a run receives this same explicit file list — tools never run on their own default globs — and explicit positional files replace it for all passes. An empty inventory short-circuits with a single `clean` event and exit 0. Discovery mechanics: [`references/usage.md`](references/usage.md).

### 3. Determine the style baseline

`baseline.detect_baselines` checks the repo root for the presence (no parsing) of every candidate config — markdownlint family first, then prettier, remark, mdformat, dprint, `.editorconfig` — and `selector.build_audit_plan` partitions the matches per tool family: the first formatter-family config governs the formatter pass, the first markdownlint-family config governs the complementary lint pass, and a concern with no declared config resolves to the `universal-subset` sentinel — the bundled fallback when the selected tool ships one, tool defaults otherwise. A config from one family never suppresses the check owned by another; multiple configs competing for the same concern resolve by declaration order. `.editorconfig` belongs to no tool family and never claims a concern. Candidate filenames, precedence detail, and cli2-only config routing: [`references/formatter-tools.md`](references/formatter-tools.md).

### 4. Run the audit

The skill wraps six markdown formatters plus yamllint, parses their output, and emits a uniform NDJSON envelope ([`references/ndjson-schema.md`](references/ndjson-schema.md)). Five operations:

- **`md-audit.py`** — the primary pipeline. Builds the composite plan from step 3 and runs every applicable pass over the shared inventory: the formatter owner in check mode, the complementary markdownlint lint pass, and — when `yamllint` is on PATH — the frontmatter pass. Each pass emits its own `selected` event; the exit code is the maximum across passes. With no formatter config, owner fallback favors prettier: `prettier` → `markdownlint-cli2` → `markdownlint` → `mdformat` → `dprint` → `remark`. When no formatter at all is usable, the run stops at a `missing` event with exit 3 — never auto-install.
- **`md-format.py`** — the chosen formatter's write mode; `--dry-run` previews via the check invocation and `would-change` events.
- **`md-fix.py`** — one-shot audit → format → re-audit, emitting a `delta` event with `{resolved, still_open, new}` counts, then the complementary passes so findings no formatter auto-fixes still surface (and drive the exit code).
- **`md-audit-frontmatter.py`** — the standalone frontmatter pass: extracts YAML frontmatter + fenced YAML blocks and pipes each to yamllint under the repo's config when one is declared, the bundled fallback otherwise. Inside the composite audit this pass soft-skips when yamllint is absent; invoked by name, a missing yamllint is a hard `missing` / exit 3.
- **`probe.py` / `recommend-tools.py`** — tool inventory and prioritized install recommendations (the install priority deliberately differs from the selection fallback; the user runs any install command themselves).

Flags (`--unwrap`, `--baseline`, `--quiet`, positional files) live in [`references/usage.md`](references/usage.md); per-tool commands, parsers, and install hints in [`references/formatter-tools.md`](references/formatter-tools.md).

**Bundled fallback configs.** When a concern resolves to `universal-subset`, the runner injects the shipped config for that pass's tool (markdownlint, prettier, yamllint) and emits a `bundled-config` event; the repo's own config always wins when present, and `--baseline FILE` forces the formatter owner only — complementary passes stay derived from what the repo declares. Policy, settings rationale, and override paths: [`assets/configs/README.md`](assets/configs/README.md).

**Out of scope:** anything the chosen formatter (or yamllint on frontmatter) does not check — prose style, sentence length, emoji policy, capitalization, and the like. Under the bundled defaults that includes line width (`MD013` disabled; `proseWrap: "never"`); a repo config that enforces a width is honored like any other repo rule. The skill adds no rules of its own — full stop.

### 5. Report (agent-rendered)

The skill emits raw NDJSON on stdout; the invoking agent aggregates the events and renders the user-facing report — template shape, per-finding rendering rule, and the `clean` / `missing` / `error` forms are in [`references/report-format.md`](references/report-format.md).

### 6. Offer fixes (agent-led)

After rendering, the agent pauses for the user; the skill has already exited. On approval the agent runs `md-format.py` (adding `--unwrap` / `--baseline FILE` as needed) — auto-fixable means whatever the chosen formatter's `--fix` / `--write` mode applies, and those formatter rewrites are the only edits: the agent never hand-authors fixes, and prose meaning, version numbers, and license text are never touched by hand. A formatter itself may reformat fenced-code layout (the bundled prettier config keeps `embeddedLanguageFormatting: "auto"`); a repo that wants code fences left alone declares `"off"` in its own config. The engine is visible in the `selected` event's `cmd` field and surfaces in the report header. After applying fixes, re-run `md-audit.py` and report the delta: `Resolved: N. Still open: M. New: K.`

## Exit codes

Uniform across the entry shims: `0` clean · `1` findings or files changed · `2` invocation error · `3` no usable tool — except `recommend-tools.py`, which exits `0` (top-priority tool present) or `1` (at least one priority tool missing) only.

## Anti-patterns

- Don't run on every prompt — only when triggered. The audit shells out to formatters and is non-trivially slow on large repos.
- Don't invent fixes — only the chosen formatter's `--fix` / `--write` mode applies edits; the agent does not synthesize its own.
- Don't enforce style the repo has not declared, beyond the bundled fallback configs. The skill mirrors local conventions; it does not import opinions.
- Don't impose a line width — the bundled defaults enforce no column limit (a repo's own config may). The default formatter (prettier under the bundled config) removes existing hard wraps on format; it never introduces them.
- Don't auto-install any orchestrated tool — detect via `probe.py`, surface hints via `recommend-tools.py`, and let the user run the install.

## Boundary with related concerns

Adjacent concerns the skill does not own — defer to a dedicated tool when the environment provides one; otherwise note the gap in the report: convention discovery (what a repo declares about commits / PRs / code style), spec conformance of a skill directory, commit / PR / branch authoring, and enforcing project-local rules on anything outside the documentation surface.
