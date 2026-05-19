---
name: docs-steward
description: >
  Audits and reformats markdown documentation by orchestrating external
  formatters (markdownlint-cli2 / markdownlint / prettier / mdformat /
  dprint / remark) and a YAML linter (yamllint) for frontmatter + fenced
  YAML blocks. Emits NDJSON findings on stdout; an invoking agent renders
  the report and offers fixes. Operates without hardcoded paths — discovers
  every `.md` / `.markdown` file (skipping `node_modules`, `.git`, `dist`,
  `build`, `.venv`, vendored trees). Read-only by default; on approval,
  runs the chosen formatter's --fix / --write mode. Ships bundled fallback
  configs (markdownlint.json, prettierrc.json, yamllint.yaml) used only
  when the repo declares none. Triggers when the user says "steward the
  docs", "audit docs", "check docs", "review markdown", "audit
  frontmatter", "lint frontmatter", or invokes `/docs-steward`. Does not
  write new prose, does not enforce style rules beyond what the chosen
  formatter applies, does not auto-install any tool.
allowed-tools: Bash Read Grep Edit Write
metadata:
  version: "1.0.0"
---

# docs-steward

## Purpose

Run external markdown formatters and yamllint on existing repo docs; emit findings as NDJSON on stdout; apply the chosen formatter's `--fix` / `--write` mode on explicit approval.

## Is / is-not

- **Is:** an orchestrator that runs markdown formatters + yamllint on existing repo docs and emits findings.
- **Is not:** a doc generator, a code editor, a code reviewer, a native markdown parser. Whatever checks the chosen formatter performs are the checks that fire — the skill adds no rules of its own beyond bundled config tweaks (4.D).

The skill respects whatever formatter / linter config the repo declares (`.markdownlint.*`, `.prettierrc*`, `.remarkrc*`, `.editorconfig`, `dprint.json`); when the repo is silent, it falls back to the skill's bundled configs (4.D).

## Supported file types

- **Markdown** (`.md`, `.markdown`) via `md-audit.py` / `md-format.py` / `md-fix.py` — driven by the chosen formatter.
- **YAML frontmatter and fenced YAML blocks inside markdown** via `md-audit-frontmatter.py` — driven by yamllint.

No other file types are handled.

## Triggers

- "Audit docs" / "check docs" / "review markdown"
- "Format docs" / "format markdown" / "rewrite docs"
- "Audit frontmatter" / "lint frontmatter" / "check yaml in docs"
- "What tools do I need to install?" / "recommend doc tools"
- Before tagging a release (run audit; resolve findings)
- `/docs-steward`

Do **not** trigger when:

- The user wants new prose written → that is authoring, not maintenance.
- The user wants the repo's conventions discovered or summarized → that is a convention-scanning concern.
- The user wants a single skill validated against the Agent Skills specification → spec-conformance is a separate concern.
- The user wants commit messages, PR descriptions, or branch names produced → that is a git/PR authoring concern.

## Runtime requirements

The scripts under `scripts/` require Python 3.10+ (stdlib only — no `pip install` for the skill itself; the markdown formatters it orchestrates have their own installers, surfaced via `recommend-tools.py`). Cross-platform — runs on macOS, Linux, and Windows wherever Python 3.10+ does. No third-party dependencies.

## Workflow

### 1. Locate repo root

```sh
git rev-parse --show-toplevel
```

If not in a git repo → fall back to the current working directory and note the limitation in the report (cannot infer renames, cannot use `git log`).

### 2. Inventory all markdown files

`discovery.list_markdown_files` returns absolute paths to every `.md` / `.markdown` file under the repo root, via `git ls-files --cached --others --exclude-standard` (covers both tracked and untracked-but-not-ignored files; respects `.gitignore`) or, when git is unavailable, an `os.walk` fallback. Either path filters out entries under `node_modules`, `.git`, `dist`, `build`, `.venv`, `venv`, `target` and drops paths whose working-tree file is missing or is a directory.

The inventory is consumed by the audit-frontmatter (`md-audit-frontmatter`) and the mdformat-plugin pre-check (`md-audit` / `md-format` / `md-fix` when mdformat is the selected tool). The markdown formatter pipeline itself does NOT iterate this list — it invokes the chosen formatter with the tool's own default glob (e.g. `prettier --check '**/*.md' '**/*.markdown'`, `markdownlint-cli2 '**/*.md' '**/*.markdown' '#node_modules' ...`, `mdformat --check .`). The skip-dir contract is enforced for the formatter pipeline by the per-tool default-glob negative patterns (markdownlint-cli2 / markdownlint), by `--ignore-path .gitignore` (markdownlint), or by the tool's own discovery (mdformat / dprint / remark via cwd=root); see `references/formatter-tools.md` for the exact commands.

### 3. Determine the style baseline

`baseline.detect_baseline` checks the repo root for the **presence** of a config file (no parsing, no field extraction — purely `os.path.isfile`). The first match wins; the relative path is recorded in the `selected` NDJSON event's `baseline` field, then — when the baseline belongs to the chosen tool's family (e.g. `.prettierrc` → prettier, `.markdownlint.json` → markdownlint) — it is resolved against the repo root and forwarded to the formatter via its `--config <path>` flag. The `selected` event's `cmd` field therefore shows the absolute resolved path while `baseline` keeps the user-visible relative name. Tools whose `CommandTemplate.config_flag` is `None` (mdformat / dprint / remark) discover their config from `cwd=root` directly; for those families the `--config` flag is omitted from `cmd`.

Candidates probed in order:

1. markdownlint family:
   - **Rule configs** (consumed by both `markdownlint` and `markdownlint-cli2`): `.markdownlint.json`, `.markdownlint.jsonc`, `.markdownlint.yaml`, `.markdownlint.yml`
   - **CLI2-only configs** (`.markdownlint-cli2.{jsonc,yaml}`): cli2-specific format the legacy `markdownlint` CLI cannot parse. The selector routes these baselines to `markdownlint-cli2` exclusively; when cli2 isn't on PATH the chosen formatter falls back via `FALLBACK_ORDER` and the cli2 config is **not** forwarded as `--config` (the legacy CLI runs against its own discovery instead).
2. prettier family: `.prettierrc`, `.prettierrc.{json,yaml,yml,js,cjs,mjs,toml}`, `prettier.config.{js,cjs,mjs}`
3. remark family: `.remarkrc`, `.remarkrc.{json,yaml,yml,js,cjs,mjs}`
4. mdformat: `.mdformat.toml`
5. `dprint.json`
6. `.editorconfig`
7. Nothing found → `universal-subset` sentinel; bundled fallback configs apply (4.D).

`dprint.json` ranks above `.editorconfig` so a repo declaring both is matched against the formatter-specific config (which routes to `Tool.DPRINT` in `selector._BASELINE_PREFERENCES`) rather than the cross-tool style hint, which has no preferred-tool entry and would otherwise trigger a `FALLBACK_ORDER` walk that picks whichever formatter happens to be on PATH first.

When two configs in the precedence are both present (e.g. `.markdownlint.json` and `.prettierrc`), the first-found wins; the second is not detected or read.

### 4. Run the audit

The skill is an **orchestrator**: it wraps external markdown formatters (markdownlint-cli2 / markdownlint / prettier / mdformat / dprint / remark) and a YAML linter (yamllint), parses their output, and emits findings in a uniform NDJSON envelope. The catalog of detected rules is whatever the chosen tool enforces; the skill adds no rules of its own beyond bundled config tweaks (4.D).

#### A. Markdown audit (`md-audit.py`)

The primary pipeline. Selects a formatter via the style-baseline precedence from step 3, runs it in check mode, and emits one `finding` event per output line. NDJSON on stdout, progress + errors on stderr, exit codes `0` clean / `1` findings (or files changed) / `2` invocation error / `3` no usable tool.

**Per-file targeting.** Positional file arguments scope the run to specific paths, bypassing the formatter's default glob. Useful for pre-commit hooks, CI changed-files-only runs, and agent invocations that target a single file. Works without git — the file list is passed verbatim. Example: `md-audit.py docs/intro.md README.md`.

**`--quiet`.** Suppresses formatter preamble lines (banners like `Linting: 3 file(s)` / `Summary: 0 error(s)`) — leaves only real `finding` / `changed` / `error` events on stdout. Useful for agent consumers that don't want to filter noise.

See [`references/usage.md`](references/usage.md) for the full invocation cheatsheet (all entry shims + the Python-module form + test commands), [`references/architecture.md`](references/architecture.md) for the `scripts/` layout + port-adapter rationale + extension recipes, and [`references/ndjson-schema.md`](references/ndjson-schema.md) for the per-event detail-field schema.

Per-tool command tables, output parsers, and install hints live in [`references/formatter-tools.md`](references/formatter-tools.md). The contract enforced across `scripts/{probe,recommend-tools,md-audit,md-format,md-audit-frontmatter}.py`:

1. **Probe order** (derived from the style-baseline precedence in step 3): `markdownlint-cli2` / `markdownlint` → `prettier` → `mdformat` → `dprint` → `remark`. First match whose corresponding config was selected as the baseline wins. `yamllint` is probed independently for the `md-audit-frontmatter` pipeline — it never participates in markdown formatter selection.
2. **Audit mode** runs the chosen tool's `--check` / `--frail` / equivalent invocation, captures stdout, parses findings into the skill's report stream — reusing the tool's rule code (`MD###` for markdownlint, rule name in parens for yamllint).
3. **Format mode** is reached only via step 6 (Offer fixes) after explicit user approval. When the bundled config (or repo config) silences line-length, the `--prose-wrap=never` / `--wrap=no` flag is appended automatically.
4. **Baseline-matched tool missing** — when the baseline matches a config family (e.g. `.markdownlint.json`) but none of that family's preferred tools (`markdownlint-cli2` / `markdownlint`) is on PATH, `selector.select_tool` walks `FALLBACK_ORDER` (`markdownlint-cli2` → `markdownlint` → `prettier` → `mdformat` → `dprint` → `remark`) and runs the first tool it finds. The chosen engine is recorded verbatim in the `selected` event so consumers can see when the actual formatter diverges from the baseline-declared family. Only when **none** of the fallback tools is on PATH does the skill emit a `MISSING` event with the install hint and exit 3; **never** auto-install.
5. **Tool error** (non-zero exit ≥ 2) → the tool's output is emitted as `finding` / `changed` events, then an `ERROR` event with `{"exit": N}` is appended; exit 2.

This delegation matches CI when CI invokes the same formatter with the same config. The bundled-config fallback diverges from a no-config CI — local applies the bundled overrides; CI applies formatter defaults.

#### B. Format + one-shot fix (`md-format.py`, `md-fix.py`)

`md-format.py` runs the chosen formatter in write mode (`--fix` / `--write` / equivalent). Emits one `changed` event per touched file. Same `--unwrap` / `--baseline` / `--quiet` / positional files semantics as `md-audit.py`.

**`--dry-run`** (md-format only): shells out to the formatter's check invocation instead of write — emits `would-change` events showing what would be modified without actually writing. Exit code mirrors audit semantics (0 clean, 1 would-change). Lets the agent preview a format pass before approving the destructive run.

`md-fix.py` is the one-shot loopback: audit → format → re-audit → emit a `delta` event with `{resolved, still_open, new}` counts. When the pre-audit is already clean, format is skipped and the delta reports zeros. When the pre-audit hits an error (exit ≥ 2), the cycle bails early without running format. Useful for "fix what can be fixed automatically and tell me what's left" workflows. Same scoping / unwrap / quiet / baseline flags as the underlying audit + format.

**mdformat plugin awareness.** When mdformat is the selected tool, the CLI dispatcher emits one `plugin-missing` event per target file containing GFM syntax (tables, task lists, strikethrough, bare autolinks) if `mdformat-gfm` is not installed — catches the silent-pass-through failure mode where mdformat would skip unrecognized syntax without warning. Fires once per CLI invocation before the formatter runs. No-op when a different tool is selected or when `mdformat-gfm` is on the system. Separately, `probe.py` emits `plugin-available` events for every installed `mdformat-*` plugin it detects (`mdformat-gfm`, `mdformat-tables`, `mdformat-frontmatter`, `mdformat-footnote`, `mdformat-toc`).

#### C. YAML frontmatter audit (`md-audit-frontmatter.py`)

Walks every markdown file under the repo root via `git ls-files` (or `os.walk` fallback), extracts each `---...---` frontmatter block plus any `` ```yaml `` / `` ```yml `` / `` ~~~yaml `` fenced code blocks via the pure-Python `frontmatter.extract_blocks`, pipes each block to `yamllint -f parsable -s -` (with the bundled `yamllint.yaml` fallback config unless `--yamllint-config` overrides), and emits one `finding` event per yamllint message. Finding locator is `<file>:<anchor>` where anchor is `frontmatter` or `yaml fence: <first-line excerpt>` — no `file:line` per the no-line-numbers convention. Exit codes mirror the audit pipeline: `0` clean, `1` findings present, `2` yamllint invocation error, `3` yamllint not on PATH. Unreadable markdown files are reported per-file as `ERROR` events; the audit continues across other files.

#### D. Style baseline + bundled fallback configs

When the repo declares no formatter config (baseline resolves to `universal-subset`), `runner.py` calls `bundled_config_for` to pick up a shipped default for the chosen tool — currently markdownlint, prettier, and yamllint. The selection emits a `bundled-config` NDJSON event so the caller knows enforcement is coming from the skill, not the repo. The config path is passed via two separate argv elements (`--config <path>` / `-c <path>`) rather than the combined `--config=<path>` form, because markdownlint-cli2 silently rejects the combined form and treats it as a file glob.

The repo's own config always wins when present. `--baseline FILE` skips auto-detection — the supplied path is recorded in the `selected` event's `baseline` field verbatim and (when the baseline belongs to the chosen tool's family) forwarded as `--config`. The bundled fallback is keyed on the `universal-subset` sentinel only: when `--baseline FILE` resolves to any other value the bundled config is not applied; when `--baseline universal-subset` is passed explicitly (or auto-detection finds no config), `runner.py` still applies the shipped fallback. Passing an arbitrary file path therefore opts out of the bundled defaults, but passing `universal-subset` explicitly is the same code path as no config detected at all. The shipped defaults align with the no-hard-wrap + compact-tables preference:

- `assets/configs/markdownlint.json` — disables `MD013` (line-length), `MD033` (inline HTML), `MD041` (first-line H1), `MD060` (table column padding); allows duplicate headings under different parents.
- `assets/configs/prettierrc.json` — markdown overrides set `proseWrap: "never"`.
- `assets/configs/yamllint.yaml` — disables `line-length`, `document-start`, `new-line-at-end-of-file` (the latter two are extraction artifacts of frontmatter pipe-to-stdin); flags `truthy` non-canonical values and `key-duplicates`.

See [`assets/configs/README.md`](assets/configs/README.md) for the full rationale and the three tools (mdformat, dprint, remark) where bundled fallback is intentionally omitted (mdformat: no `--config <path>`; dprint: plugin-URL pinning rots; remark: requires preset install).

#### E. Install recommendations (`recommend-tools.py`)

When `probe.py` reports no usable formatter (exit 3), call `recommend-tools.py` for a prioritized install-recommendation list. The install priority is deliberately different from `selector.py`'s fallback order — `select` answers *"given multiple on PATH, which runs?"* (favors strict linters), while `recommend-tools` answers *"given nothing, what should be installed first?"* (favors `prettier` for the widest ecosystem fit + `--prose-wrap=never` support that matches the no-hard-wrap preference). Order: `prettier` → `mdformat` → `markdownlint-cli2` → `dprint` → `remark` → `yamllint`. The first five are markdown formatters; `yamllint` is the complementary YAML linter used by `md-audit-frontmatter`. The script emits `installed`, `recommend` (with `priority_rank` + `install_options` — a JSON array of platform / package-manager alternatives covering npm, pnpm, bun, yarn, mise, pipx, uv, brew, winget, apt, dnf, cargo, curl/iwr installers), and a single `verdict` event tied to the exit code. Exit `0` when the top-priority tool is already present, `1` when at least one priority tool is missing, `2` on invocation error. The skill never invokes the install commands — `install_hints()` returns them; the user picks the line for their platform.

#### F. Out of scope

The skill does not enforce: Oxford comma, sentence length, voice / tense, emoji policy, bullet density, paragraph length, capitalization of common nouns, locale-specific quotation marks, em-dash vs en-dash policy, line-width (per the bundled `MD013: false` and `proseWrap: never` configs). Anything not covered by the chosen formatter or by yamllint on frontmatter is out of scope — full stop.

### 5. Report (agent-rendered)

The skill emits raw NDJSON events on stdout. An invoking agent (e.g. Claude under `/docs-steward`) aggregates them and renders the user-facing report. The skill itself does not write a markdown report file — that's the agent's responsibility if the user wants one.

See [`references/report-format.md`](references/report-format.md) for the template shape, per-finding rendering rule (the agent does not synthesize severity tiers or rule codes the formatter didn't emit), header-field source map, and the alternate forms for `clean` / `MISSING` / `ERROR` event streams.

### 6. Offer fixes (agent-led)

After the agent renders the report, it pauses for the user. The skill itself does not pause; it has already exited.

- **Auto-fixable** (safe): whatever the chosen formatter's `--fix` / `--write` mode applies (markdownlint-cli2 `--fix`, prettier `--write`, mdformat in-place rewrite, dprint `fmt`, remark `--output`). When the bundled or repo style baseline silences line-length, the `--prose-wrap=never` / `--wrap=no` flag is appended automatically so the rewrite does not re-wrap prose. The agent invokes `scripts/md-format.py [--unwrap] [--baseline FILE]` on approval.
- **Never auto-fix**: anything affecting prose meaning, version numbers, license text, code examples inside docs.

**Fix engine** — the chosen engine is recorded in the `selected` NDJSON event's `cmd` field; the agent surfaces it as `Fix engine: <engine>` in the report header (5).

After applying fixes, the agent re-runs `md-audit.py` and reports a delta: `Resolved: N. Still open: M. New: K.`.

## Edge cases

- **No `git` in PATH** — `discovery.list_markdown_files` falls back to `os.walk` skipping the standard excluded directories. Repo-root detection (`repo.repo_root`) falls back to `os.getcwd()`.
- **No formatter on PATH** — `md-audit.py` / `md-format.py` emit a `MISSING` event with the install hint and exit 3. `md-audit-frontmatter.py` does the same for yamllint.
- **Formatter on `PATH` errors out** (config syntax error, missing plugin, returncode ≥ 2) — runner emits the output as `finding`/`changed` events plus an `ERROR` event with the exit code, then returns exit 2. Stderr is captured into the event stream.
- **Style-baseline conflict** (e.g. both `.markdownlint.json` and `.prettierrc` present) — first match per step 3's precedence wins; later configs are not detected.
- **Universal-subset baseline + tool with no bundled config** (mdformat / dprint / remark) — the tool runs with its own discovery defaults; the `selected` event's `config_source` is `tool-default` rather than `bundled`.
- **Non-UTF-8 markdown files** — `OsFileSystem.read_text` raises during `md-audit-frontmatter`; the failure is captured as an `ERROR` event per-file and the audit continues across other files. The markdown-formatter path delegates encoding handling to the formatter.
- **Windows shells** (Git Bash, WSL, PowerShell) — `SubprocessRunner` extends PATH with mise / asdf / pipx / brew / cargo / bun / pnpm / volta directories so tools installed via those managers resolve even when the harness shell hasn't activated them.

## Anti-patterns

- Don't run on every prompt — only when triggered. The audit shells out to a formatter and is non-trivially slow on large repos.
- Don't invent fixes. The skill only runs the chosen formatter's `--fix` / `--write`; the agent does not synthesize edits the formatter wouldn't apply.
- Don't enforce style rules the repo has not declared, beyond what the chosen formatter applies via the bundled fallback config (4.D). The skill mirrors local conventions; it does not import opinions.
- Don't impose a line width. The bundled markdownlint config disables `MD013` and the bundled prettier config sets `proseWrap: "never"` — hard-wrap is neither flagged nor introduced by the default flow.
- Don't auto-install any orchestrated tool — markdown formatters or `yamllint`. Detect what is on `PATH` via `probe.py`; surface install hints via `recommend-tools.py`; the user runs the install command themselves.

## Boundary with related concerns

The skill is intentionally narrow. Adjacent concerns are listed here as *capabilities the skill does not own* — not as references to other installed skills. If the surrounding environment provides a dedicated tool for any of these, defer to it; otherwise note the gap in the report.

- **Convention discovery** — answering "what does this repo declare about commits / PRs / code style?" is a separate concern. This skill consumes such conventions when it finds them but does not enumerate them on its own.
- **Spec conformance for a single skill** — checking a skill directory against the Agent Skills specification (file-reference resolution, frontmatter compliance, progressive disclosure) is a separate concern. This skill audits markdown files only (plus YAML inside markdown via `md-audit-frontmatter`); it does not perform spec-level validation.
- **Commit / PR / branch authoring** — producing those artifacts is a separate concern. This skill keeps the docs that *describe* those rules honest, but does not generate the artifacts.
- **Project-local commit / style rules** — when the repo declares them in a discoverable file, this skill reads them to interpret findings, but never enforces them on commits, source code, or files outside the documentation surface.
