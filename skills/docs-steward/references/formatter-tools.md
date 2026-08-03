# Formatter tools — concrete commands

Load on demand from `SKILL.md` step 4 (audit) and step 6 (fix). Five tools, two modes each (audit / format), one universal probe step, install hints when missing.

## Detection probe

Run once per audit; cache the result for the session. The listing follows `selector.FALLBACK_ORDER` (prettier first). `selector.build_audit_plan` derives the run from every detected config (step 3 of `SKILL.md`): the first formatter-family config's preferred tool becomes the write-capable owner, and a markdownlint binary — when the owner isn't one — runs the read-only complementary lint pass with the repo's own markdownlint config (bundled fallback otherwise). When a declared family's tools are absent, owner selection walks `FALLBACK_ORDER` and picks the first formatter on PATH (see "Baseline-matched tool missing" below); only when no formatter at all is available does the skill emit `MISSING` and exit 3 — there is no implicit hand-rolled-edits path.

```sh
command -v prettier          >/dev/null 2>&1 && echo prettier
command -v markdownlint-cli2 >/dev/null 2>&1 && echo markdownlint-cli2
command -v markdownlint      >/dev/null 2>&1 && echo markdownlint
command -v mdformat          >/dev/null 2>&1 && echo mdformat
command -v dprint            >/dev/null 2>&1 && echo dprint
command -v remark            >/dev/null 2>&1 && echo remark
```

When the **baseline** matches a config family (e.g. `.markdownlint.json`) but none of that family's preferred tools is on PATH, `selector.select_tool` falls back to the next available tool in `FALLBACK_ORDER` (`prettier` → `markdownlint-cli2` → `markdownlint` → `mdformat` → `dprint` → `remark`) and runs the first one it finds. The `selected` NDJSON event records the engine that actually ran so consumers can see when the chosen formatter diverges from the baseline-declared family. Only when none of the fallback tools is on PATH does the skill emit `MISSING` and exit 3. There is no implicit hand-rolled-edits path; tool selection always resolves to either a formatter on PATH or `MISSING`.

## Per-tool commands

For each tool, columns are: **Probe** (one-shot detect + version), **Audit** (read-only, parseable output, non-zero exit on findings), **Format** (write-mode, idempotent), **Notes**.

### markdownlint-cli2 / markdownlint

Pairs with `.markdownlint.json` / `.markdownlint.jsonc` / `.markdownlint.yaml` / `.markdownlint-cli2.{jsonc,yaml}`.

| Mode | Command |
| --- | --- |
| Probe | `markdownlint-cli2 --version` (or `markdownlint --version`) |
| Audit | `markdownlint-cli2 "**/*.md" "**/*.markdown" "#node_modules" "#.git" "#dist" "#build" "#.venv" "#venv" "#target"` |
| Audit (older CLI) | `markdownlint --ignore-path .gitignore "**/*.md" "**/*.markdown"` |
| Format | `markdownlint-cli2 --fix "**/*.md" "**/*.markdown" "#node_modules" "#.git" "#dist" "#build" "#.venv" "#venv" "#target"` |
| Format (older CLI) | `markdownlint --fix --ignore-path .gitignore "**/*.md" "**/*.markdown"` |

- **Exit 0** = no findings; **exit 1** = findings present; **exit 2** = config / invocation error.
- **Output line shape**: `path/to/file.md:LINE:COL MD### name "fragment"`. The skill emits each non-empty stdout/stderr line verbatim as a `finding` event detail string — no parsing, no field extraction. The line:col prefix IS stripped internally by `runner._normalize_finding_key` when computing the `md-fix` DELTA so an unfixed finding at a shifted line still counts as `still_open` rather than `resolved + new`, but consumers reading the NDJSON `finding.detail` see the raw line. To skip the line:col prefix for display, parse `^([^:]+):(\d+)(?::(\d+))? (MD\d{3})(?:/(\S+))? (.*)$` on the consumer side.
- **Install hints**: `npm install -g markdownlint-cli2` (canonical — substitute `markdownlint-cli` for the older CLI); `pnpm add -g markdownlint-cli2` / `bun add -g markdownlint-cli2` / `yarn global add markdownlint-cli2` (alternative JS package managers); `mise use -g npm:markdownlint-cli2` (mise via npm backend). No standalone binary; requires a Node runtime.

### prettier

Pairs with `.prettierrc` / `.prettierrc.{json,yaml,yml,js,cjs,mjs,toml}` / `prettier.config.{js,cjs,mjs}`. Prettier itself also reads a `prettier` key out of `package.json`, but `docs_steward.baseline.BASELINE_CANDIDATES` does NOT include `package.json` — selection happens by filename match, so a repo whose only Prettier config lives under `package.json#prettier` falls through to `universal-subset` and the bundled fallback. Add a standalone `.prettierrc` (or any of the other names above) when you want the skill to detect Prettier.

| Mode | Command |
| --- | --- |
| Probe | `prettier --version` |
| Audit | `prettier --check --parser markdown "**/*.md" "**/*.markdown"` |
| Audit (unwrap-respecting) | `prettier --check --parser markdown --prose-wrap=never "**/*.md" "**/*.markdown"` |
| Format | `prettier --write --parser markdown "**/*.md" "**/*.markdown"` |
| Format (unwrap) | `prettier --write --parser markdown --prose-wrap=never "**/*.md" "**/*.markdown"` |

- **Exit 0** = formatted; **exit 1** = unformatted files exist (audit) or write error (format); **exit 2** = config / invocation error.
- **Output**: structured but per-mode. In **audit mode** (`--check`) Prettier emits a `Checking formatting...` banner, then one `[warn] <path>` line per unformatted file, then a `Code style issues found in N files. Run Prettier with --write to fix.` summary; in **format mode** (`--write`) it emits `<file> Nms` per write. The skill does not synthesize messages, so each non-empty stdout/stderr line lands verbatim as a `finding` event detail string (audit) or a `changed` event detail string (format) — the `[warn]` prefix on each audit line and the summary line both reach the consumer. NDJSON has no INFO/severity concept; consumers that want bare file paths must strip the `[warn] ` prefix locally (or filter the trailing summary line on text). `--quiet` drops the banner + summary via the preamble filter; the `[warn] <path>` lines are preserved as findings.
- `--prose-wrap=never` is appended automatically when the unwrap gating in `SKILL.md` step 4 permits.
- Honors `.prettierignore`; the glob is otherwise unfiltered.
- **Install hints**: `npm install -g prettier` (canonical); `pnpm add -g prettier` / `bun add -g prettier` / `yarn global add prettier` (alternative JS package managers); `volta install prettier` (toolchain manager); `mise use -g npm:prettier` (mise via npm backend); `npx prettier@latest` (one-shot, no install). Requires a Node runtime.

### mdformat

Pairs with `.mdformat.toml` at the repo root. mdformat itself also reads a `[tool.mdformat]` section out of `pyproject.toml`, but `docs_steward.baseline.BASELINE_CANDIDATES` only matches by filename — `pyproject.toml` is not in the candidate list (and adding it would require parsing the TOML to confirm the `[tool.mdformat]` table exists, which the rest of baseline detection deliberately avoids). A repo whose only mdformat config lives under `pyproject.toml#[tool.mdformat]` therefore falls through to `universal-subset` and may select a different formatter. Add a standalone `.mdformat.toml` when you want the skill to detect mdformat.

| Mode | Command |
| --- | --- |
| Probe | `mdformat --version` |
| Audit | `mdformat --check .` (recursive on the working dir) |
| Audit (single file) | `mdformat --check path/to/file.md` |
| Format | `mdformat .` |
| Format (unwrap) | `mdformat --wrap=no .` |
| Format (preserve width) | `mdformat --wrap=N .` |

- **Exit 0** = formatted (audit) or success (format); **non-zero** = changes needed (audit) or error (format).
- **Output**: file paths only. Each non-empty stdout/stderr line is emitted verbatim as a `finding` event detail string (audit) or `changed` (format); no per-file message synthesis.
- `--wrap=no` is appended automatically when the unwrap gating in `SKILL.md` step 4 permits.
- Plugins (`mdformat-gfm`, `mdformat-tables`, `mdformat-frontmatter`, `mdformat-footnote`, `mdformat-toc`) extend syntax coverage but are not auto-installed. `probe.py` emits a `plugin-available` event per installed plugin during inventory. The CLI also emits a `plugin-missing` event when mdformat is the selected tool, a target file contains GFM syntax (tables / task lists / strikethrough / bare autolinks), and `mdformat-gfm` is NOT installed — that one absent-plugin case has a dedicated content sniffer in `plugins.needs_gfm`. Other plugins are surfaced only via `plugin-available` during probe; the skill does not auto-detect when a file would benefit from `mdformat-tables` / `mdformat-frontmatter` / `mdformat-footnote` / `mdformat-toc` and does not emit `plugin-missing` for them.
- **Install hints**: `pipx install mdformat` (preferred — isolated); `uv tool install mdformat` (fast); `pip install --user mdformat` (user-site); `brew install mdformat` (macOS); `mise use -g pipx:mdformat` (mise via pipx backend); add `mdformat-gfm` for GitHub-flavored markdown. Pure-Python; no Node required.

### dprint

Pairs with `dprint.json` containing a `markdown` plugin entry.

| Mode   | Command            |
| ------ | ------------------ |
| Probe  | `dprint --version` |
| Audit  | `dprint check`     |
| Format | `dprint fmt`       |

- **Exit 0** = formatted; **non-zero** = changes needed (audit) or error (format).
- **Output**: file paths only. Each non-empty stdout/stderr line is emitted verbatim as a `finding` event detail string (audit) or `changed` (format); no per-file message synthesis.
- Honors `dprint.json`'s `includes` / `excludes`; no glob argument needed.
- **Install hints**: `curl -fsSL https://dprint.dev/install.sh | sh` (POSIX official installer); `iwr https://dprint.dev/install.ps1 -useb | iex` (Windows PowerShell); `brew install dprint` (macOS); `winget install dprint` / `scoop install dprint` (Windows package managers); `cargo install dprint` (via Rust toolchain); `mise use -g aqua:dprint/dprint` (mise via aqua backend). Single static binary regardless of installer.

### remark-cli

Pairs with `.remarkrc` / `.remarkrc.{json,yaml,yml,js,cjs,mjs}`. Less common today than `prettier` for general markdown but still seen in remark-based pipelines.

| Mode   | Command                                            |
| ------ | -------------------------------------------------- |
| Probe  | `remark --version`                                 |
| Audit  | `remark --quiet --frail "**/*.md" "**/*.markdown"` |
| Format | `remark --output "**/*.md" "**/*.markdown"`        |

- `--frail` forces non-zero exit on any warning; the skill relies on this to flip exit semantics into a usable signal.
- `--output` rewrites in place; without it `remark` prints to stdout.
- Output is one VFile message per finding: `path:line:col-line:col  warning  <message>  <rule>  <source>` — parse with `^([^:]+):(\d+):(\d+)-\d+:\d+\s+(warning|error)\s+(.*?)\s+(\S+)\s+(\S+)$`.
- **Install hints**: `npm install -g remark-cli remark-preset-lint-recommended` (canonical — preset is required, otherwise `remark` runs no checks); `pnpm add -g remark-cli remark-preset-lint-recommended` / `bun add -g remark-cli remark-preset-lint-recommended` (alternative JS package managers); `mise use -g npm:remark-cli` (mise via npm backend — install the preset separately).

### yamllint

Complementary tool — not a markdown formatter. Used by `md-audit-frontmatter` to lint YAML frontmatter + fenced YAML blocks extracted from markdown files. Pairs with `.yamllint` / `.yamllint.yaml` (any of the canonical yamllint config names); the skill's bundled `../assets/configs/yamllint.yaml` is used when the repo declares none and no `--yamllint-config` override is passed.

| Mode                             | Command                                 |
| -------------------------------- | --------------------------------------- |
| Probe                            | `yamllint --version`                    |
| Audit (per block, fed via stdin) | `yamllint -f parsable -s -c <config> -` |

- **Exit 0** = no findings; **exit 1** = findings present; **exit 2** = config / invocation error.
- **Output line shape**: `stdin:LINE:COL: [LEVEL] message (rule)`. The skill replaces `stdin:LINE:COL` with `<file>:<anchor>` per the no-line-numbers convention; `<anchor>` is `frontmatter` for top-of-file blocks or `yaml fence: <excerpt>` for fenced YAML blocks.
- yamllint reads from stdin (`-`) — no glob argument; the skill pipes each extracted block separately so each finding lands against the correct file + anchor.
- **Install hints**: `pipx install yamllint` (preferred — isolated); `uv tool install yamllint` (fast); `pip install --user yamllint` (user-site); `brew install yamllint` (macOS); `sudo apt install yamllint` / `sudo dnf install yamllint` (Linux distro packages); `mise use -g pipx:yamllint` (mise via pipx backend). Pure-Python; no Node required.

## No-tool behavior

When no formatter at all is on `PATH` (every tool in `FALLBACK_ORDER` is absent), `selector.select_tool` returns `None` and `runner.run_tool` emits a single `MISSING` event with the install hint and exits 3. The skill does not synthesize a hand-rolled fix path — addressing the missing toolchain is the caller's responsibility (typically by running `recommend-tools.py` to surface install commands).

## Exit-code handling pattern

The skill must distinguish the three classes for every tool:

| Class | Action |
| --- | --- |
| **Clean** (exit 0 in audit) | No findings; skip the file in the report. |
| **Findings** (exit 1 in audit) | Stream each non-empty stdout line verbatim as a `finding` event (and stderr too in AUDIT mode — some tools emit findings there). No rule-code synthesis: consumers that want a `<RULE>` slot should parse the tool's own format from `finding.detail` (e.g. `MD\d{3}` for markdownlint, the rule field in remark's parsable output). The skill stays out of the synthesis business so it doesn't paper over consumer-side variation. |
| **Tool error** (exit ≥ 2, or unexpected stderr) | Append the tool's stdout/stderr as event-stream lines, then emit a single `ERROR` event with `{"exit": N}` and exit 2. There is no implicit hand-rolled-edits fallback after a tool error — addressing the failing tool is on the caller. |

## Caveats

- **Tool drift** — formatter releases change default rules occasionally (e.g. `prettier` flipped `proseWrap` default in 1.9, `markdownlint` added new rules each minor). The skill does not pin versions; trust whatever is on `PATH`. Surface the version in the report header so the user can correlate.
- **Plugin coverage** — `mdformat` requires plugins for GFM tables, footnotes, frontmatter; `remark` requires `remark-preset-*`; `prettier` and `dprint` cover CommonMark + GFM out of the box. Unknown syntax is whatever the chosen tool passes through silently — the orchestrator does not synthesize warnings about unrecognized constructs. The exception is the GFM check: when mdformat is selected, the CLI dispatcher pre-scans target files via `plugins.needs_gfm` and emits a `plugin-missing` event when `mdformat-gfm` is absent.
- **Glob differences** — POSIX `find` and the Node `glob` library expand `**/*.md` differently on Windows shells. When invoking on Windows, prefer `git ls-files '*.md' | xargs <tool>` over a raw glob to avoid the cross-shell expansion gap.
- **Multiple tools, single repo** — when both `.prettierrc` and `.markdownlint.json` exist, the style-baseline precedence in step 3 picks one. Do not run both — that produces conflicting rewrites. The orchestrator does not emit any event for the non-baseline config; reconciling competing configs is a manual step the user should take after reading the `selected` event's `baseline` field.
- **Auto-install is forbidden** — per anti-pattern in `SKILL.md`. Always report missing tools with the install hint; never invoke `npm install` / `pip install` / `cargo install` from the skill.
