# Bundled fallback configs

These files are tool configs the skill uses **only when the target repo declares none of its own for that tool family**. Repo config always wins — `docs_steward.baseline.detect_baselines` surfaces everything the repo declares and `docs_steward.selector.build_audit_plan` gives each family's pass its own config; only when a concern resolves to the `universal-subset` sentinel does `docs_steward.bundled_config.bundled_config_for` substitute a file from this directory for that pass.

## What is shipped

| Tool | File | Reason |
| --- | --- | --- |
| `markdownlint` / `markdownlint-cli2` | `markdownlint.json` | Tool accepts `--config <path>` reliably; covers full rule set in one file. |
| `prettier` | `prettierrc.json` | Tool accepts `--config <path>`; markdown overrides only, no global side effects. |
| `yamllint` | `yamllint.yaml` | Tool accepts `-c <path>`; used by `md-audit-frontmatter` for frontmatter + fenced YAML block linting. Disables line-length, relaxes document-start, allows `true`/`false` only for truthy, keeps key-duplicates as error. |

## What is intentionally **not** shipped

| Tool | Reason |
| --- | --- |
| `mdformat` | No `--config` flag for arbitrary paths; config must live in `pyproject.toml` or `.mdformat.toml` discovered from CWD upward. Bundling would require symlink hacks or invasive copy-in / copy-out. |
| `dprint` | Requires the markdown plugin URL pinned in the config (e.g. `https://plugins.dprint.dev/markdown-0.17.8.wasm`). Pinning rots; a stale bundled URL would silently break. |
| `remark` | Useful behavior requires an installed preset (e.g. `remark-preset-lint-recommended`). The skill cannot guarantee the preset is on the user's machine. |

For these three tools, when the repo declares no config the skill runs them with their **out-of-the-box defaults**. The `selected` NDJSON event flags this so the caller knows enforcement is weaker than the markdownlint / prettier paths.

## Why these settings

All defaults track one rule: never hard-wrap prose — line-width is the preview tool's job; source files must not encode visual width.

- `MD013: false` — disable markdownlint's line-length rule.
- `MD024: { siblings_only: true }` — allow duplicate headings under different parents (common in changelogs, design docs).
- `MD033: false` — allow inline HTML (`<details>`, `<br>`, `<img>` with attributes).
- `MD041: false` — allow files to not begin with a top-level heading (frontmatter, includes, ADR templates).
- `MD060: false` — allow compact table style (`|col|---|` without surrounding pipe padding); the rule's "consistent" default expects `| col | --- |` which adds noise without information.
- Prettier `proseWrap: never` — never re-wrap paragraphs.
- Prettier `embeddedLanguageFormatting: "auto"` — keep prettier's default of formatting code inside fenced blocks. The skill does not impose `"off"` here; a repo whose markdown carries illustrative snippets it does not want reformatted (e.g. GitHub-Actions `${{ }}` examples) declares its own `.prettierrc` with `"off"` to override the fallback.

## How to override

These bundled files are machine-local: they ship with the skill and are never committed to the audited repo, so CI, pre-commit hooks, and teammates checking out the repo see none of them — an audit that passes locally under a bundled fallback enforces nothing anywhere else. Committing an explicit config (for the no-wrap house style, a `.prettierrc.json` with `proseWrap: never` markdown overrides) is what turns the preference into an enforceable convention; the bundled defaults are a safety net for repos that have not decided yet, not a substitute for deciding.

Two ways to override:

1. **Add a config to your repo.** `docs_steward.baseline.detect_baselines` will pick it up; the bundled fallback is skipped for that tool family's pass. For yamllint specifically, `md-audit-frontmatter.py` auto-discovers `.yamllint` / `.yamllint.yaml` / `.yamllint.yml` at the repo root (mirroring yamllint's own standalone lookup) — the bundled `yamllint.yaml` only kicks in when none of those is present.
2. **Pass `--baseline FILE` to the `md-audit.py` / `md-format.py` / `md-fix.py` entry shims.** Forces a specific config path onto the formatter owner (the complementary lint and frontmatter passes stay derived from what the repo declares). The bundled fallback fires only when the resolved baseline is the `universal-subset` sentinel: an arbitrary file path therefore opts out of the bundled defaults, but explicit `--baseline universal-subset` is the same code path as "no config detected" and still applies the bundled config. The `md-audit-frontmatter.py` shim takes the parallel `--yamllint-config FILE` flag — supplying it overrides both auto-discovery and the bundled fallback.

## Editing these files

These configs ship with the skill, not per-repo. Edits affect every fresh repo the skill audits. Before editing, confirm the change should apply globally and preserves the no-hard-wrap default (no line-width enforcement, `proseWrap: never`); per-repo overrides belong in the repo, not here.
