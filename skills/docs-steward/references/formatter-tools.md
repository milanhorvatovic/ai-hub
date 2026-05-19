# Formatter tools — concrete commands

Load on demand from `SKILL.md` section 5.D.4 (audit) and section 7 (fix). Five tools, two modes each (audit / format), one universal probe step, install hints when missing.

## Detection probe

Run once per audit; cache the result for the session. Order matches the style-baseline precedence in step 4 — the first matching tool **whose corresponding config file was chosen as the baseline** wins. When no tool matches, selection walks `FALLBACK_ORDER` and picks the first formatter on PATH (see "Baseline-matched tool missing" below); only when no formatter at all is available does the skill emit `MISSING` and exit 3 — there is no implicit hand-rolled-edits path.

```sh
command -v markdownlint-cli2 >/dev/null 2>&1 && echo markdownlint-cli2
command -v markdownlint       >/dev/null 2>&1 && echo markdownlint
command -v prettier           >/dev/null 2>&1 && echo prettier
command -v mdformat           >/dev/null 2>&1 && echo mdformat
command -v dprint             >/dev/null 2>&1 && echo dprint
command -v remark             >/dev/null 2>&1 && echo remark
```

When the **baseline** matches a config family (e.g. `.markdownlint.json`) but none of that family's preferred tools is on PATH, `selector.select_tool` falls back to the next available tool in `FALLBACK_ORDER` (`markdownlint-cli2` → `markdownlint` → `prettier` → `mdformat` → `dprint` → `remark`) and runs the first one it finds. The `selected` NDJSON event records the engine that actually ran so consumers can see when the chosen formatter diverges from the baseline-declared family. Only when none of the fallback tools is on PATH does the skill emit `MISSING` and exit 3. There is no implicit hand-rolled-edits path; tool selection always resolves to either a formatter on PATH or `MISSING`.

## Per-tool commands

For each tool, columns are: **Probe** (one-shot detect + version), **Audit** (read-only, parseable output, non-zero exit on findings), **Format** (write-mode, idempotent), **Notes**.

### markdownlint-cli2 / markdownlint

Pairs with `.markdownlint.json` / `.markdownlint.jsonc` / `.markdownlint.yaml` / `.markdownlint-cli2.{jsonc,yaml}`.

| Mode | Command |
|---|---|
| Probe | `markdownlint-cli2 --version` (or `markdownlint --version`) |
| Audit | `markdownlint-cli2 "**/*.md" "#node_modules" "#.git" "#dist" "#build" "#.venv"` |
| Audit (older CLI) | `markdownlint --ignore-path .gitignore '**/*.md'` |
| Format | `markdownlint-cli2 --fix "**/*.md" "#node_modules" "#.git" "#dist" "#build" "#.venv"` |
| Format (older CLI) | `markdownlint --fix --ignore-path .gitignore '**/*.md'` |

- **Exit 0** = no findings; **exit 1** = findings present; **exit 2** = config / invocation error.
- **Output line shape**: `path/to/file.md:LINE:COL MD### name "fragment"`. The skill emits each non-empty stdout/stderr line verbatim as a `finding` event detail string — no parsing, no field extraction. The line:col prefix IS stripped internally by `runner._normalize_finding_key` when computing the `md-fix` DELTA so an unfixed finding at a shifted line still counts as `still_open` rather than `resolved + new`, but consumers reading the NDJSON `finding.detail` see the raw line. To skip the line:col prefix for display, parse `^([^:]+):(\d+)(?::(\d+))? (MD\d{3})(?:/(\S+))? (.*)$` on the consumer side.
- **Install hints**: `npm install -g markdownlint-cli2` (canonical — substitute `markdownlint-cli` for the older CLI); `pnpm add -g markdownlint-cli2` / `bun add -g markdownlint-cli2` / `yarn global add markdownlint-cli2` (alternative JS package managers); `mise use -g npm:markdownlint-cli2` (mise via npm backend). No standalone binary; requires a Node runtime.

### prettier

Pairs with `.prettierrc` / `.prettierrc.{json,yaml,yml,js,cjs,mjs,toml}` / `prettier.config.{js,cjs,mjs}` / `package.json#prettier`.

| Mode | Command |
|---|---|
| Probe | `prettier --version` |
| Audit | `prettier --check --parser markdown "**/*.md"` |
| Audit (unwrap-respecting) | `prettier --check --parser markdown --prose-wrap=never "**/*.md"` |
| Format | `prettier --write --parser markdown "**/*.md"` |
| Format (unwrap) | `prettier --write --parser markdown --prose-wrap=never "**/*.md"` |

- **Exit 0** = formatted; **exit 1** = unformatted files exist (audit) or write error (format); **exit 2** = config / invocation error.
- **Output**: file paths only (audit) or `<file> Nms` per write (format). No structured rule codes; the skill does not synthesize messages, so each non-empty stdout/stderr line lands verbatim as a `finding` event detail string (audit) or a `changed` event detail string (format). NDJSON has no INFO/severity concept — consumers that want a human "Prettier would reformat" hint should render it locally from the bare file path in the detail.
- `--prose-wrap=never` is appended automatically by section 5.D.3 when the unwrap gating permits.
- Honors `.prettierignore`; the glob is otherwise unfiltered.
- **Install hints**: `npm install -g prettier` (canonical); `pnpm add -g prettier` / `bun add -g prettier` / `yarn global add prettier` (alternative JS package managers); `volta install prettier` (toolchain manager); `mise use -g npm:prettier` (mise via npm backend); `npx prettier@latest` (one-shot, no install). Requires a Node runtime.

### mdformat

Pairs with `pyproject.toml#[tool.mdformat]` or a standalone `.mdformat.toml`.

| Mode | Command |
|---|---|
| Probe | `mdformat --version` |
| Audit | `mdformat --check .` (recursive on the working dir) |
| Audit (single file) | `mdformat --check path/to/file.md` |
| Format | `mdformat .` |
| Format (unwrap) | `mdformat --wrap=no .` |
| Format (preserve width) | `mdformat --wrap=N .` |

- **Exit 0** = formatted (audit) or success (format); **non-zero** = changes needed (audit) or error (format).
- **Output**: file paths only. Each non-empty stdout/stderr line is emitted verbatim as a `finding` event detail string (audit) or `changed` (format); no per-file message synthesis.
- `--wrap=no` is appended automatically when section 5.D.3 unwrap gating permits.
- Plugins (`mdformat-gfm`, `mdformat-tables`, `mdformat-frontmatter`, `mdformat-footnote`) extend syntax coverage but are not auto-installed; surface their absence as INFO when the file uses the corresponding syntax.
- **Install hints**: `pipx install mdformat` (preferred — isolated); `uv tool install mdformat` (fast); `pip install --user mdformat` (user-site); `brew install mdformat` (macOS); `mise use -g pipx:mdformat` (mise via pipx backend); add `mdformat-gfm` for GitHub-flavored markdown. Pure-Python; no Node required.

### dprint

Pairs with `dprint.json` containing a `markdown` plugin entry.

| Mode | Command |
|---|---|
| Probe | `dprint --version` |
| Audit | `dprint check` |
| Format | `dprint fmt` |

- **Exit 0** = formatted; **non-zero** = changes needed (audit) or error (format).
- **Output**: file paths only. Each non-empty stdout/stderr line is emitted verbatim as a `finding` event detail string (audit) or `changed` (format); no per-file message synthesis.
- Honors `dprint.json`'s `includes` / `excludes`; no glob argument needed.
- **Install hints**: `curl -fsSL https://dprint.dev/install.sh | sh` (POSIX official installer); `iwr https://dprint.dev/install.ps1 -useb | iex` (Windows PowerShell); `brew install dprint` (macOS); `winget install dprint` / `scoop install dprint` (Windows package managers); `cargo install dprint` (via Rust toolchain); `mise use -g aqua:dprint/dprint` (mise via aqua backend). Single static binary regardless of installer.

### remark-cli

Pairs with `.remarkrc` / `.remarkrc.{json,yaml,yml,js,cjs,mjs}`. Less common today than `prettier` for general markdown but still seen in remark-based pipelines.

| Mode | Command |
|---|---|
| Probe | `remark --version` |
| Audit | `remark --quiet --frail "**/*.md"` |
| Format | `remark --output "**/*.md"` |

- `--frail` forces non-zero exit on any warning; the skill relies on this to flip exit semantics into a usable signal.
- `--output` rewrites in place; without it `remark` prints to stdout.
- Output is one VFile message per finding: `path:line:col-line:col  warning  <message>  <rule>  <source>` — parse with `^([^:]+):(\d+):(\d+)-\d+:\d+\s+(warning|error)\s+(.*?)\s+(\S+)\s+(\S+)$`.
- **Install hints**: `npm install -g remark-cli remark-preset-lint-recommended` (canonical — preset is required, otherwise `remark` runs no checks); `pnpm add -g remark-cli remark-preset-lint-recommended` / `bun add -g remark-cli remark-preset-lint-recommended` (alternative JS package managers); `mise use -g npm:remark-cli` (mise via npm backend — install the preset separately).

### yamllint

Complementary tool — not a markdown formatter. Used by `audit-frontmatter` to lint YAML frontmatter + fenced YAML blocks extracted from markdown files. Pairs with `.yamllint` / `.yamllint.yaml` (any of the canonical yamllint config names); the skill's bundled `assets/configs/yamllint.yaml` is used when the repo declares none and no `--yamllint-config` override is passed.

| Mode | Command |
|---|---|
| Probe | `yamllint --version` |
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
|---|---|
| **Clean** (exit 0 in audit) | No findings; skip the file in the report. |
| **Findings** (exit 1 in audit) | Parse stdout; emit one finding per reported issue. Reuse the tool's rule code when present, else synthesize `MD000-<tool>` so the report still has a `<RULE>` slot. |
| **Tool error** (exit ≥ 2, or unexpected stderr) | Append the tool's stdout/stderr as event-stream lines, then emit a single `ERROR` event with `{"exit": N}` and exit 2. There is no implicit hand-rolled-edits fallback after a tool error — addressing the failing tool is on the caller. |

## Caveats

- **Tool drift** — formatter releases change default rules occasionally (e.g. `prettier` flipped `proseWrap` default in 1.9, `markdownlint` added new rules each minor). The skill does not pin versions; trust whatever is on `PATH`. Surface the version in the report header so the user can correlate.
- **Plugin coverage** — `mdformat` requires plugins for GFM tables, footnotes, frontmatter; `remark` requires `remark-preset-*`; `prettier` and `dprint` cover CommonMark + GFM out of the box. When a syntax the file uses is unrecognized by the chosen tool, the audit emits INFO and proceeds; do not crash on unknown syntax.
- **Glob differences** — POSIX `find` and the Node `glob` library expand `**/*.md` differently on Windows shells. When invoking on Windows, prefer `git ls-files '*.md' | xargs <tool>` over a raw glob to avoid the cross-shell expansion gap.
- **Multiple tools, single repo** — when both `.prettierrc` and `.markdownlint.json` exist, the style-baseline precedence in step 4 picks one. Do not run both — that produces conflicting rewrites. The non-baseline config gets an INFO finding so the user can consolidate.
- **Auto-install is forbidden** — per anti-pattern in `SKILL.md`. Always report missing tools with the install hint; never invoke `npm install` / `pip install` / `cargo install` from the skill.
