# Bundled fallback configs

These files are formatter configs the skill uses **only when the target repo declares none of its own**. Repo config always wins — `docs_steward.baseline.detect_baseline` returns whatever the repo declares first; only when the result is `universal-subset` does `docs_steward.bundled_config.bundled_config_for` substitute a file from this directory.

## What is shipped

| Tool | File | Reason |
| --- | --- | --- |
| `markdownlint` / `markdownlint-cli2` | [`markdownlint.json`](markdownlint.json) | Tool accepts `--config <path>` reliably; covers full rule set in one file. |
| `prettier` | [`prettierrc.json`](prettierrc.json) | Tool accepts `--config <path>`; markdown overrides only, no global side effects. |
| `yamllint` | [`yamllint.yaml`](yamllint.yaml) | Tool accepts `-c <path>`; used by `md-audit-frontmatter` for frontmatter + fenced YAML block linting. Disables line-length, relaxes document-start, allows `true`/`false` only for truthy, keeps key-duplicates as error. |

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

## How to override

Two ways:

1. **Add a config to your repo.** `docs_steward.baseline.detect_baseline` will pick it up; the bundled fallback is skipped. For yamllint specifically, `md-audit-frontmatter.py` auto-discovers `.yamllint` / `.yamllint.yaml` / `.yamllint.yml` at the repo root (mirroring yamllint's own standalone lookup) — the bundled `yamllint.yaml` only kicks in when none of those is present.
2. **Pass `--baseline FILE` to `../../scripts/md-audit.py` / `../../scripts/md-format.py` / `../../scripts/md-fix.py`.** Forces a specific config path and skips auto-detection. The bundled fallback fires only when the resolved baseline is the `universal-subset` sentinel: an arbitrary file path therefore opts out of the bundled defaults, but explicit `--baseline universal-subset` is the same code path as "no config detected" and still applies the bundled config. The `md-audit-frontmatter.py` shim takes the parallel `--yamllint-config FILE` flag — supplying it overrides both auto-discovery and the bundled fallback.

## Editing these files

These configs ship with the skill, not per-repo. Edits affect every fresh repo the skill audits. Before editing, confirm the change should apply globally and preserves the no-hard-wrap default (no line-width enforcement, `proseWrap: never`); per-repo overrides belong in the repo, not here.
