# Formatter tools — detection, selection, and concrete commands

Load on demand from `SKILL.md` steps 3–4 (baseline + audit) and step 6 (fix). This file owns the tool facts: baseline detection and selection order (fed by `selector.py`), per-tool commands, output parsing, and install hints.

## Baseline detection and selection

`baseline.detect_baselines` probes the repo root for the **presence** of every candidate config (a pure file-exists check — no parsing, no field extraction) and returns all matches, in declaration order:

1. markdownlint family — **rule configs** consumed by both binaries (`.markdownlint.json`, `.markdownlint.jsonc`, `.markdownlint.yaml`, `.markdownlint.yml`) and **cli2-only configs** (`.markdownlint-cli2.jsonc`, `.markdownlint-cli2.yaml`) in a format the legacy `markdownlint` CLI cannot parse. The plan routes cli2-only configs to `markdownlint-cli2` exclusively; when cli2 is not on PATH the lint pass runs the legacy binary under the **bundled** rules instead — a cli2 config is never forwarded to a binary that cannot parse it, and the pass never silently degrades to tool defaults (repo-config-or-bundled, always).
2. prettier family — `.prettierrc`, `.prettierrc.{json,yaml,yml,js,cjs,mjs,toml}`, `prettier.config.{js,cjs,mjs}`.
3. remark family — `.remarkrc`, `.remarkrc.{json,yaml,yml,js,cjs,mjs}`.
4. mdformat — `.mdformat.toml`.
5. `dprint.json`.
6. `.editorconfig`.

`selector.build_audit_plan` partitions the matches **per tool family**: the first formatter-family config governs the formatter pass, the first markdownlint-family config governs the complementary lint pass, and a concern with no declared config resolves to the `universal-subset` sentinel — the bundled fallback when the selected tool ships one (markdownlint / prettier / yamllint), tool defaults otherwise. Configs from different families are complementary, never competing — a repo declaring both `.markdownlint.json` and `.prettierrc` gets both passes, each honoring its own file. Multiple configs competing for the **same concern** (e.g. `.prettierrc` and `dprint.json`, both formatter-family) resolve by declaration order: the earlier candidate owns the concern and the later one is not read.

`dprint.json` ranks above `.editorconfig` so a repo declaring both is matched against the formatter-specific config the user explicitly wrote. `.editorconfig` belongs to no tool family, so its presence never claims a concern — a repo declaring only `.editorconfig` resolves both concerns to `universal-subset` and gets the bundled defaults, exactly like a repo that declares nothing.

Each pass's governing config is recorded in that pass's `selected` event `baseline` field; when it belongs to the pass's tool family it is resolved against the repo root and forwarded via the tool's config flag, so the `selected` event's `cmd` shows the absolute resolved path while `baseline` keeps the user-visible relative name. Tools whose `CommandTemplate.config_flag` is `None` (mdformat / dprint / remark) discover their config from `cwd=root` directly; for those families no config flag appears in `cmd`.

## Detection probe

Run once per audit; cache the result for the session. The listing follows `selector.FALLBACK_ORDER` (prettier first).

```sh
command -v prettier          >/dev/null 2>&1 && echo prettier
command -v markdownlint-cli2 >/dev/null 2>&1 && echo markdownlint-cli2
command -v markdownlint      >/dev/null 2>&1 && echo markdownlint
command -v mdformat          >/dev/null 2>&1 && echo mdformat
command -v dprint            >/dev/null 2>&1 && echo dprint
command -v remark            >/dev/null 2>&1 && echo remark
```

When the **baseline** matches a config family (e.g. `.markdownlint.json`) but none of that family's preferred tools is on PATH, `selector.select_tool` falls back to the next available tool in `FALLBACK_ORDER` (`prettier` → `markdownlint-cli2` → `markdownlint` → `mdformat` → `dprint` → `remark`) and runs the first one it finds. The `selected` NDJSON event records the engine that actually ran so consumers can see when the chosen formatter diverges from the baseline-declared family. Only when every tool in `FALLBACK_ORDER` is absent does `selector.select_tool` return `None`: `runner.run_tool` emits a single `missing` event with the install hint and exits 3. There is no implicit hand-rolled-edits path — addressing the missing toolchain is the caller's responsibility, typically by running `recommend-tools.py` to surface install commands.

## Per-tool commands

For each tool, columns are: **Probe** (one-shot detect + version), **Audit** (read-only, parseable output, non-zero exit on findings), **Format** (write-mode, idempotent), **Notes**. The Audit / Format rows show each tool's canonical glob invocation; CLI-driven runs scope every pass to the shared inventory, so the actual `selected` event's `cmd` carries explicit file paths in place of these globs.

### markdownlint-cli2 / markdownlint

Pairs with the markdownlint-family configs — rule configs and cli2-only configs, listed under "Baseline detection and selection".

| Mode | Command |
| --- | --- |
| Probe | `markdownlint-cli2 --version` (or `markdownlint --version`) |
| Audit | `markdownlint-cli2 "**/*.md" "**/*.markdown" "#node_modules" "#.git" "#dist" "#build" "#.venv" "#venv" "#target"` |
| Audit (older CLI) | `markdownlint --ignore-path .gitignore "**/*.md" "**/*.markdown"` |
| Format | `markdownlint-cli2 --fix "**/*.md" "**/*.markdown" "#node_modules" "#.git" "#dist" "#build" "#.venv" "#venv" "#target"` |
| Format (older CLI) | `markdownlint --fix --ignore-path .gitignore "**/*.md" "**/*.markdown"` |

- **Exit 0** = no findings; **exit 1** = findings present; **exit 2** = config / invocation error.
- **Output line shape**: `path/to/file.md:LINE:COL MD### name "fragment"`. The skill emits each non-empty stdout/stderr line verbatim as a `finding` event detail string — no parsing, no field extraction. The line:col prefix IS stripped internally by `runner._normalize_finding_key` when computing the `md-fix` `delta` event so an unfixed finding at a shifted line still counts as `still_open` rather than `resolved + new`, but consumers reading the NDJSON `finding.detail` see the raw line. To skip the line:col prefix for display, parse `^([^:]+):(\d+)(?::(\d+))? (MD\d{3})(?:/(\S+))? (.*)$` on the consumer side.
- **Install hints**: `npm install -g markdownlint-cli2` (canonical — substitute `markdownlint-cli` for the older CLI); `pnpm add -g markdownlint-cli2` / `bun add -g markdownlint-cli2` / `yarn global add markdownlint-cli2` (alternative JS package managers); `mise use -g npm:markdownlint-cli2` (mise via npm backend). No standalone binary; requires a Node runtime.
- **Config argv shape**: a config path is passed as two separate argv elements (`--config <path>`), never the combined `--config=<path>` form — markdownlint-cli2 silently rejects the combined form and treats it as a file glob.

### prettier

Pairs with the prettier-family configs listed under "Baseline detection and selection". Prettier itself also reads a `prettier` key out of `package.json`, but `docs_steward.baseline.BASELINE_CANDIDATES` does NOT include `package.json` — selection happens by filename match, so a repo whose only Prettier config lives under `package.json#prettier` falls through to `universal-subset` and the bundled fallback. Add a standalone `.prettierrc` (or any of the other names above) when you want the skill to detect Prettier.

| Mode | Command |
| --- | --- |
| Probe | `prettier --version` |
| Audit | `prettier --check --parser markdown "**/*.md" "**/*.markdown"` |
| Audit (with `--unwrap`) | `prettier --prose-wrap=never --check --parser markdown "**/*.md" "**/*.markdown"` |
| Format | `prettier --write --parser markdown "**/*.md" "**/*.markdown"` |
| Format (with `--unwrap`) | `prettier --prose-wrap=never --write --parser markdown "**/*.md" "**/*.markdown"` |

- **Exit 0** = formatted; **exit 1** = unformatted files exist (audit) or write error (format); **exit 2** = config / invocation error.
- **Output**: structured but per-mode. In **audit mode** (`--check`) Prettier emits a `Checking formatting...` banner, then one `[warn] <path>` line per unformatted file, then a `Code style issues found in N files. Run Prettier with --write to fix.` summary; in **format mode** (`--write`) it emits `<file> Nms` per write. The skill does not synthesize messages, so each non-empty stdout/stderr line lands verbatim as a `finding` event detail string (audit) or a `changed` event detail string (format) — the `[warn]` prefix on each audit line and the summary line both reach the consumer. NDJSON has no INFO/severity concept; consumers that want bare file paths must strip the `[warn] ` prefix locally (or filter the trailing summary line on text). `--quiet` drops the banner + summary via the preamble filter; the `[warn] <path>` lines are preserved as findings.
- `--prose-wrap=never` is appended when the caller passes `--unwrap`, in both audit and format modes — a caller decision, not a config-derived one: a format run then never re-wraps prose, and an audit run checks against that same unwrapped layout.
- Honors `.prettierignore`; the glob is otherwise unfiltered.
- **Install hints**: `npm install -g prettier` (canonical); `pnpm add -g prettier` / `bun add -g prettier` / `yarn global add prettier` (alternative JS package managers); `volta install prettier` (toolchain manager); `mise use -g npm:prettier` (mise via npm backend); `npx prettier@latest` (one-shot, no install). Requires a Node runtime.

### mdformat

Pairs with `.mdformat.toml` at the repo root. mdformat itself also reads a `[tool.mdformat]` section out of `pyproject.toml`, but `docs_steward.baseline.BASELINE_CANDIDATES` only matches by filename — `pyproject.toml` is not in the candidate list (and adding it would require parsing the TOML to confirm the `[tool.mdformat]` table exists, which the rest of baseline detection deliberately avoids). A repo whose only mdformat config lives under `pyproject.toml#[tool.mdformat]` therefore falls through to `universal-subset` and may select a different formatter. Add a standalone `.mdformat.toml` when you want the skill to detect mdformat.

| Mode | Command |
| --- | --- |
| Probe | `mdformat --version` |
| Audit | `mdformat --check .` (recursive on the working dir) |
| Audit (single file) | `mdformat --check path/to/file.md` |
| Audit (with `--unwrap`) | `mdformat --wrap=no --check .` |
| Format | `mdformat .` |
| Format (with `--unwrap`) | `mdformat --wrap=no .` |
| Format (preserve width) | `mdformat --wrap=N .` |

- **Exit 0** = formatted (audit) or success (format); **non-zero** = changes needed (audit) or error (format).
- **Output**: file paths only. Each non-empty stdout/stderr line is emitted verbatim as a `finding` event detail string (audit) or `changed` (format); no per-file message synthesis.
- `--wrap=no` is appended when the caller passes `--unwrap`, in both audit and format modes — same rule as prettier's `--prose-wrap=never` above.
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

Pairs with the remark-family configs listed under "Baseline detection and selection". Less common today than `prettier` for general markdown but still seen in remark-based pipelines.

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

Complementary tool — not a markdown formatter; it never participates in markdown formatter selection. Used by `md-audit-frontmatter` (and the composite audit's frontmatter pass) to lint YAML frontmatter + fenced YAML blocks extracted from markdown files. Config resolution order: an explicit `--yamllint-config <path>`; otherwise an auto-discovered `.yamllint` / `.yamllint.yaml` / `.yamllint.yml` at the repo root (mirroring yamllint's own standalone lookup); otherwise the skill's bundled `yamllint.yaml` fallback.

| Mode                             | Command                                 |
| -------------------------------- | --------------------------------------- |
| Probe                            | `yamllint --version`                    |
| Audit (per block, fed via stdin) | `yamllint -f parsable -s -c <config> -` |

- **Exit 0** = no findings; **exit 1** = findings present; **exit 2** = config / invocation error.
- **Output line shape**: `stdin:LINE:COL: [LEVEL] message (rule)`. The skill replaces `stdin:LINE:COL` with `<file>:<anchor>` per the no-line-numbers convention; `<anchor>` is `frontmatter` for top-of-file blocks or `yaml fence: <excerpt>` for fenced YAML blocks.
- yamllint reads from stdin (`-`) — no glob argument; the skill pipes each extracted block separately so each finding lands against the correct file + anchor.
- **Install hints**: `pipx install yamllint` (preferred — isolated); `uv tool install yamllint` (fast); `pip install --user yamllint` (user-site); `brew install yamllint` (macOS); `sudo apt install yamllint` / `sudo dnf install yamllint` (Linux distro packages); `mise use -g pipx:yamllint` (mise via pipx backend). Pure-Python; no Node required.

## Install recommendations (`recommend-tools.py`)

The install priority is deliberately different from the selection order above — selection answers _"given multiple tools on PATH, which runs?"_ (favors strict linters), while recommendation answers _"given nothing, what should be installed first?"_ (favors `prettier` for the widest ecosystem fit plus `--prose-wrap=never` support matching the no-hard-wrap preference). `priority.INSTALL_PRIORITY` order: `prettier` → `mdformat` → `markdownlint-cli2` → `dprint` → `remark` → `yamllint`; the first five are markdown formatters, `yamllint` serves the frontmatter pass. The script emits `installed` for each present tool, `recommend` for each missing priority tool (`priority_rank` + `install_options` — platform / package-manager alternatives drawn from the per-tool install hints above), and a single `verdict` event tied to the exit code: `0` when the top-priority tool is already present, `1` when at least one priority tool is missing — the script's only two exits. The skill never invokes the install commands — the user picks the line for their platform.

## Exit-code handling pattern

The skill must distinguish the three classes for every tool:

| Class | Action |
| --- | --- |
| **Clean** (exit 0 in audit) | No findings; skip the file in the report. |
| **Findings** (exit 1 in audit) | Stream each non-empty stdout line verbatim as a `finding` event (and stderr too in AUDIT mode — some tools emit findings there). No rule-code synthesis: consumers that want a `<RULE>` slot should parse the tool's own format from `finding.detail` (e.g. `MD\d{3}` for markdownlint, the rule field in remark's parsable output). The skill stays out of the synthesis business so it doesn't paper over consumer-side variation. |
| **Tool error** (exit ≥ 2, or unexpected stderr) | Append the tool's stdout/stderr as event-stream lines, then emit a single `error` event with `{"exit": N}` and exit 2. There is no implicit hand-rolled-edits fallback after a tool error — addressing the failing tool is on the caller. |

## Caveats

- **Tool drift** — formatter releases change default rules occasionally (e.g. `prettier` flipped `proseWrap` default in 1.9, `markdownlint` added new rules each minor). The skill does not pin versions; trust whatever is on `PATH`. Surface the version in the report header so the user can correlate.
- **Plugin coverage** — `mdformat` requires plugins for GFM tables, footnotes, frontmatter; `remark` requires `remark-preset-*`; `prettier` and `dprint` cover CommonMark + GFM out of the box. Unknown syntax is whatever the chosen tool passes through silently — the orchestrator does not synthesize warnings about unrecognized constructs. The exception is the GFM check: when mdformat is selected, the CLI dispatcher pre-scans target files via `plugins.needs_gfm` and emits a `plugin-missing` event when `mdformat-gfm` is absent.
- **Glob differences** — POSIX `find` and the Node `glob` library expand `**/*.md` differently on Windows shells. When invoking on Windows, prefer `git ls-files '*.md' | xargs <tool>` over a raw glob to avoid the cross-shell expansion gap.
- **Multiple configs, single repo** — configs from different families are complementary, not competing: the composite plan runs the formatter owner plus the read-only markdownlint lint pass, each under its own family's config (see "Baseline detection and selection"). Only configs for the same concern compete, resolved by declaration order; each pass's `selected` event names its governing config, and only the formatter owner ever writes.
- **Manager-installed tools on fresh shells** — `SubprocessRunner` extends PATH with mise / asdf / pipx / brew / cargo / bun / pnpm / volta directories, so tools installed via those managers resolve on Git Bash / WSL / PowerShell even when the harness shell has not activated them.
- **Auto-install is forbidden** — per anti-pattern in `SKILL.md`. Always report missing tools with the install hint; never invoke `npm install` / `pip install` / `cargo install` from the skill.
